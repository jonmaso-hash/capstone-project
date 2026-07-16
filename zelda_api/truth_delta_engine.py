# zelda_api/truth_delta_engine.py
"""
Truth Delta Verification Engine
Compares claimed data vs observed data to detect discrepancies.
Highest-value diligence feature: Answers "Is the founder telling the truth?"
"""
import json
import logging
import re
from urllib.parse import urlparse

from django.conf import settings

from .truth_delta_models import ClaimedDatapoint, ObservedDatapoint, TruthDeltaReport
from .truth_delta_sources import data_source_manager

logger = logging.getLogger(__name__)


TRUTH_DELTA_SYSTEM_PROMPT = """You are Zelda's Truth Delta verification analyst. You are given a founder's/seller's self-reported claims from a pitch deck, alongside data pulled from independent public sources (SEC EDGAR filings, Crunchbase, recent news headlines) for the same company. Your job is to judge how well the claims hold up against that external data.

ABSOLUTE RULES:
- Only reason about the claims and observed data given to you. Never invent a number, source, or fact that isn't in the input.
- If a claim has no matching observed data, say so plainly in per_claim — that is NOT evidence the claim is false, only that it could not be checked. Do not penalize the score for unchecked claims.
- A claim that is directionally consistent with observed data (e.g. within a reasonable range, accounting for the observed data possibly being from a different, older time period) should not be flagged as a contradiction.
- A claim that is significantly higher than observed data (e.g. claiming 10x the SEC-reported revenue) is a real red flag and should lower the score substantially.
- News headlines are supporting context only, not a verified numeric source — they can corroborate a narrative (e.g. a funding round being reported) but never confirm an exact figure.

Return ONLY valid JSON in this exact shape, no markdown fences, no other text:
{
  "overall_truth_score": <0-100 integer, your holistic judgment across only the CHECKED claims>,
  "credibility_risk": "<low|medium|high|critical>",
  "summary": "<2-4 sentence plain-English summary a busy investor can read in 10 seconds>",
  "per_claim": [
    {"category": "<claim category>", "claimed": "<claimed value>", "observed": "<observed value or 'no external data found'>", "assessment": "<one short sentence>"}
  ]
}"""


def _risk_band(score: float) -> str:
    """
    Shared score->risk mapping so 'credibility_risk' means the same thing
    whether Claude produced it or the numeric fallback did.
    """
    if score >= 80:
        return 'low'
    if score >= 60:
        return 'medium'
    if score >= 40:
        return 'high'
    return 'critical'


