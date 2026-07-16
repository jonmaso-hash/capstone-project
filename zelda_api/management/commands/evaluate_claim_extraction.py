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

Every DocumentSource this command creates is deleted at the end of the
run (cascade-deletes its chunks/insights/claims/observed-datapoints too),
so re-running this repeatedly never accumulates junk in the dev database.

Usage:
    python manage.py evaluate_claim_extraction
    python manage.py evaluate_claim_extraction --check-external-evidence
    python manage.py evaluate_claim_extraction --verbose
"""
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


class Command(BaseCommand):
    help = 'Score claim extraction against the manually annotated evaluation corpus (see evaluation_corpus.py)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-external-evidence', action='store_true',
            help='Also query SEC EDGAR (live, free, no key needed) per real-company document to compute verification coverage. Off by default to keep runs instant.',
        )
        parser.add_argument('--verbose', action='store_true', help='Print a per-claim breakdown, not just aggregate metrics.')

    def handle(self, *args, **options):
        check_evidence = options['check_external_evidence']
        verbose = options['verbose']

        user, _ = User.objects.get_or_create(username='eval_claim_extraction_scratch_user', defaults={'email': 'eval@test.local'})

        tp = fp = fn = tn = 0
        numeric_checked = numeric_correct = 0
        evidence_checked = evidence_found = 0
        misses, false_positives, numeric_mismatches = [], [], []
        created_doc_ids = []

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

            # extract_claims_from_insights normally also queues Truth
            # Delta verification (real Claude cost, and an unneeded
            # side effect for a pure extraction-quality eval) — patched
            # to a no-op for this run only.
            with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
                extract_claims_from_insights.run(doc.id)

            claims_by_category = {c.category: c for c in ClaimedDatapoint.objects.filter(document=doc)}

            if check_evidence and entry['is_real_public_company']:
                from zelda_api.truth_delta_sources import data_source_manager
                try:
                    data_source_manager.create_observed_datapoints(doc, entry['company_name'], domain=None)
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"{entry['id']}: external evidence lookup failed — {e}"))
            observed_categories = set(ObservedDatapoint.objects.filter(document=doc).values_list('category', flat=True))

            for annotation in entry['annotations']:
                category = annotation['category']
                claim_category = CATEGORY_MAPPING[category]
                extracted = claims_by_category.get(claim_category) if claim_category else None

                if annotation['should_extract']:
                    if extracted:
                        tp += 1
                        if check_evidence and entry['is_real_public_company']:
                            evidence_checked += 1
                            if claim_category in observed_categories:
                                evidence_found += 1
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
                        misses.append(f"{entry['id']} [{category}]: {annotation['note']}")
                else:
                    if extracted:
                        fp += 1
                        false_positives.append(f"{entry['id']} [{category}]: extracted \"{extracted.claimed_value[:80]}\" — {annotation['note']}")
                    else:
                        tn += 1

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
            coverage = evidence_found / evidence_checked if evidence_checked else None
            self.stdout.write(f"{'Verification coverage':<28}{self._pct(coverage):<12}How many extracted claims have external evidence available? (real companies only, SEC EDGAR)")
        else:
            self.stdout.write(f"{'Verification coverage':<28}{'(skipped)':<12}Re-run with --check-external-evidence to compute")
        self.stdout.write('')
        self.stdout.write(f"Numeric accuracy (within 15% of annotated value, among true positives): {self._pct(numeric_accuracy)} ({numeric_correct}/{numeric_checked})")
        self.stdout.write('')
        self.stdout.write(f"Confusion counts — TP={tp}  FP={fp}  FN={fn}  TN={tn}")

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

    @staticmethod
    def _pct(value):
        return f"{value * 100:.1f}%" if value is not None else "N/A"
