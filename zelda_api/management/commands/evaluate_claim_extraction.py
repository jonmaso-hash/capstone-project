# zelda_api/management/commands/evaluate_claim_extraction.py
"""
Django management command: evaluate_claim_extraction

Runs the manually annotated corpus in zelda_api/evaluation_corpus.py
through the real claim-extraction pipeline (_chunk_document ->
_analyze_document -> extract_claims_from_insights — none of which call
Claude, so this costs nothing to re-run) and scores the resulting
ClaimedDatapoint rows against ground truth: precision, recall,
unsupported-claim rate, and (optionally) how many extracted claims have
real external evidence available via SEC EDGAR.

--check-external-evidence doesn't just report a single coverage
percentage — it attributes every gap to a specific cause (company is
genuinely private, the resolver failed to find a real public company,
SEC timed out, or the claim category has no SEC data source at all),
since those call for entirely different fixes and a blended percentage
can't tell them apart. "Resolver miss" is cross-referenced against the
corpus's own is_real_public_company annotation, so a private company
correctly having no SEC data is never counted as a bug.

Every DocumentSource this command creates is deleted at the end of the
run (cascade-deletes its chunks/insights/claims/observed-datapoints too),
so re-running this repeatedly never accumulates junk in the dev database.

Usage:
    python manage.py evaluate_claim_extraction
    python manage.py evaluate_claim_extraction --check-external-evidence
    python manage.py evaluate_claim_extraction --verbose
    python manage.py evaluate_claim_extraction --by-sector
"""
from collections import Counter, defaultdict
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from zelda_api.evaluation_corpus import CORPUS, ALL_CATEGORIES
from zelda_api.vector_models import DocumentSource
from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
from zelda_api.truth_delta_models import ClaimedDatapoint, ObservedDatapoint
from zelda_api.truth_delta_tasks import extract_claims_from_insights

User = get_user_model()

# Map the pipeline's 8 IntelligenceInsight categories to the same
# ClaimedDatapoint categories extract_claims_from_insights uses — mirrors
# truth_delta_tasks.py's own category_mapping exactly, since only these 6
# ever produce a ClaimedDatapoint at all (Problem/Product/Risk are
# narrative and never map to a numeric claim category).
CATEGORY_MAPPING = {
    'Revenue': 'revenue', 'Team': 'employees', 'Funding': 'funding_raised',
    'Traction': 'customers', 'Market': None, 'Problem': None, 'Product': None, 'Risk': None,
}

# Only these claim categories can ever be matched against SEC data —
# SECFilingsIntegration has no extract_funding/extract_customers/
# extract_market_size implementation (no XBRL concept reliably captures
# them), so a Funding or Traction claim is structurally unverifiable via
# SEC regardless of how well the company resolves. Counting these against
# "coverage" would make 100% unreachable even for a perfect resolver.
SEC_VERIFIABLE_CLAIM_CATEGORIES = {'revenue', 'employees'}


