"""Reporting currency is explicit, retained in display, and gates comparisons."""
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse

from accounts.forms import ApplicationForm, InvestorForm, SellerForm, BuyerForm
from matchmaking.models import Application, InvestorApplication, SellerApplication, BuyerApplication
from matchmaking.tests import _mock_embedding_generation
from matchmaking.currencies import currencies_match
from matchmaking.templatetags.deal_display import money_display
from zelda_api.vector_models import DocumentSource
from zelda_api.truth_delta_models import ClaimedDatapoint
from zelda_api.profile_reconciliation import reconcile_profile_with_deck
from zelda_api.peer_benchmark import interlink_benchmark, safe_interlink_snapshot

User = get_user_model()


class ProfileCurrencyTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.counter = 0

    def profile(self, role='founder', currency='', **kwargs):
        self.counter += 1
        user = User.objects.create_user(f'currency_{self.counter}', password='x')
        common = dict(user=user, company_name=f'Company{self.counter}', email=f'c{self.counter}@test.invalid',
                      reporting_currency=currency)
        defaults = {
            'founder': (Application, dict(founder_name='F', description='We build grid software.', sector='SaaS', stage='Seed')),
            'investor': (InvestorApplication, dict(full_name='I', investment_focus='SaaS', investment_stage='Seed', investment_amount='100000-500000')),
            'seller': (SellerApplication, dict(seller_name='S', description='Operating software business', industry='SaaS')),
            'buyer': (BuyerApplication, dict(full_name='B', acquisition_thesis='Buy SaaS businesses', budget_min=100000, budget_max=500000)),
        }
        model, extra = defaults[role]
        extra.update(kwargs)
        return model.objects.create(**common, **extra)

    def test_each_role_starts_unknown_and_can_explicitly_save_currency(self):
        for role, form_type in [('founder', ApplicationForm), ('investor', InvestorForm), ('seller', SellerForm), ('buyer', BuyerForm)]:
            with self.subTest(role=role):
                profile = self.profile(role)
                self.assertEqual(profile.reporting_currency, '')
                data = {k: str(v) for k, v in model_to_dict(profile).items()
                        if k in form_type.Meta.fields and v is not None and k not in ('pitch_deck', 'pitch_video', 'cim_document')}
                data['reporting_currency'] = 'EUR'
                form = form_type(data=data, instance=profile)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.save().reporting_currency, 'EUR')
                data['reporting_currency'] = 'ZZZ'
                self.assertIn('reporting_currency', form_type(data=data, instance=profile).errors)

    def test_each_editor_renders_the_currency_selector(self):
        for role in ('founder', 'investor', 'seller', 'buyer'):
            with self.subTest(role=role):
                profile = self.profile(role, 'EUR')
                self.client.force_login(profile.user)
                response = self.client.get(reverse(f'usersettings:edit_{role}_profile'))
                self.assertContains(response, 'name="reporting_currency"')
                self.assertContains(response, '<option value="EUR" selected>EUR</option>', html=True)

    def test_unknown_currency_is_never_assumed_from_equal_numbers(self):
        left, right = self.profile(), self.profile(currency='USD')
        self.assertFalse(currencies_match(left, right))
        self.assertIn('currency unknown', money_display(1000000))
        self.assertEqual(money_display(1000000, 'EUR'), '1,000,000 EUR')

    def test_reconciliation_compares_only_explicit_matching_currency(self):
        profile = self.profile(currency='USD', prior_amount_raised=163000000)
        doc = DocumentSource.objects.create(uploaded_by=profile.user, filename='deck.pdf',
            source_entity=profile.company_name, document_type='pitch_deck')
        claim = ClaimedDatapoint.objects.create(document=doc, category='funding_raised',
            claimed_value='$23.1M', claimed_value_numeric=23100000)
        def row():
            return reconcile_profile_with_deck(doc, profile.user)[0]
        self.assertEqual(row().reason, 'deck_currency_unknown')
        claim.currency = 'EUR'; claim.save(update_fields=['currency'])
        self.assertEqual(row().reason, 'currency_mismatch')
        claim.currency = 'USD'; claim.save(update_fields=['currency'])
        self.assertEqual(row().status, 'differs')
        self.assertEqual(row().profile_display, '163,000,000 USD')
        self.assertEqual(row().deck_display, '23,100,000 USD')
        self.assertEqual(reconcile_profile_with_deck(doc, self.profile().user), [])

    def test_money_matching_abstains_for_unknown_or_mixed_currencies(self):
        from matchmaking.match_components import deal_size_signal
        from matchmaking.utils import passes_hard_filters
        seller = self.profile('seller', 'EUR', asking_price=200000)
        buyer = self.profile('buyer', 'USD')
        self.assertIsNone(deal_size_signal(seller, buyer).value)
        buyer.reporting_currency = 'EUR'
        self.assertEqual(deal_size_signal(seller, buyer).value, 100)
        buyer.reporting_currency = ''
        self.assertIsNone(deal_size_signal(seller, buyer).value)
        founder = self.profile(currency='EUR', raising_amount=100000,
            field_visibility={'raising_amount': 'PUBLIC'})
        investor = self.profile('investor', 'USD', ticket_size_min=200000)
        self.assertTrue(passes_hard_filters(founder, investor))
        investor.reporting_currency = 'EUR'
        self.assertFalse(passes_hard_filters(founder, investor))
        investor.reporting_currency = ''
        self.assertTrue(passes_hard_filters(founder, investor))

    def test_peer_money_aggregates_require_five_same_currency_contributors(self):
        subject = self.profile('seller', 'USD', annual_revenue=1500000)
        peers = [self.profile('seller', 'USD', annual_revenue=1000000,
            field_visibility={'annual_revenue': 'PUBLIC'}) for _ in range(5)]
        self.profile('seller', 'EUR', annual_revenue=999999999)
        self.profile('seller', '', annual_revenue=999999999)
        snapshot = interlink_benchmark(subject, 'seller')
        row = snapshot['site']['metrics']['annual_revenue']
        self.assertEqual((row['median'], row['peer_values_available'], row['currency']), (1000000, 5, 'USD'))
        self.assertEqual(safe_interlink_snapshot(snapshot, 'seller')['site']['metrics']['annual_revenue']['median'], 1000000)
        peers[0].reporting_currency = 'EUR'; peers[0].save(update_fields=['reporting_currency'])
        self.assertIsNone(safe_interlink_snapshot(snapshot, 'seller')['site']['metrics']['annual_revenue']['median'])
        self.assertIsNone(interlink_benchmark(subject, 'seller')['site']['metrics']['annual_revenue']['median'])
        subject.reporting_currency = ''
        self.assertIsNone(interlink_benchmark(subject, 'seller')['site']['metrics']['annual_revenue']['median'])

    def test_money_search_requires_an_explicit_currency(self):
        from matchmaking.models import FIELD_PUBLIC
        usd = self.profile(currency='USD', raising_amount=100000, field_visibility={'raising_amount': FIELD_PUBLIC})
        eur = self.profile(currency='EUR', raising_amount=100000, field_visibility={'raising_amount': FIELD_PUBLIC})
        self.client.force_login(usd.user)
        url = reverse('matchmaking:global_search')
        self.assertEqual(list(self.client.get(url, {'capital': '200000'}).context['results']), [])
        response = self.client.get(url, {'capital': '200000', 'currency': 'USD'})
        self.assertEqual([p.pk for p in response.context['results']], [usd.pk])

    def test_valuation_facts_do_not_confirm_equal_amounts_with_unknown_currency(self):
        from zelda_api.intelligence_pipeline import ZeldaIntelligencePipelineV2
        from zelda_api.vector_models import IntelligenceInsight
        profile = self.profile(currency='USD', current_revenue=500000)
        doc = DocumentSource.objects.create(uploaded_by=profile.user, filename='deck.pdf',
            source_entity=profile.company_name, document_type='business_valuation')
        insight = IntelligenceInsight.objects.create(document=doc, category='Revenue',
            insight_type='statement', insight_text='Current Revenue: $500K', confidence_score=90)
        pipeline = ZeldaIntelligencePipelineV2()
        facts = pipeline._build_structured_context(doc, doc.insights.all())
        self.assertEqual(facts['_provenance']['revenue']['status'], 'not_comparable')
        self.assertEqual(facts['_provenance']['revenue']['comparison_reason'], 'currency_unknown')
        insight.insight_text = 'Current Revenue: US$500K'; insight.save(update_fields=['insight_text'])
        facts = pipeline._build_structured_context(doc, doc.insights.all())
        self.assertEqual(facts['_provenance']['revenue']['status'], 'confirmed')

    def test_ask_zelda_does_not_guess_currency_from_model_output_or_a_dollar_sign(self):
        from unittest import mock
        profile = self.profile(currency='USD', raising_amount=100000,
            field_visibility={'raising_amount': 'PUBLIC'})
        self.profile(currency='EUR', raising_amount=100000, field_visibility={'raising_amount': 'PUBLIC'})
        self.client.force_login(profile.user)
        extracted = {'constraints': [{'field': 'raising_amount', 'qualifier': 'at_most',
                                      'value': 200000, 'currency': 'USD'}]}
        with mock.patch('zelda_api.intelligence_pipeline._call_claude_for_query_extraction', return_value=extracted):
            response = self.client.post(reverse('zelda_api:ask'), {'q': 'Founders raising under $200K'}, content_type='application/json')
            self.assertTrue(response.json()['requires_currency'])
            self.assertEqual(response.json()['results'], [])
            response = self.client.post(reverse('zelda_api:ask'), {'q': 'Founders raising under USD 200K'}, content_type='application/json')
            self.assertEqual([r['startup_name'] for r in response.json()['results']], [profile.company_name])
