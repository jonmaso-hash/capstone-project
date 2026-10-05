"""
A profile revenue figure carries its period (A, before deck-period extraction).

Application.current_revenue had no period, so $100K could be monthly or
annual and nothing could be compared with it. revenue_period and
revenue_as_of record what the founder says it is.

    THE FORM ASKS. A positive revenue needs a period. Zero needs none. No
    revenue clears both, so they never describe nothing.

    NOTHING IS INFERRED. Existing rows stay unknown; no period is guessed.

    A PATH THAT DOES NOT ASK CANNOT LEAVE A STALE PERIOD. The dashboard
    sliders and the upload API write the amount only. If they change it, the
    old period no longer describes it and becomes unknown. If they do not,
    it stands -- the paired control, so "always clear" cannot pass.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse

from accounts.forms import ApplicationForm
from matchmaking.models import Application

User = get_user_model()


class RevenuePeriodFixture(TestCase):

    def setUp(self):
        from matchmaking.tests import _mock_embedding_generation
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('rp_founder', password='x')
        self.app = Application.objects.create(
            user=self.user, company_name='Northwind Grid', founder_name='F', email='f@t.test',
            description='We build grid software.', sector='SaaS', stage='Seed', raising_amount=500_000)

    def form(self, **overrides):
        # Submitted form data is strings; the comma-stripping widget relies on it.
        data = {k: str(v) for k, v in model_to_dict(self.app).items()
                if k in ApplicationForm.Meta.fields and k not in ('pitch_deck', 'pitch_video') and v is not None}
        data.update(overrides)
        return ApplicationForm(data=data, instance=self.app)


class TheFormAsksTests(RevenuePeriodFixture):

    def test_positive_revenue_without_a_period_is_refused(self):
        form = self.form(current_revenue='120000', revenue_period='')
        self.assertFalse(form.is_valid())
        self.assertIn('revenue_period', form.errors)

    def test_positive_revenue_with_a_period_is_accepted(self):
        """Paired control: the rule must not refuse everything."""
        form = self.form(current_revenue='120000', revenue_period='ttm', revenue_as_of='2026-06-30')
        self.assertTrue(form.is_valid(), form.errors)
        app = form.save()
        self.assertEqual((app.revenue_period, app.revenue_as_of), ('ttm', date(2026, 6, 30)))

    def test_zero_revenue_needs_no_period(self):
        self.assertTrue(self.form(current_revenue='0', revenue_period='').is_valid())

    def test_no_revenue_clears_period_and_date(self):
        Application.objects.filter(pk=self.app.pk).update(
            current_revenue=Decimal('5000'), revenue_period='monthly', revenue_as_of=date(2026, 1, 1))
        self.app.refresh_from_db()
        form = self.form(current_revenue='', revenue_period='monthly', revenue_as_of='2026-01-01')
        self.assertTrue(form.is_valid(), form.errors)
        app = form.save()
        self.assertEqual((app.revenue_period, app.revenue_as_of), ('', None))

    def test_the_edit_page_renders_the_period_field(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('usersettings:edit_founder_profile')).content.decode()
        self.assertIn('name="revenue_period"', html)
        self.assertIn('name="revenue_as_of"', html)


class NothingIsInferredTests(RevenuePeriodFixture):

    def test_an_existing_figure_has_no_period(self):
        Application.objects.filter(pk=self.app.pk).update(current_revenue=Decimal('120000'))
        self.app.refresh_from_db()
        self.assertEqual((self.app.revenue_period, self.app.revenue_as_of), ('', None))


class APathThatDoesNotAskTests(RevenuePeriodFixture):

    def setUp(self):
        super().setUp()
        Application.objects.filter(pk=self.app.pk).update(
            current_revenue=Decimal('120000'), revenue_period='ttm', revenue_as_of=date(2026, 6, 30))
        self.app.refresh_from_db()

    def test_a_changed_amount_clears_the_period(self):
        self.app.set_current_revenue('90000')
        self.assertEqual((self.app.revenue_period, self.app.revenue_as_of), ('', None))
        self.assertEqual(self.app.current_revenue, '90000')

    def test_an_unchanged_amount_keeps_the_period(self):
        self.app.set_current_revenue('120000')
        self.assertEqual((self.app.revenue_period, self.app.revenue_as_of), ('ttm', date(2026, 6, 30)))

    def test_clearing_the_amount_clears_the_period(self):
        self.app.set_current_revenue(None)
        self.assertEqual(self.app.revenue_period, '')

    def test_the_dashboard_sliders_clear_a_stale_period(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:update_criteria'), {'revenue': '90000', 'burn': '10000', 'team': '4'})
        self.app.refresh_from_db()
        self.assertEqual(self.app.current_revenue, Decimal('90000'), 'the slider did not write, so this proves nothing')
        self.assertEqual(self.app.revenue_period, '')

    def test_the_dashboard_sliders_keep_a_period_when_revenue_is_unchanged(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:update_criteria'), {'revenue': '120000', 'burn': '10000', 'team': '4'})
        self.app.refresh_from_db()
        self.assertEqual(self.app.revenue_period, 'ttm')