class Command(BaseCommand):
    help = 'Score claim extraction against the manually annotated evaluation corpus (see evaluation_corpus.py)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-external-evidence', action='store_true',
            help='Also query SEC EDGAR (live, free, no key needed, cached) to compute verification coverage, attributed by cause.',
        )
        parser.add_argument('--verbose', action='store_true', help='Print a per-claim breakdown, not just aggregate metrics.')
        parser.add_argument('--by-sector', action='store_true', help='Break precision/recall down by the corpus entries\' sector tag.')
        parser.add_argument('--by-type', action='store_true', help='Break precision/recall down by company_type (public/seed/series_ab/established_private/business_for_sale).')

    def handle(self, *args, **options):
        check_evidence = options['check_external_evidence']
        verbose = options['verbose']
        by_sector = options['by_sector']
        by_type = options['by_type']

        user, _ = User.objects.get_or_create(username='eval_claim_extraction_scratch_user', defaults={'email': 'eval@test.local'})

        tp = fp = fn = tn = 0
        numeric_checked = numeric_correct = 0
        misses, false_positives, numeric_mismatches, provenance_lines = [], [], [], []
        created_doc_ids = []
        coverage_reasons = Counter()
        resolution_cache = {}  # company_name -> (cik, reason), avoids re-resolving the same company across corpus entries
        sector_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0})
        type_stats = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0})

        for entry in CORPUS:
            doc = DocumentSource.objects.create(
                filename=f"{entry['id']}.txt", source_entity=entry['company_name'],
                uploaded_by=user, document_type='pitch_deck',
            )
            created_doc_ids.append(doc.id)

            pipeline = ZeldaIntelligencePipelineV2()
            chunk_result = pipeline._chunk_document(doc, entry['text'])
            if 'error' in chunk_result:
                self.stderr.write(self.style.ERROR(f"{entry['id']}: chunking failed — {chunk_result['error']}"))
                continue

            pipeline.used_chunks = set()
            analysis_result = pipeline._analyze_document(doc, entry['text'])
            if 'error' in analysis_result:
                self.stderr.write(self.style.ERROR(f"{entry['id']}: analysis failed — {analysis_result['error']}"))
                continue

            # In-memory only (see ZeldaIntelligencePipelineV2._smart_extract's
            # docstring) — which rule/keyword/sentence produced each
            # insight, keyed by IntelligenceInsight category (Revenue/
            # Team/etc, not the ClaimedDatapoint category name).
            provenance_by_category = {
                insight.category: getattr(insight, 'extraction_provenance', None)
                for insight in analysis_result['insights']
            }

            # extract_claims_from_insights normally also queues Truth
            # Delta verification (real Claude cost, and an unneeded
            # side effect for a pure extraction-quality eval) — patched
            # to a no-op for this run only.
            with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
                extract_claims_from_insights.run(doc.id)

            claims_by_category = {c.category: c for c in ClaimedDatapoint.objects.filter(document=doc)}

            resolved_cik, resolution_reason = None, None
            observed_categories = set()
            if check_evidence:
                from zelda_api.truth_delta_sources import SECFilingsIntegration, data_source_manager
                company_name = entry['company_name']
                if company_name not in resolution_cache:
                    resolution_cache[company_name] = SECFilingsIntegration().resolve_with_diagnostics(company_name)
                resolved_cik, resolution_reason = resolution_cache[company_name]

                if resolved_cik:
                    try:
                        data_source_manager.create_observed_datapoints(doc, company_name, domain=None)
                    except Exception as e:
                        self.stderr.write(self.style.WARNING(f"{entry['id']}: external evidence lookup failed — {e}"))
                observed_categories = set(ObservedDatapoint.objects.filter(document=doc).values_list('category', flat=True))

            sector = entry.get('sector', 'unspecified')
            company_type = entry.get('company_type', 'unspecified')

            for annotation in entry['annotations']:
                category = annotation['category']
                claim_category = CATEGORY_MAPPING[category]
                extracted = claims_by_category.get(claim_category) if claim_category else None

                if annotation['should_extract']:
                    if extracted:
                        tp += 1
                        sector_stats[sector]['tp'] += 1
                        type_stats[company_type]['tp'] += 1
                        if verbose:
                            provenance_lines.append(self._format_provenance(entry['id'], category, 'TP', provenance_by_category.get(category)))
                        if check_evidence:
                            # Skipped = nothing reasonable to verify (a product/data
                            # limitation, not a bug). Failed = verification should
                            # have been possible but didn't complete (an engineering
                            # defect worth investigating). Keeping these visually
                            # separate means "failed" trending to zero over time is
                            # a real engineering signal, uncontaminated by however
                            # many private companies happen to be in this run's mix.
                            if claim_category not in SEC_VERIFIABLE_CLAIM_CATEGORIES:
                                coverage_reasons[('skipped', 'unsupported_claim_type (no SEC data source for this category)')] += 1
                            elif claim_category in observed_categories:
                                coverage_reasons[('found', 'found')] += 1
                            elif resolution_reason:
                                if entry['is_real_public_company']:
                                    coverage_reasons[('failed', f'resolver_miss:{resolution_reason} (real company, should have resolved)')] += 1
                                else:
                                    coverage_reasons[('skipped', 'private_company (expected — not an SEC filer)')] += 1
                            else:
                                coverage_reasons[('failed', 'no_relevant_filing (company resolved, but no matching XBRL data)')] += 1
                        if annotation['expected_numeric'] is not None and extracted.claimed_value_numeric is not None:
                            numeric_checked += 1
                            expected = annotation['expected_numeric']
                            actual = extracted.claimed_value_numeric
                            if expected and abs(actual - expected) / abs(expected) <= 0.15:
                                numeric_correct += 1
                            else:
                                numeric_mismatches.append(f"{entry['id']} [{category}]: expected ~{expected:,.0f}, got {actual:,.0f}")
                    else:
                        fn += 1
                        sector_stats[sector]['fn'] += 1
                        type_stats[company_type]['fn'] += 1
                        misses.append(f"{entry['id']} [{category}]: {annotation['note']}")
                else:
                    if extracted:
                        fp += 1
                        sector_stats[sector]['fp'] += 1
                        type_stats[company_type]['fp'] += 1
                        false_positives.append(f"{entry['id']} [{category}]: extracted \"{extracted.claimed_value[:80]}\" — {annotation['note']}")
                        provenance_lines.append(self._format_provenance(entry['id'], category, 'FP', provenance_by_category.get(category)))
                    else:
                        tn += 1
                        sector_stats[sector]['tn'] += 1
                        type_stats[company_type]['tn'] += 1

        DocumentSource.objects.filter(id__in=created_doc_ids).delete()

        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        unsupported_rate = fp / (tp + fp) if (tp + fp) else None
        numeric_accuracy = numeric_correct / numeric_checked if numeric_checked else None

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"Evaluation corpus: {len(CORPUS)} documents, {len(ALL_CATEGORIES)} categories each ({len(CORPUS) * len(ALL_CATEGORIES)} annotations)"))
        self.stdout.write('')
        self.stdout.write(f"{'Metric':<28}{'Value':<12}Why it matters")
        self.stdout.write('-' * 90)
        self.stdout.write(f"{'Precision':<28}{self._pct(precision):<12}Are extracted claims actually supported by the document?")
        self.stdout.write(f"{'Recall':<28}{self._pct(recall):<12}How many supported claims are missed?")
        self.stdout.write(f"{'Unsupported claim rate':<28}{self._pct(unsupported_rate):<12}Should now approach zero.")
        if check_evidence:
            found_count = coverage_reasons[('found', 'found')]
            failed_total = sum(c for (bucket, _), c in coverage_reasons.items() if bucket == 'failed')
            sec_verifiable_total = found_count + failed_total
            coverage = found_count / sec_verifiable_total if sec_verifiable_total else None
            self.stdout.write(f"{'Verification coverage':<28}{self._pct(coverage):<12}Of claims verification SHOULD have worked for, how many did? (excludes skipped)")
        else:
            self.stdout.write(f"{'Verification coverage':<28}{'(skipped)':<12}Re-run with --check-external-evidence to compute")
        self.stdout.write('')
        self.stdout.write(f"Numeric accuracy (within 15% of annotated value, among true positives): {self._pct(numeric_accuracy)} ({numeric_correct}/{numeric_checked})")
        self.stdout.write('')
        self.stdout.write(f"Confusion counts — TP={tp}  FP={fp}  FN={fn}  TN={tn}")

        if check_evidence and coverage_reasons:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f"Verified ({found_count}):"))
            self.stdout.write(f"  {found_count:>4}  found")

            skipped_reasons = {reason: c for (bucket, reason), c in coverage_reasons.items() if bucket == 'skipped'}
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f"Skipped ({sum(skipped_reasons.values())}) — nothing reasonable to verify, not a bug:"))
            for reason, count in sorted(skipped_reasons.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"  {count:>4}  {reason}")

            failed_reasons = {reason: c for (bucket, reason), c in coverage_reasons.items() if bucket == 'failed'}
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f"Failed ({sum(failed_reasons.values())}) — verification should have been possible but didn't complete:"))
            if failed_reasons:
                for reason, count in sorted(failed_reasons.items(), key=lambda kv: -kv[1]):
                    self.stdout.write(f"  {count:>4}  {reason}")
            else:
                self.stdout.write("  (none)")

        if by_sector and sector_stats:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS("By sector:"))
            self.stdout.write(f"  {'Sector':<20}{'Precision':<12}{'Recall':<12}TP / FP / FN / TN")
            for sector in sorted(sector_stats):
                s = sector_stats[sector]
                sec_precision = s['tp'] / (s['tp'] + s['fp']) if (s['tp'] + s['fp']) else None
                sec_recall = s['tp'] / (s['tp'] + s['fn']) if (s['tp'] + s['fn']) else None
                self.stdout.write(
                    f"  {sector:<20}{self._pct(sec_precision):<12}{self._pct(sec_recall):<12}"
                    f"{s['tp']} / {s['fp']} / {s['fn']} / {s['tn']}"
                )

        if by_type and type_stats:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS("By company type — checks whether extraction is quietly overfit to fundraising-pitch-deck style prose:"))
            self.stdout.write(f"  {'Type':<22}{'Precision':<12}{'Recall':<12}TP / FP / FN / TN")
            for company_type in sorted(type_stats):
                s = type_stats[company_type]
                type_precision = s['tp'] / (s['tp'] + s['fp']) if (s['tp'] + s['fp']) else None
                type_recall = s['tp'] / (s['tp'] + s['fn']) if (s['tp'] + s['fn']) else None
                self.stdout.write(
                    f"  {company_type:<22}{self._pct(type_precision):<12}{self._pct(type_recall):<12}"
                    f"{s['tp']} / {s['fp']} / {s['fn']} / {s['tn']}"
                )

        if verbose or false_positives:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f"False positives ({len(false_positives)}) — extracted a claim the document doesn't support:"))
            for line in false_positives:
                self.stdout.write(f"  - {line}")

        if verbose or misses:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f"Missed claims ({len(misses)}) — document supports a claim that wasn't extracted:"))
            for line in misses:
                self.stdout.write(f"  - {line}")

        if verbose and numeric_mismatches:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f"Numeric mismatches ({len(numeric_mismatches)}) — extracted but value is off by >15%:"))
            for line in numeric_mismatches:
                self.stdout.write(f"  - {line}")

        if provenance_lines:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f"Extraction provenance ({len(provenance_lines)}) — which rule/keyword/sentence produced each claim below "
                f"{'(--verbose: all true positives' if verbose else '(false positives only'}, so a future regression can be "
                f"root-caused without re-deriving this by hand:"
            ))
            for line in provenance_lines:
                self.stdout.write(line)

    @staticmethod
    def _format_provenance(doc_id, category, outcome, provenance):
        if provenance is None:
            return f"  [{outcome}] {doc_id} [{category}]: (no provenance — claim came from ClaimedDatapoint numeric parsing, not an insight in this run)\n"
        keywords = ', '.join(provenance['matched_keywords']) or '(none — fallback path)'
        sentence = provenance['matched_sentence']
        sentence = (sentence[:150] + '…') if len(sentence) > 150 else sentence
        return (
            f"  [{outcome}] {doc_id} [{category}]\n"
            f"        Rule:             {provenance['rule']}\n"
            f"        Matched keyword:  {keywords}\n"
            f"        Matched sentence: \"{sentence}\"\n"
        )

    @staticmethod
    def _pct(value):
        return f"{value * 100:.1f}%" if value is not None else "N/A"
