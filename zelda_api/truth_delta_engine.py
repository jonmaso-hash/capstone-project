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

from .truth_delta_models import (
    TRUTH_DELTA_SEMANTICS, ClaimedDatapoint, ObservedDatapoint, TruthDeltaReport,
)
from .truth_delta_sources import data_source_manager
from .source_capabilities import CAN_CORROBORATE, CAN_ESTABLISH, INFORMATIONAL_ONLY
from . import truth_delta_narrative as narrative
from .financial_metrics import currency_comparison_reason

logger = logging.getLogger(__name__)


TRUTH_DELTA_SYSTEM_PROMPT = """You are Zelda's Truth Delta explainer. You are given a founder's/seller's self-reported claims from a pitch deck, the data Zelda pulled from independent public sources for the same company, and Zelda's verdict on each claim. Your only job is to explain each verdict in plain English. You do not judge the claims, and you do not score them.

ABSOLUTE RULES:
- Only reason about the claims and observed data given to you. Never invent a number, source, or fact that isn't in the input.
- Each row carries `zelda_state` (verified, contradicted or no_data) and, for no_data, `zelda_reason`. These are Zelda's final verdict on that claim and are not yours to change. Your per_claim `assessment` explains that verdict in one short sentence. Never call a claim verified, confirmed, contradicted, overstated, inaccurate or a red flag unless its zelda_state says so; a no_data claim was not established either way, whatever the numbers look like.
- A row's `corroboration` entries come from lower-authority sources: describe them as consistent with or differing from the claim, never as verification, and treat an entry with "independent": false as no extra confirmation. `context` entries are background only and never evidence about the claim.
- If a claim has no matching observed data, say so plainly — that is NOT evidence the claim is false, only that it could not be checked.
- News headlines are context only, never a verified numeric source.

Return ONLY valid JSON in this exact shape, no markdown fences, no other text:
{
  "per_claim": [
    {"category": "<claim category>", "assessment": "<one short sentence explaining zelda_state>"}
  ]
}"""


def canonical_score(stats):
    """
    (overall_truth_score, credibility_risk) from the canonical counts alone (R-003b).

    score = verified / (verified + contradicted) * 100. Only claims Zelda
    established either way are scored: a no_data claim -- period_unknown,
    no_external_evidence, corroboration_only, source_unavailable -- is excluded,
    however far apart its raw numbers are, because Zelda has said they cannot be
    compared. With nothing scoreable there is no score and the risk is 'unknown':
    Nike's 0 verified / 0 contradicted is "insufficient evidence", not 42/100.

    Before this the model chose both numbers. It was shown a 13.8% gap and a
    prompt calling such gaps "a real red flag", and scored a claim Zelda could
    not compare.
    """
    verified = stats.get('verified') or 0
    scoreable = verified + (stats.get('contradicted') or 0)
    if not scoreable:
        return None, 'unknown'
    score = round(verified / scoreable * 100, 1)
    return score, _risk_band(score)


def _risk_band(score: float) -> str:
    """Score -> risk band, the one mapping every report uses."""
    if score >= 80:
        return 'low'
    if score >= 60:
        return 'medium'
    if score >= 40:
        return 'high'
    return 'critical'


