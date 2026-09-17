"""
No charge for a failed analysis (D7).

An investor who confirms "Analyze with Zelda" is charged one analysis through
an AnalysisCreditCharge on the founder's document (zelda_api/quotas.py). An
owner's own document that ends in `error` has never counted against them, but
an investor's charge counted whatever happened to the document -- so an
analysis that failed after every retry still used up one of the investor's
three free analyses.

The rule, applied where credits are counted (so the monthly allowance, the
weekly cap, the "N analyses remaining" display and the 80% warning all agree):

    a charge whose document ended in `error` does not count.

No refund record, ledger or notification -- the charge simply stops counting,
exactly as an owner's failed document does. A document that later succeeds
(a staff requeue) counts again. Unreadable decks never create a charge at all
(D9), so they need nothing here.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from matchmaking.models import Application, InvestorApplication
from matchmaking.tests import _mock_embedding_generation
from zelda_api import quotas
from zelda_api.models import AnalysisCreditCharge
from zelda_api.vector_models import DocumentSource

User = get_user_model()

IN_FLIGHT_OR_DONE = ('ingested', 'chunking', 'chunked', 'embedding', 'embedded', 'analyzing', 'analyzed')


class _Charges(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.investor = User.objects.create_user('nc_investor', password='x')
        InvestorApplication.objects.create(
            user=self.investor, full_name='I', email='i@t.com', company_name='Harbor Capital',
            investment_focus='SaaS', investment_stage='Seed',
        )
        self.founders = []

    def _analysis(self, status='analyzed', days_ago=0):
        """One investor-paid analysis of a different founder's deck, as the confirm step records it."""
        n = len(self.founders)
        founder = User.objects.create_user(f'nc_founder_{n}', password='x')
        Application.objects.create(
            user=founder, company_name=f'Company {n}', founder_name='F', email=f'f{n}@t.com',
            description='test', sector='SaaS', stage='Seed',
        )
        self.founders.append(founder)
        doc = DocumentSource.objects.create(
            uploaded_by=founder, filename='deck.pdf', source_entity=f'Company {n}',
            document_type='pitch_deck', status=status, raw_text_full='Deck text.',
        )
        charge = AnalysisCreditCharge.objects.create(document=doc, user=self.investor, job_type='memo')
        if days_ago:
            moment = timezone.now() - timedelta(days=days_ago)
            AnalysisCreditCharge.objects.filter(pk=charge.pk).update(created_at=moment)
            DocumentSource.objects.filter(pk=doc.pk).update(created_at=moment)
        return doc

    def _set_status(self, doc, status):
        DocumentSource.objects.filter(pk=doc.pk).update(status=status)


class ChargeCountingTests(_Charges):

    def test_a_charge_counts_while_the_analysis_is_running_or_done(self):
        for status in IN_FLIGHT_OR_DONE:
            with self.subTest(status=status):
                AnalysisCreditCharge.objects.all().delete()
                self._analysis(status=status)
                self.assertEqual(quotas.credits_used(self.investor), 1)
                self.assertEqual(quotas.credits_used_this_week(self.investor), 1)

    def test_a_failed_analysis_does_not_count_against_the_investor(self):
        self._analysis(status='error')
        self.assertEqual(quotas.credits_used(self.investor), 0)
        self.assertEqual(quotas.credits_used_this_week(self.investor), 0)
        self.assertEqual(quotas.remaining_analyses(self.investor), quotas.credit_limit(self.investor))

    def test_at_the_limit_a_failed_analysis_gives_the_slot_back(self):
        docs = [self._analysis() for _ in range(quotas.FREE_CREDITS)]
        self.assertFalse(quotas.has_credits_for(self.investor, 'memo'))
        self._set_status(docs[0], 'error')
        self.assertTrue(quotas.has_credits_for(self.investor, 'memo'))
        self.assertEqual(quotas.remaining_analyses(self.investor), 1)

    def test_the_weekly_cap_follows_the_same_rule(self):
        docs = [self._analysis() for _ in range(quotas.weekly_credit_limit(self.investor))]
        self.assertEqual(quotas.remaining_weekly_analyses(self.investor), 0)
        self._set_status(docs[0], 'error')
        self.assertEqual(quotas.remaining_weekly_analyses(self.investor), 1)

    def test_the_nearing_limit_warning_ignores_failed_analyses(self):
        docs = [self._analysis() for _ in range(quotas.FREE_CREDITS)]
        self.assertTrue(quotas.usage_nearing_limit(self.investor))
        for doc in docs:
            self._set_status(doc, 'error')
        self.assertFalse(quotas.usage_nearing_limit(self.investor))

    def test_a_document_that_later_succeeds_counts_again(self):
        doc = self._analysis(status='error')
        self.assertEqual(quotas.credits_used(self.investor), 0)
        self._set_status(doc, 'analyzed')
        self.assertEqual(quotas.credits_used(self.investor), 1)

    def test_only_the_failed_one_stops_counting(self):
        self._analysis(status='analyzed')
        self._analysis(status='error')
        self._analysis(status='analyzing')
        self.assertEqual(quotas.credits_used(self.investor), 2)

    def test_old_charges_still_fall_out_of_the_window_as_before(self):
        self._analysis(status='analyzed', days_ago=quotas.CREDIT_WINDOW_DAYS + 1)
        self.assertEqual(quotas.credits_used(self.investor), 0)


class UnchangedRulesTests(_Charges):
    """Controls: the owner-side rules this mirrors are untouched."""

    def test_the_founder_is_never_charged_for_an_investor_paid_analysis(self):
        for status in ('analyzed', 'error'):
            with self.subTest(status=status):
                doc = self._analysis(status=status)
                self.assertEqual(quotas.credits_used(doc.uploaded_by), 0)

    def test_an_owners_failed_document_already_does_not_count(self):
        owner = User.objects.create_user('nc_owner', password='x')
        DocumentSource.objects.create(
            uploaded_by=owner, filename='mine.pdf', source_entity='Mine', document_type='pitch_deck', status='error',
        )
        self.assertEqual(quotas.credits_used(owner), 0)
        DocumentSource.objects.create(
            uploaded_by=owner, filename='mine2.pdf', source_entity='Mine', document_type='pitch_deck', status='analyzed',
        )
        self.assertEqual(quotas.credits_used(owner), 1)
