"""
The Zelda Library lists the signed-in user's existing analyses and reports.

What is pinned:
- only the requester's own documents and valuations are ever listed;
- an investor's list comes from what they actually did (interest events and paid
  analyses), newest first, and drops companies that went private;
- report links come from report_nav, so a locked report is named with a note and
  no link, and a deck staff hid for review offers no brief;
- the raw-document-ID developer tools are hidden from non-staff;
- global search's site-page links all resolve.

Runs in the blocking CI job (see .github/workflows/ci.yml).
"""
import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from matchmaking.models import Application, Connection, InvestorApplication, InvestorInterestEvent
from matchmaking.tests import _mock_embedding_generation
from zelda_api.models import AnalysisCreditCharge
from zelda_api.vector_models import DocumentSource, IntelligenceMemo

User = get_user_model()
URL = '/api/v1/zelda/library/'


def _founder(username, company, **extra):
    user = User.objects.create_user(username, password='x')
    application = Application.objects.create(
        user=user, company_name=company, founder_name='F', email=f'{username}@t.test',
        description='test', sector='SaaS', stage='Seed', **extra,
    )
    return user, application


def _analyzed_deck(owner, company, hidden=False):
    document = DocumentSource.objects.create(
        uploaded_by=owner, filename='deck.pdf', source_entity=company,
        document_type='pitch_deck', status='analyzed', is_hidden_by_staff=hidden,
    )
    IntelligenceMemo.objects.create(document=document, executive_summary='s', investment_thesis='t')
    return document


class LibraryAccessTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)

    def test_anonymous_visitors_are_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_a_founder_sees_only_their_own_documents_and_valuations(self):
        me, _ = _founder('lib_me', 'MyCo')
        other, _ = _founder('lib_other', 'OtherCo')
        mine = _analyzed_deck(me, 'MyCo')
        _analyzed_deck(other, 'OtherCo')
        DocumentSource.objects.create(uploaded_by=me, filename='v.pdf', source_entity='MyCo',
                                      document_type='business_valuation', status='analyzed')
        DocumentSource.objects.create(uploaded_by=other, filename='v.pdf', source_entity='OtherCo',
                                      document_type='business_valuation', status='analyzed')

        self.client.force_login(me)
        data = self.client.get(URL).json()
        sections = {s['key']: s for s in data['sections']}

        documents = sections['your_company']['documents']
        self.assertEqual([d['document_id'] for d in documents], [mine.id])
        self.assertTrue(documents[0]['can_open_brief'])
        self.assertEqual(documents[0]['status'], 'Ready')
        self.assertEqual([v['name'] for v in sections['valuations']['items']], ['MyCo'])
        self.assertNotIn('OtherCo', str(data))
        self.assertNotIn('recent_companies', sections)

    def test_a_founders_own_report_links_follow_report_nav(self):
        me, _ = _founder('lib_nav', 'NavCo')
        deck = _analyzed_deck(me, 'NavCo')
        self.client.force_login(me)
        reports = {r['key']: r for r in self.client.get(URL).json()['sections'][0]['reports']}

        self.assertEqual(reports['evidence']['url'], reverse('zelda_api:truth_delta_ui', args=[deck.id]))
        self.assertEqual(reports['analysis']['url'], reverse('zelda_api:ic_memo', args=[deck.id]))
        # The standalone overview is for investors; the owner sees it named, not linked.
        self.assertIsNone(reports['overview']['url'])
        self.assertTrue(reports['overview']['note'])

    def test_a_user_with_nothing_gets_no_sections_and_no_analytics_link(self):
        User.objects.create_user('lib_empty', password='x')
        self.client.force_login(User.objects.get(username='lib_empty'))
        data = self.client.get(URL).json()
        self.assertEqual(data['sections'], [])
        self.assertIsNone(data['profile_analytics_url'])


class InvestorRecentCompaniesTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)
        self.investor_user = User.objects.create_user('lib_investor', password='x')
        self.investor = InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.test',
            investment_focus='SaaS', investment_stage='Seed',
        )

    def _recent(self):
        self.client.force_login(self.investor_user)
        data = self.client.get(URL).json()
        return next(s for s in data['sections'] if s['key'] == 'recent_companies')['items'], data

    def test_viewed_and_paid_companies_are_listed_newest_first(self):
        viewed_user, viewed = _founder('lib_viewed', 'ViewedCo')
        paid_user, _ = _founder('lib_paid', 'PaidCo')
        _analyzed_deck(viewed_user, 'ViewedCo')
        paid_deck = _analyzed_deck(paid_user, 'PaidCo')

        event = InvestorInterestEvent.objects.create(investor=self.investor_user, founder=viewed, event_type='memo_view')
        InvestorInterestEvent.objects.filter(pk=event.pk).update(created_at=timezone.now() - timedelta(days=2))
        AnalysisCreditCharge.objects.create(document=paid_deck, user=self.investor_user, job_type='memo')

        items, data = self._recent()
        self.assertEqual([i['company'] for i in items], ['PaidCo', 'ViewedCo'])
        self.assertEqual(items[0]['activity'], 'You ran a Zelda analysis')
        self.assertEqual(items[1]['activity'], 'You opened its Zelda brief')
        self.assertEqual(data['profile_analytics_url'],
                         reverse('accounts:profile_analysis', kwargs={'username': 'lib_investor'}))

    def test_a_company_that_went_private_drops_out(self):
        _, private = _founder('lib_private', 'PrivateCo', is_private=True)
        InvestorInterestEvent.objects.create(investor=self.investor_user, founder=private, event_type='analyze')
        items, _ = self._recent()
        self.assertEqual(items, [])

    def test_the_ic_memo_is_named_but_locked_without_an_accepted_connection(self):
        founder_user, founder = _founder('lib_locked', 'LockedCo')
        _analyzed_deck(founder_user, 'LockedCo')
        InvestorInterestEvent.objects.create(investor=self.investor_user, founder=founder, event_type='analyze')

        items, _ = self._recent()
        analysis = next(r for r in items[0]['reports'] if r['key'] == 'analysis')
        self.assertIsNone(analysis['url'])
        self.assertTrue(analysis['note'])

        Connection.objects.create(investor=self.investor, founder=founder, status='ACCEPTED', initiated_by='INVESTOR')
        items, _ = self._recent()
        analysis = next(r for r in items[0]['reports'] if r['key'] == 'analysis')
        self.assertTrue(analysis['url'])

    def test_a_deck_hidden_for_review_offers_no_brief_or_evidence_link(self):
        founder_user, founder = _founder('lib_hidden', 'HiddenCo')
        _analyzed_deck(founder_user, 'HiddenCo', hidden=True)
        InvestorInterestEvent.objects.create(investor=self.investor_user, founder=founder, event_type='truth_delta_view')

        items, _ = self._recent()
        self.assertIsNone(items[0]['brief_document_id'])
        self.assertNotIn('evidence', [r['key'] for r in items[0]['reports'] if r['url']])

    def test_another_investors_activity_never_appears(self):
        other = User.objects.create_user('lib_other_investor', password='x')
        InvestorApplication.objects.create(user=other, full_name='O', company_name='OtherFund', email='o@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        _, founder = _founder('lib_theirs', 'TheirsCo')
        InvestorInterestEvent.objects.create(investor=other, founder=founder, event_type='analyze')
        items, _ = self._recent()
        self.assertEqual(items, [])


class LibraryPanelTests(TestCase):

    def setUp(self):
        _mock_embedding_generation(self)

    def _panel(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('billing:billing_page')).content.decode()

    def test_every_signed_in_user_gets_the_library_tab(self):
        html = self._panel(User.objects.create_user('lib_panel', password='x'))
        self.assertIn('data-tab="library"', html)
        self.assertIn('id="tab-library"', html)

    def test_the_raw_document_id_tools_are_hidden_from_non_staff(self):
        html = self._panel(User.objects.create_user('lib_member', password='x'))
        self.assertRegex(html, r'class="zelda-card p-4 d-none" id="vector-search-card"')
        self.assertIn('#tab-memo .zelda-card > div { display: none !important; }', html)
        self.assertIn('id="memo-library-hint"', html)
        # Still in the page: the analyze flow writes to and reads from these.
        self.assertIn('id="memo-doc-id"', html)
        self.assertIn('id="vector-search-form"', html)

    def test_staff_keep_the_developer_tools(self):
        html = self._panel(User.objects.create_user('lib_staff', password='x', is_staff=True))
        self.assertRegex(html, r'class="zelda-card p-4" id="vector-search-card"')
        self.assertNotIn('id="memo-library-hint"', html)


class GlobalSearchPageLinkTests(TestCase):

    def test_every_site_page_global_search_can_suggest_resolves(self):
        source = (Path(settings.BASE_DIR) / 'zelda_api' / 'views.py').read_text(encoding='utf-8')
        block = re.search(r'template_route_map = \{(.*?)\}', source, re.S).group(1)
        urls = re.findall(r"\('[^']+', '(/[^']*)'\)", block)
        self.assertGreaterEqual(len(urls), 8)
        unresolved = []
        for url in urls:
            try:
                resolve(url)
            except Resolver404:
                unresolved.append(url)
        self.assertEqual(unresolved, [])