class TruthDeltaEngine:
    # Stamped onto every report this engine writes, so a state can later be
    # explained by the evidence AND the rules available when it was produced.
    # Without it, "Zelda changed its mind" is indistinguishable from "Zelda
    # used to be wrong", and a reader cannot tell new evidence from new rules.
    semantics_version = TRUTH_DELTA_SEMANTICS

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
        # What each source DID, not just what it returned. A decline caused by
        # an unreachable source must not be recorded as an absence of evidence
        # about the company.
        source_diagnostics = {}
        try:
            data_source_manager.create_observed_datapoints(
                document, company_name, domain, diagnostics=source_diagnostics)
        except TypeError:
            # A caller or double that predates the diagnostics argument.
            data_source_manager.create_observed_datapoints(document, company_name, domain)
        except Exception as e:
            logger.warning(f"External data fetch failed for document {document_id}: {e}")
            source_diagnostics.setdefault('fetch', 'request_error')

        # Lower-authority providers write role-stamped rows through their own
        # adapters (Task 8), never through the establishing path above. Their
        # outcomes are kept apart from source_diagnostics on purpose: a
        # DataForB2B timeout must not relabel a revenue claim's absence as
        # "source unavailable" when DataForB2B can never speak to revenue.
        provider_outcomes = {}
        try:
            from .dataforb2b_adapter import observe as observe_dataforb2b
            provider_outcomes['dataforb2b'] = observe_dataforb2b(document, list(claims))
        except Exception as e:
            logger.warning(f"DataForB2B observation failed for document {document_id}: {type(e).__name__}")
            provider_outcomes['dataforb2b'] = 'provider_error'

        observed = ObservedDatapoint.objects.filter(document_id=document_id)
        establishing = observed.filter(role=CAN_ESTABLISH)

        headlines = []
        try:
            headlines = data_source_manager.fetch_news_headlines(company_name)
        except Exception as e:
            logger.warning(f"News headline fetch failed for document {document_id}: {e}")

        if not establishing.exists() and not headlines:
            # The same list the surfaces render, from the same helper: news is
            # fetched when configured but yields no comparable datapoint, so
            # listing it among the sources a claim was "checked" against
            # overstates what happened. See zelda_api/disclaimers.py.
            from .disclaimers import verifying_source_names
            checked_sources = verifying_source_names()

            # A source that never answered was not "checked", and saying it
            # was turns a failed attempt into a statement about the company --
            # the same conflation the grounding layer refuses to make. Now
            # that diagnostics actually reach the report, a summary claiming
            # the sources were checked would contradict the report's own data.
            unreachable = sorted(
                source for source, reason in (source_diagnostics or {}).items()
                if reason in TruthDeltaReport.SOURCE_FAILURE_REASONS
            )
            corroborated = observed.filter(role=CAN_CORROBORATE).exists()
            if unreachable:
                summary = (
                    f"Public sources could not be reached, so these claims were left "
                    f"unchecked rather than found unsupported. This says nothing about "
                    f"\"{company_name}\" — only that the attempt did not complete."
                )
            elif corroborated:
                summary = (
                    f"No authoritative source could verify these claims. Lower-authority "
                    f"data (LinkedIn-derived) is shown alongside them as corroboration "
                    f"only; it does not verify or contradict anything about "
                    f"\"{company_name}\"."
                )
            else:
                summary = (
                    f"No public data could be found to independently verify these claims "
                    f"(checked {', '.join(checked_sources)}). This is not a confirmation the "
                    f"claims are accurate — only that no corroborating or contradicting "
                    f"external data was found for \"{company_name}\"."
                )

            # Even with nothing to compare against, record WHAT could not be
            # compared. Without this the report has no chain at all, so a
            # reader cannot tell which claims were left unchecked or why --
            # and the decline carries no reason.
            comparison = self._build_comparison(claims, observed)
            states, reasons, stats = self._canonical_state(comparison, source_diagnostics)
            # Nothing establishing, so nothing scoreable: (None, 'unknown').
            score, risk = canonical_score(stats)
            report = TruthDeltaReport.objects.create(
                document_id=document_id,
                engine_version=self.semantics_version,
                overall_truth_score=score,
                credibility_risk=risk,
                summary=summary,
                details={
                    'claims': self._serialize_claims(claims), 'observed': [],
                    'source_diagnostics': source_diagnostics,
                    'provider_outcomes': provider_outcomes,
                    'comparison': comparison,
                    # The same claim table as the other branch, written the same way.
                    'per_claim': narrative.claim_rows(comparison, states, reasons),
                },
            )
            return report

        comparison = self._build_comparison(claims, observed)
        # The verdict is decided BEFORE any prose, by the same rules every
        # surface reads (R-003). The model is told it; it does not decide it.
        states, reasons, stats = self._canonical_state(comparison, source_diagnostics)
        result = self._call_claude_for_verification(
            company_name, comparison, headlines, document, states=states, reasons=reasons)
        explanations = {}
        summary = narrative.summary(states, reasons, comparison, stats, headlines)
        if result is None:
            # Claude unavailable (circuit open, API error, malformed JSON).
            # Nothing it would have produced decides anything any more, so the
            # report is complete without it; the reader is told no
            # explanation ran, and each row shows Zelda's own reason.
            summary = f"{summary} {self._numeric_fallback(comparison)['summary']}"
        else:
            explanations = {
                row.get('category'): row.get('assessment')
                for row in result.get('per_claim') or [] if isinstance(row, dict)
            }
        # From the canonical counts, never from the model (R-003b).
        score, risk = canonical_score(stats)

        report = TruthDeltaReport.objects.create(
            document_id=document_id,
            engine_version=self.semantics_version,
            overall_truth_score=score,
            credibility_risk=risk,
            # Composed from the canonical state; the model's summary is not stored.
            summary=summary,
            details={
                'claims': self._serialize_claims(claims),
                'observed': self._serialize_observed(observed),
                # The canonical intermediate artifact. Previously built, handed
                # to Claude and discarded, which left the model's prose as the
                # only surviving account of a comparison it did not perform.
                'comparison': comparison,
                'source_diagnostics': source_diagnostics,
                'provider_outcomes': provider_outcomes,
                # One row per stored comparison row -- the model can neither
                # add nor drop a claim -- with deterministic observed text and
                # a model explanation only where the guard accepted it.
                'per_claim': narrative.claim_rows(comparison, states, reasons, explanations),
            },
        )
        return report

    @staticmethod
    def _canonical_state(comparison, source_diagnostics):
        """
        (states, reasons, stats) for a comparison, computed by
        TruthDeltaReport's own rules on an unsaved report -- so there is still
        exactly one implementation of what a pairing establishes.
        """
        canonical = TruthDeltaReport(engine_version=TruthDeltaEngine.semantics_version,
                                     details={'comparison': comparison,
                                              'source_diagnostics': source_diagnostics})
        for row in comparison:
            row['zelda_state'], row['zelda_reason'], _ = canonical._row_state(row)
        return canonical.category_states(), canonical.grounding_reasons(), canonical.verifiability_stats()

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
            # Only an establishing observation may become THE observation the
            # state is computed from. A corroborating one is attached as
            # agreeing or dissenting evidence and an informational one as
            # context; neither can verify or contradict, alone or against an
            # establishing source. This is the single place a claim is paired
            # with evidence, so it is the single place that rule lives.
            establishing = [o for o in matches if o.role == CAN_ESTABLISH]
            compatible = [o for o in establishing if not currency_comparison_reason(
                claim.category, claim.currency, o.currency)]
            candidates = compatible or establishing
            best = max(candidates, key=lambda o: o.source_credibility) if candidates else None
            currency_reason = (currency_comparison_reason(claim.category, claim.currency, best.currency)
                               if best else None)

            discrepancy_pct = None
            if best and not currency_reason and claim.claimed_value_numeric is not None and best.observed_value_numeric:
                discrepancy_pct = round(
                    (claim.claimed_value_numeric - best.observed_value_numeric) / best.observed_value_numeric * 100, 1
                )

            rows.append({
                'category': claim.category,
                'claim_id': claim.pk,
                'claimed_value': claim.claimed_value,
                'claimed_value_numeric': claim.claimed_value_numeric,
                'claim_currency': claim.currency,
                'observed_value': best.observed_value if best else None,
                'observed_value_numeric': best.observed_value_numeric if best else None,
                'observed_currency': best.currency if best else None,
                'observed_source': best.source.source_name if best and best.source else None,
                # WHICH SOURCE is not WHICH COMPANY AT THAT SOURCE. "SEC EDGAR"
                # alone cannot distinguish this business from a dormant
                # registrant sharing its former name -- the confusion the
                # identity authority exists to settle. Carried from the
                # observation, never re-resolved here: a second lookup at this
                # boundary would be a second identity authority.
                'observed_registrant': (best.registrant or None) if best else None,
                'observed_time_period': best.time_period if best else None,
                'discrepancy_pct': discrepancy_pct,
                # Provenance. A contradiction has to be explainable from what
                # was stored: which sentence the claim came from, which source
                # the datapoint came from, and how much that source is trusted.
                # Without it the state is an accusation nobody can audit.
                'claim_raw_text': claim.claimed_value,
                'observed_raw_value': best.observed_value if best else None,
                'source_credibility': best.source_credibility if best else None,
                # ClaimedDatapoint carries no period yet. Recorded explicitly
                # as unknown rather than omitted, because the grounding rule
                # reads it: an unknown period blocks a contradiction and only
                # qualifies an agreement.
                'claim_period': None,
                'observed_role': CAN_ESTABLISH if best else None,
                'observed_origin': (best.evidence_origin or None) if best else None,
                'corroboration': [
                    self._corroboration_entry(claim, obs, best)
                    for obs in matches if obs.role == CAN_CORROBORATE
                ],
                'context': [
                    {'value': obs.observed_value, 'source': obs.source.source_name if obs.source else None,
                     'origin': obs.evidence_origin or None, 'period': obs.time_period or None,
                     'currency': obs.currency}
                    for obs in matches if obs.role == INFORMATIONAL_ONLY
                ],
            })
        return rows

    @staticmethod
    def _corroboration_entry(claim, obs, best):
        """
        One corroborating observation, described against the claim. `agrees`
        uses the category's grounding tolerance; `independent` is False when
        it shares an origin with the establishing observation, because two
        readings of one upstream are not two confirmations.
        """
        from .truth_delta_models import TruthDeltaReport

        tolerance = TruthDeltaReport.GROUNDING_TOLERANCE.get(claim.category, TruthDeltaReport.DEFAULT_TOLERANCE)
        agrees = None
        discrepancy_pct = None
        currency_reason = currency_comparison_reason(claim.category, claim.currency, obs.currency)
        if not currency_reason and claim.claimed_value_numeric is not None and obs.observed_value_numeric:
            gap = (claim.claimed_value_numeric - obs.observed_value_numeric) / obs.observed_value_numeric
            discrepancy_pct = round(gap * 100, 1)
            agrees = abs(gap) <= tolerance
        return {
            'value': obs.observed_value,
            'value_numeric': obs.observed_value_numeric,
            'currency': obs.currency,
            'comparison_reason': currency_reason,
            'source': obs.source.source_name if obs.source else None,
            'origin': obs.evidence_origin or None,
            'period': obs.time_period or None,
            'agrees': agrees,
            'discrepancy_pct': discrepancy_pct,
            'independent': not (best is not None and best.evidence_origin
                                and best.evidence_origin == obs.evidence_origin),
        }

    @staticmethod
    def _serialize_claims(claims):
        return [
            {'category': c.category, 'claimed_value': c.claimed_value, 'claimed_value_numeric': c.claimed_value_numeric,
             'unit': c.unit, 'currency': c.currency}
            for c in claims
        ]

    @staticmethod
    def _serialize_observed(observed):
        return [
            {
                'category': o.category, 'observed_value': o.observed_value,
                'currency': o.currency,
                'source': o.source.source_name if o.source else None, 'time_period': o.time_period,
                'role': o.role, 'origin': o.evidence_origin or None,
            }
            for o in observed
        ]

    def _call_claude_for_verification(self, company_name, comparison, headlines, document,
                                      states=None, reasons=None):
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

        from .anthropic_client import background_anthropic_client
        client = background_anthropic_client()

        # Each row carries the verdict the model is to explain, never decide.
        states, reasons = states or {}, reasons or {}
        rows = [
            {**row, 'zelda_state': row.get('zelda_state', states.get(row.get('category'), 'no_data')),
             'zelda_reason': row.get('zelda_reason', reasons.get(row.get('category')))}
            for row in comparison
        ]
        user_content = json.dumps({
            'company_name': company_name,
            'claims_vs_observed': rows,
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
            if not isinstance(parsed, dict) or not isinstance(parsed.get('per_claim'), list):
                logger.error("Truth Delta Claude response missing per_claim")
                return None
            # Only the explanations are read. Any score, risk or summary the
            # model adds anyway is ignored: those are Zelda's (R-003, R-003b).
            return {'per_claim': parsed['per_claim']}

        except json.JSONDecodeError as e:
            logger.error(f"Truth Delta Claude JSON parse error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Truth Delta Claude call failed: {str(e)}")
            return None

    def _numeric_fallback(self, comparison):
        """
        Used only when Claude is unavailable: the sentence that tells the
        reader no explanation ran.

        It used to compute its own score from every raw gap -- the same
        mistake the model made, in arithmetic: Nike's 13.8% revenue gap, which
        Zelda cannot compare (period unknown), scored as a 13.8-point penalty.
        The score now comes from canonical_score() on every path, so nothing
        here is a number.
        """
        return {'summary': ('Automated explanations (Claude) were unavailable, so each claim shows '
                            "Zelda's own reason; the verdicts and the score do not depend on them.")}