class TruthDeltaEngine:
    def verify_document(self, document_id):
        claims = ClaimedDatapoint.objects.filter(document_id=document_id)
        if not claims.exists():
            logger.warning(f"No claims found for document {document_id}")
            return None

        document = claims.first().document
        company_name = document.source_entity
        domain = self._resolve_domain(document)

        # External-source failures must never block report creation — a
        # report saying "no external data found" is a true, useful result,
        # not a broken one.
        try:
            data_source_manager.create_observed_datapoints(document, company_name, domain)
        except Exception as e:
            logger.warning(f"External data fetch failed for document {document_id}: {e}")

        observed = ObservedDatapoint.objects.filter(document_id=document_id)

        headlines = []
        try:
            headlines = data_source_manager.fetch_news_headlines(company_name)
        except Exception as e:
            logger.warning(f"News headline fetch failed for document {document_id}: {e}")

        if not observed.exists() and not headlines:
            checked_sources = ['SEC EDGAR']
            if settings.CRUNCHBASE_API_KEY:
                checked_sources.append('Crunchbase')
            if settings.NEWS_API_KEY:
                checked_sources.append('recent news')
            report = TruthDeltaReport.objects.create(
                document_id=document_id,
                overall_truth_score=None,
                credibility_risk='unknown',
                summary=(
                    f"No public data could be found to independently verify these claims "
                    f"(checked {', '.join(checked_sources)}). This is not a confirmation the "
                    f"claims are accurate — only that no corroborating or contradicting "
                    f"external data was found for \"{company_name}\"."
                ),
                details={'claims': self._serialize_claims(claims), 'observed': []},
            )
            return report

        comparison = self._build_comparison(claims, observed)
        result = self._call_claude_for_verification(company_name, comparison, headlines, document)

        if result is None:
            # Claude unavailable (circuit open, API error, malformed JSON)
            # — fall back to a purely numeric score computed only from
            # already-gathered real numbers, rather than producing nothing.
            result = self._numeric_fallback(comparison)

        report = TruthDeltaReport.objects.create(
            document_id=document_id,
            overall_truth_score=result['overall_truth_score'],
            credibility_risk=result['credibility_risk'],
            summary=result['summary'],
            details={
                'claims': self._serialize_claims(claims),
                'observed': self._serialize_observed(observed),
                'per_claim': result.get('per_claim', []),
            },
        )
        return report

    # --- helpers ---

    def _resolve_domain(self, document):
        """Best-effort company domain, for Crunchbase's domain-first lookup — None if unavailable."""
        from matchmaking.models import Application, SellerApplication

        app = Application.objects.filter(user=document.uploaded_by).first()
        if app and app.company_website:
            return self._extract_domain(app.company_website)

        seller = SellerApplication.objects.filter(user=document.uploaded_by).first()
        if seller and seller.company_website:
            return self._extract_domain(seller.company_website)

        return None

    @staticmethod
    def _extract_domain(url: str):
        netloc = urlparse(url if '://' in url else f'https://{url}').netloc
        return netloc.replace('www.', '') or None

    def _build_comparison(self, claims, observed):
        """
        Pairs each claim with the highest-credibility observed datapoint of
        the same category (if any), and computes a numeric discrepancy
        percentage when both sides have a number.
        """
        observed_by_category = {}
        for obs in observed:
            observed_by_category.setdefault(obs.category, []).append(obs)

        rows = []
        for claim in claims:
            matches = observed_by_category.get(claim.category, [])
            best = max(matches, key=lambda o: o.source_credibility) if matches else None

            discrepancy_pct = None
            if best and claim.claimed_value_numeric is not None and best.observed_value_numeric:
                discrepancy_pct = round(
                    (claim.claimed_value_numeric - best.observed_value_numeric) / best.observed_value_numeric * 100, 1
                )

            rows.append({
                'category': claim.category,
                'claimed_value': claim.claimed_value,
                'claimed_value_numeric': claim.claimed_value_numeric,
                'observed_value': best.observed_value if best else None,
                'observed_value_numeric': best.observed_value_numeric if best else None,
                'observed_source': best.source.source_name if best and best.source else None,
                'observed_time_period': best.time_period if best else None,
                'discrepancy_pct': discrepancy_pct,
            })
        return rows

    @staticmethod
    def _serialize_claims(claims):
        return [
            {'category': c.category, 'claimed_value': c.claimed_value, 'claimed_value_numeric': c.claimed_value_numeric, 'unit': c.unit}
            for c in claims
        ]

    @staticmethod
    def _serialize_observed(observed):
        return [
            {
                'category': o.category, 'observed_value': o.observed_value,
                'source': o.source.source_name if o.source else None, 'time_period': o.time_period,
            }
            for o in observed
        ]

    def _call_claude_for_verification(self, company_name, comparison, headlines, document):
        """
        Qualitative judgment on top of the raw comparison — same call
        convention as the rest of zelda_api (local anthropic import, Sonnet
        model, circuit breaker, usage logging, markdown-fence-stripped JSON
        parse). Uses its own circuit ('claude_truth_delta') rather than the
        shared 'claude_api' one, so a burst of malformed-claim failures
        here can't trip the breaker for memo/valuation generation too.
        Returns None (never raises) on any failure, so the caller can fall
        back to the numeric-only path.
        """
        import anthropic
        from zelda_api.circuit_breaker import call_with_breaker
        from zelda_api.intelligence_pipeline import _log_anthropic_usage

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        user_content = json.dumps({
            'company_name': company_name,
            'claims_vs_observed': comparison,
            'recent_news_headlines': headlines,
        }, indent=2, default=str)

        try:
            response = call_with_breaker(
                'claude_truth_delta', client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=1536,
                system=TRUTH_DELTA_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            _log_anthropic_usage(response, document, 'truth delta verification')

            raw = response.content[0].text.strip()
            if raw.startswith('```'):
                raw = re.sub(r'^```(?:json)?\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)

            parsed = json.loads(raw)
            if not isinstance(parsed, dict) or 'overall_truth_score' not in parsed:
                logger.error("Truth Delta Claude response missing overall_truth_score")
                return None

            score = max(0.0, min(100.0, float(parsed['overall_truth_score'])))
            parsed['overall_truth_score'] = score
            if parsed.get('credibility_risk') not in {'low', 'medium', 'high', 'critical'}:
                parsed['credibility_risk'] = _risk_band(score)
            parsed.setdefault('summary', '')
            parsed.setdefault('per_claim', [])
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Truth Delta Claude JSON parse error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Truth Delta Claude call failed: {str(e)}")
            return None

    def _numeric_fallback(self, comparison):
        """
        Used only when Claude is unavailable. A plain arithmetic score
        computed from real claimed-vs-observed numbers already gathered —
        never a fabricated figure, and never penalizes a claim just for
        having no external match (absence of data isn't evidence of a lie).
        """
        checked = [row for row in comparison if row['discrepancy_pct'] is not None]
        if not checked:
            return {
                'overall_truth_score': None,
                'credibility_risk': 'unknown',
                'summary': (
                    "Automated qualitative verification (Claude) was unavailable, and none of "
                    "the claims had a matching external datapoint to compare against numerically."
                ),
                'per_claim': [],
            }

        # Each checked claim starts at 100 and loses a point per percent of
        # deviation, capped at 100 so one wildly-off claim can't zero out
        # an otherwise-consistent report on its own.
        per_claim_scores = [max(0, 100 - min(abs(row['discrepancy_pct']), 100)) for row in checked]
        overall = round(sum(per_claim_scores) / len(per_claim_scores), 1)

        return {
            'overall_truth_score': overall,
            'credibility_risk': _risk_band(overall),
            'summary': (
                f"Claude was unavailable, so this score is a plain arithmetic comparison of "
                f"{len(checked)} claim(s) against matching external data — no qualitative "
                f"judgment was applied."
            ),
            'per_claim': [
                {
                    'category': row['category'], 'claimed': row['claimed_value'], 'observed': row['observed_value'],
                    'assessment': f"{row['discrepancy_pct']}% difference from observed value ({row['observed_source']})",
                }
                for row in checked
            ],
        }
