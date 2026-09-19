"""
A company can dispute a finding about itself, and the record survives.

Truth Delta publishes evidence states about named companies to other users.
`ClarificationRequest` already lets an investor ask the company to explain a
claim — but there was no way for the subject of a report to say "this finding is
wrong, here is why". A platform that publishes findings about businesses needs a
right of reply, and needs it to be auditable afterwards.

Two rules shape the design:

1. **A dispute never implies the company is right.** While open it reads
   "Disputed by the company — under review", and the evidence state itself does
   not move. Resolution distinguishes upheld, corrected, closed for insufficient
   basis, and withdrawn.
2. **Nothing is edited in place.** The dispute copies what the report said at the
   time it was raised, so re-running verification cannot erase what was
   originally reported. The chain is: finding → original state → dispute →
   submitted evidence → staff action → resolution, each with actor and time.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation

from .truth_delta_models import FindingDispute, TruthDeltaReport
from .vector_models import DocumentSource

User = get_user_model()

PER_CLAIM = [
    {'category': 'revenue', 'claimed': '$2.4M', 'observed': 'No external data found', 'assessment': 'n/a'},
    {'category': 'team_size', 'claimed': '12', 'observed': 'LinkedIn: 11 employees', 'assessment': 'close'},
]


class DisputeBase(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.owner = User.objects.create_user('fd_owner', password='x')
        Application.objects.create(
            user=self.owner, company_name='FDCo', founder_name='F', email='fd@t.test',
            description='d', sector='SaaS', stage='Seed',
        )
        self.investor_user = User.objects.create_user('fd_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='FDFund', email='fdi@t.test',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.staff = User.objects.create_user('fd_staff', password='x', is_staff=True)
        self.stranger = User.objects.create_user('fd_stranger', password='x')
        self.doc = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='deck.pdf', source_entity='FDCo',
            document_type='pitch_deck', status='analyzed', raw_text_full='FDCo text.',
        )
        self.report = TruthDeltaReport.objects.create(
            document=self.doc, overall_truth_score=70.0, credibility_risk='low', summary='Summary.',
            details={'claims': [{'category': r['category']} for r in PER_CLAIM], 'per_claim': PER_CLAIM},
        )
        self.url = reverse('zelda_api:dispute_finding', args=[self.doc.id, 'revenue'])

    def _dispute(self, user, **extra):
        self.client.force_login(user)
        payload = {'reason': 'Our audited statement shows this revenue.', **extra}
        return self.client.post(self.url, payload)


class OnlyTheSubjectCanDisputeTests(DisputeBase):

    def test_the_company_can_dispute_a_finding_about_itself(self):
        response = self._dispute(self.owner)
        self.assertEqual(response.status_code, 200)
        dispute = FindingDispute.objects.get(report=self.report, category='revenue')
        self.assertEqual(dispute.raised_by, self.owner)
        self.assertEqual(dispute.status, FindingDispute.Status.OPEN)

    def test_an_investor_cannot_dispute_someone_elses_finding(self):
        self.assertEqual(self._dispute(self.investor_user).status_code, 403)
        self.assertFalse(FindingDispute.objects.exists())

    def test_a_stranger_cannot_either(self):
        self.assertEqual(self._dispute(self.stranger).status_code, 403)
        self.assertFalse(FindingDispute.objects.exists())

    def test_a_reason_is_required(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, {'reason': '   '}).status_code, 400)
        self.assertFalse(FindingDispute.objects.exists())

    def test_the_same_finding_is_not_disputed_twice_while_one_is_open(self):
        self._dispute(self.owner)
        second = self._dispute(self.owner)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(FindingDispute.objects.count(), 1)


class TheDisputeRecordsWhatTheReportSaidTests(DisputeBase):

    def test_it_copies_the_evidence_state_and_wording_at_the_time(self):
        self._dispute(self.owner)
        dispute = FindingDispute.objects.get()
        self.assertEqual(dispute.original_evidence_state, 'no_data')
        self.assertEqual(dispute.original_observed_text, 'No external data found')

    def test_re_running_verification_does_not_erase_what_was_reported(self):
        self._dispute(self.owner)
        # The report is regenerated and the finding changes.
        self.report.details = {
            'claims': [{'category': 'revenue'}],
            'per_claim': [{'category': 'revenue', 'claimed': '$2.4M',
                           'observed': 'Audited statement: $2.4M', 'assessment': 'match'}],
        }
        self.report.save(update_fields=['details'])
        dispute = FindingDispute.objects.get()
        # The dispute still answers "what did it say when this was raised?"
        self.assertEqual(dispute.original_evidence_state, 'no_data')
        self.assertEqual(dispute.original_observed_text, 'No external data found')


class AnOpenDisputeIsVisibleWithoutChangingTheFindingTests(DisputeBase):

    def test_viewers_see_that_the_company_disputed_it(self):
        self._dispute(self.owner)
        self.client.force_login(self.investor_user)
        html = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id])).content.decode()
        self.assertIn('Disputed by the company', html)
        self.assertIn('under review', html)

    def test_the_evidence_state_itself_does_not_move(self):
        self._dispute(self.owner)
        # Still unverified: a dispute is a right of reply, not a re-verification.
        self.assertEqual(self.report.category_states()['revenue'], 'no_data')

    def test_a_resolved_dispute_no_longer_reads_as_under_review(self):
        self._dispute(self.owner)
        dispute = FindingDispute.objects.get()
        dispute.resolve(status=FindingDispute.Status.UPHELD, note='Checked again; no source found.', by=self.staff)
        self.client.force_login(self.investor_user)
        html = self.client.get(reverse('zelda_api:truth_delta_ui', args=[self.doc.id])).content.decode()
        self.assertNotIn('under review', html)


class StaffResolveItOnTheRecordTests(DisputeBase):

    def setUp(self):
        super().setUp()
        self._dispute(self.owner)
        self.dispute = FindingDispute.objects.get()

    def test_each_resolution_records_who_and_when(self):
        for status in (
            FindingDispute.Status.UPHELD,
            FindingDispute.Status.CORRECTED,
            FindingDispute.Status.CLOSED_INSUFFICIENT,
            FindingDispute.Status.WITHDRAWN,
        ):
            with self.subTest(status=status):
                self.dispute.resolve(status=status, note='Reviewed the supplied statement.', by=self.staff)
                self.dispute.refresh_from_db()
                self.assertEqual(self.dispute.status, status)
                self.assertEqual(self.dispute.resolved_by, self.staff)
                self.assertIsNotNone(self.dispute.resolved_at)

    def test_a_resolution_requires_a_note(self):
        with self.assertRaises(ValueError):
            self.dispute.resolve(status=FindingDispute.Status.UPHELD, note='  ', by=self.staff)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, FindingDispute.Status.OPEN)

    def test_resolving_never_rewrites_what_was_originally_reported(self):
        before = (self.dispute.original_evidence_state, self.dispute.original_observed_text, self.dispute.reason)
        self.dispute.resolve(status=FindingDispute.Status.CORRECTED, note='Statement supplied; finding updated.', by=self.staff)
        self.dispute.refresh_from_db()
        self.assertEqual(
            (self.dispute.original_evidence_state, self.dispute.original_observed_text, self.dispute.reason),
            before,
        )


class OpsResolutionIsAReviewedActionTests(DisputeBase):
    """
    Resolution lives in the ops dashboard, not the Django admin, because it
    decides what other users see. The invariant worth guarding: staff say
    whether a finding stands or must change — they never type an evidence
    state. Correcting hands off to the same pipeline the Verify button uses.
    """

    def setUp(self):
        super().setUp()
        self._dispute(self.owner)
        self.dispute = FindingDispute.objects.get()
        self.url = reverse('ops:resolve_finding_dispute', args=[self.dispute.id])
        self.client.force_login(self.staff)

    def test_the_queue_is_staff_only(self):
        self.client.force_login(self.investor_user)
        response = self.client.get(reverse('ops:finding_disputes'), follow=True)
        self.assertNotContains(response, 'Disputed findings')

    def test_the_queue_shows_the_immutable_record_beside_the_companys_words(self):
        html = self.client.get(reverse('ops:finding_disputes')).content.decode()
        self.assertIn('What the report said when this was raised', html)
        self.assertIn('No external data found', html)
        self.assertIn('Our audited statement shows this revenue.', html)

    def test_a_resolution_without_a_note_is_refused(self):
        self.client.post(self.url, {'action': 'uphold', 'resolution_note': '   '})
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, FindingDispute.Status.OPEN)

    def test_upholding_records_the_decision_and_re_runs_nothing(self):
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay') as verify:
            self.client.post(self.url, {'action': 'uphold', 'resolution_note': 'Searched again; no source.'})
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, FindingDispute.Status.UPHELD)
        self.assertEqual(self.dispute.resolved_by, self.staff)
        verify.assert_not_called()

    def test_correcting_hands_off_to_the_verification_pipeline(self):
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay') as verify:
            self.client.post(self.url, {'action': 'correct', 'resolution_note': 'Statement supplied; re-checking.'})
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, FindingDispute.Status.CORRECTED)
        verify.assert_called_once_with(self.doc.id)

    def test_staff_cannot_type_an_evidence_state(self):
        before = self.report.category_states()['revenue']
        with mock.patch('zelda_api.truth_delta_tasks.verify_document_truth_delta.delay'):
            self.client.post(self.url, {
                'action': 'uphold',
                'resolution_note': 'Reviewed.',
                # Anything resembling a state on this form is ignored — the
                # evidence state comes from the pipeline, never from a human.
                'original_evidence_state': 'verified',
                'evidence_state': 'verified',
                'category_state': 'verified',
            })
        self.report.refresh_from_db()
        self.dispute.refresh_from_db()
        self.assertEqual(self.report.category_states()['revenue'], before)
        self.assertEqual(self.dispute.original_evidence_state, 'no_data')

    def test_an_already_resolved_dispute_is_not_resolved_twice(self):
        self.client.post(self.url, {'action': 'uphold', 'resolution_note': 'First decision.'})
        self.client.post(self.url, {'action': 'withdraw', 'resolution_note': 'Second decision.'})
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, FindingDispute.Status.UPHELD)
        self.assertEqual(self.dispute.resolution_note, 'First decision.')

    def test_the_company_is_told_the_outcome(self):
        from notifications.models import Notification
        self.client.post(self.url, {'action': 'uphold', 'resolution_note': 'Reviewed.'})
        notification = Notification.objects.filter(recipient=self.owner).latest('id')
        self.assertIn('reviewed', notification.message.lower())


class TheDisclaimerAddressesTheReaderTests(TestCase):
    """
    One constant renders on every report surface, and the old wording said
    "Investors are solely responsible for conducting their own independent due
    diligence" — on reports read by founders, sellers and buyers too.
    """

    def test_it_says_do_not_rely_solely_on_it(self):
        from .disclaimers import DUE_DILIGENCE_DISCLAIMER
        self.assertIn('Do not rely solely on this report', DUE_DILIGENCE_DISCLAIMER)

    def test_it_names_every_kind_of_advice_it_is_not(self):
        from .disclaimers import DUE_DILIGENCE_DISCLAIMER
        for kind in ('financial', 'investment', 'legal', 'tax', 'accounting'):
            with self.subTest(kind=kind):
                self.assertIn(kind, DUE_DILIGENCE_DISCLAIMER)

    def test_it_addresses_the_reader_not_only_investors(self):
        from .disclaimers import DUE_DILIGENCE_DISCLAIMER
        self.assertIn('You are responsible', DUE_DILIGENCE_DISCLAIMER)
        self.assertNotIn('Investors are solely responsible', DUE_DILIGENCE_DISCLAIMER)
