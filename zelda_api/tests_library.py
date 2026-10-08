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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from matchmaking.models import Application, Connection, DataRoomDocument, DataRoomReportLink, InvestorApplication, InvestorInterestEvent
from matchmaking.data_room_quota import FREE_LIMIT_BYTES, PREMIUM_LIMIT_BYTES, try_save_report
from matchmaking.tests import _mock_embedding_generation
from billing.models import ZeldaOrder
from billing.fulfillment import reconcile_order
from zelda_api.models import AnalysisCreditCharge, LibraryHiddenItem
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
    IntelligenceMemo.objects.create(document=document, executive_summary='s', business_model_analysis='t')
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
        self.assertNotIn('profile_analytics_url', data)

    def test_library_pages_five_entries_across_sections_and_keeps_full_history_reachable(self):
        me, _ = _founder('lib_pages', 'MyCo')
        for n in range(12):
            DocumentSource.objects.create(uploaded_by=me, filename=f'deck-{n}.pdf',
                                          source_entity=f'Subject {n}', document_type='pitch_deck')
        self.client.force_login(me)
        pages = [self.client.get(URL, {'page': number}).json() for number in (1, 2, 3)]
        self.assertEqual([len(page['sections'][0]['documents']) for page in pages], [5, 5, 2])
        self.assertEqual([page['pagination']['page'] for page in pages], [1, 2, 3])
        self.assertEqual(pages[0]['pagination']['total'], 12)
        self.assertEqual(pages[0]['pagination']['pages'], 3)
        self.assertTrue(pages[0]['archive_url'].endswith('#zelda-reports'))
        self.assertNotIn('profile_analytics_url', pages[0])

    def test_pagination_counts_orders_and_documents_together(self):
        me, _ = _founder('lib_mixed', 'MyCo')
        for n in range(4):
            DocumentSource.objects.create(uploaded_by=me, filename=f'deck-{n}.pdf',
                                          source_entity=f'Deck {n}', document_type='pitch_deck')
        source = DocumentSource.objects.create(uploaded_by=me, filename='buy.pdf', source_entity='Bought',
                                                document_type='pitch_deck', is_product_input=True)
        for _ in range(3):
            ZeldaOrder.objects.create(user=me, source_document=source, product='intelligence_memo',
                                      reports=['intelligence_memo'], amount=199)
        self.client.force_login(me)
        first = self.client.get(URL).json()
        second = self.client.get(URL, {'page': 2}).json()
        first_count = len(first['purchases']) + sum(len(s.get('documents', [])) for s in first['sections'])
        second_count = len(second['purchases']) + sum(len(s.get('documents', [])) for s in second['sections'])
        self.assertEqual((first_count, second_count), (5, 2))

    def test_processing_deck_can_be_removed_without_deleting_its_evidence(self):
        me, _ = _founder('lib_qibby', 'Interlink Foundry')
        deck = DocumentSource.objects.create(
            uploaded_by=me, filename='qibby.pdf', source_entity='Qibby Saves LLC',
            document_type='pitch_deck', status='analyzing',
        )
        self.client.force_login(me)
        data = self.client.get(URL).json()
        self.assertEqual(data['sections'][0]['documents'][0]['status'], 'Processing')
        self.assertEqual(data['sections'][0]['documents'][0]['document_id'], deck.pk)

        dismiss = reverse('zelda_api:library_dismiss', args=['document', deck.pk])
        self.assertEqual(self.client.post(dismiss).json(), {'dismissed': True})
        self.assertEqual(self.client.post(dismiss).json(), {'dismissed': True})
        self.assertEqual(self.client.get(URL).json()['sections'][0]['documents'], [])
        self.assertTrue(DocumentSource.objects.filter(pk=deck.pk).exists())
        self.assertEqual(LibraryHiddenItem.objects.filter(user=me, item_type='document').count(), 1)

    def test_ingested_deck_is_not_labeled_as_processing(self):
        me, _ = _founder('lib_ingested', 'Interlink Foundry')
        DocumentSource.objects.create(uploaded_by=me, filename='qibby.pptx', source_entity='Qibby Saves LLC',
                                      document_type='pitch_deck', status='ingested')
        self.client.force_login(me)
        self.assertEqual(self.client.get(URL).json()['sections'][0]['documents'][0]['status'], 'Uploaded — not analyzed')

    def test_hiding_an_analyzed_deck_also_hides_its_report_buttons_in_library(self):
        me, _ = _founder('lib_hide_nav', 'MyCo')
        deck = _analyzed_deck(me, 'MyCo')
        self.client.force_login(me)
        self.assertIn('evidence', [r['key'] for r in self.client.get(URL).json()['sections'][0]['reports']])
        self.client.post(reverse('zelda_api:library_dismiss', args=['document', deck.pk]))
        report_keys = [r['key'] for r in self.client.get(URL).json()['sections'][0]['reports']]
        self.assertNotIn('evidence', report_keys)
        self.assertNotIn('analysis', report_keys)
        self.assertTrue(IntelligenceMemo.objects.filter(document=deck).exists())

    def test_awaiting_payment_order_can_be_removed_without_canceling_or_unlocking_it(self):
        me, _ = _founder('lib_buyer', 'BuyerCo')
        source = DocumentSource.objects.create(
            uploaded_by=me, filename='deck.pdf', source_entity='Tesla, Inc.',
            document_type='pitch_deck', is_product_input=True,
        )
        order = ZeldaOrder.objects.create(
            user=me, source_document=source, product='intelligence_memo',
            reports=['intelligence_memo'], amount=999, status='awaiting_payment',
        )
        self.client.force_login(me)
        self.assertEqual(self.client.get(URL).json()['purchases'][0]['order_id'], str(order.pk))
        dismiss = reverse('zelda_api:library_dismiss', args=['order', order.pk])
        self.assertEqual(self.client.post(dismiss).status_code, 200)
        self.assertEqual(self.client.get(URL).json()['purchases'], [])
        order.refresh_from_db()
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertTrue(DocumentSource.objects.filter(pk=source.pk).exists())

    def test_dismissal_is_private_and_cannot_hide_another_users_items(self):
        me, _ = _founder('lib_hide_me', 'MyCo')
        other, _ = _founder('lib_hide_other', 'OtherCo')
        deck = _analyzed_deck(other, 'OtherCo')
        self.client.force_login(me)
        url = reverse('zelda_api:library_dismiss', args=['document', deck.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.post(reverse('zelda_api:library_dismiss', args=['order', 'not-a-uuid'])).status_code, 404)
        self.assertEqual(LibraryHiddenItem.objects.count(), 0)
        self.client.force_login(other)
        self.assertEqual(self.client.get(URL).json()['sections'][0]['documents'][0]['document_id'], deck.pk)

    def test_dismiss_requires_authentication_and_session_csrf(self):
        owner, _ = _founder('lib_csrf', 'MyCo')
        deck = _analyzed_deck(owner, 'MyCo')
        url = reverse('zelda_api:library_dismiss', args=['document', deck.pk])
        self.assertIn(self.client.post(url).status_code, (401, 403))
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(owner)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        self.assertFalse(LibraryHiddenItem.objects.exists())

    def test_dismissed_valuation_and_recent_company_leave_original_records(self):
        me = User.objects.create_user('lib_hide_investor', password='x')
        InvestorApplication.objects.create(user=me, full_name='I', company_name='Fund', email='i@t.test',
                                           investment_focus='SaaS', investment_stage='Seed')
        _, founder = _founder('lib_hide_founder', 'RecentCo')
        InvestorInterestEvent.objects.create(investor=me, founder=founder, event_type='analyze')
        valuation = DocumentSource.objects.create(uploaded_by=me, filename='v.pdf', source_entity='ValueCo',
                                                  document_type='business_valuation', status='analyzed')
        self.client.force_login(me)
        self.assertEqual(self.client.post(reverse('zelda_api:library_dismiss', args=['valuation', valuation.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('zelda_api:library_dismiss', args=['company', founder.pk])).status_code, 200)
        sections = {section['key']: section for section in self.client.get(URL).json()['sections']}
        self.assertNotIn('valuations', sections)
        self.assertEqual(sections['recent_companies']['items'], [])
        self.assertTrue(DocumentSource.objects.filter(pk=valuation.pk).exists())
        self.assertTrue(InvestorInterestEvent.objects.filter(investor=me, founder=founder).exists())


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
        self.assertNotIn('profile_analytics_url', data)

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
        self.assertIn('zelda-library-dismiss', html)
        self.assertIn("method: 'POST', credentials: 'same-origin'", html)

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


class DataRoomReportArchiveTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.owner, self.founder = _founder('archive_owner', 'FoundryCo')
        self.source = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='input.pdf', source_entity='Tesla, Inc.',
            document_type='research', is_product_input=True, is_external_subject=True,
        )
        self.order = ZeldaOrder.objects.create(
            user=self.owner, source_document=self.source, product='intelligence_memo',
            reports=['intelligence_memo'], amount=199, status='ready', paid_at=timezone.now(),
        )
        self.room_url = reverse('matchmaking:data_room', args=[self.owner.username])

    def test_owner_can_search_paid_reports_even_after_removing_library_entry(self):
        self.assertTrue(try_save_report(self.owner, 'order', self.order.id, 'intelligence_memo', 1024))
        self.client.force_login(self.owner)
        self.client.post(reverse('zelda_api:library_dismiss', args=['order', self.order.id]))
        self.assertEqual(self.client.get(URL).json()['purchases'], [])
        response = self.client.get(self.room_url, {'q': 'Tesla'})
        self.assertContains(response, 'Zelda report archive')
        self.assertContains(response, 'Tesla, Inc.')
        self.assertContains(response, reverse('billing:zelda_report', args=[self.order.id, 'intelligence_memo']))
        self.assertContains(response, 'Memos')
        self.assertNotContains(self.client.get(self.room_url, {'q': 'NoSuchCompany'}), 'Tesla, Inc.')

    def test_new_memo_is_saved_to_archive_automatically(self):
        document = _analyzed_deck(self.owner, 'FoundryCo')
        self.assertTrue(DataRoomReportLink.objects.filter(
            founder=self.founder, source_kind='document', source_id=str(document.id), report_key='memo').exists())

    def test_fulfilled_purchase_saves_report_automatically(self):
        analysis = DocumentSource.objects.create(
            uploaded_by=self.owner, filename='analysis.pdf', source_entity='Tesla, Inc.',
            document_type='pitch_deck', status='analyzed', is_product_input=True,
        )
        self.order.status = 'processing'
        self.order.product = 'ic_memo'
        self.order.reports = ['ic_memo']
        self.order.analysis_document = analysis
        self.order.save(update_fields=['status', 'product', 'reports', 'analysis_document'])
        IntelligenceMemo.objects.create(document=analysis, executive_summary='A report', business_model_analysis='Evidence')
        reconcile_order(self.order)
        self.assertEqual(self.order.status, 'ready')
        self.assertTrue(DataRoomReportLink.objects.filter(
            founder=self.founder, source_kind='order', source_id=str(self.order.id), report_key='ic_memo').exists())

    def test_connected_investor_does_not_see_owner_only_report_index(self):
        self.assertTrue(try_save_report(self.owner, 'order', self.order.id, 'intelligence_memo', 1024))
        viewer = User.objects.create_user('archive_investor', password='x')
        investor = InvestorApplication.objects.create(user=viewer, full_name='I', company_name='Fund',
                                                       email='i@t.test', investment_focus='SaaS', investment_stage='Seed')
        Connection.objects.create(investor=investor, founder=self.founder, status='ACCEPTED', initiated_by='INVESTOR')
        self.client.force_login(viewer)
        response = self.client.get(self.room_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Zelda report archive')
        self.assertNotContains(response, 'Tesla, Inc.')

    def test_data_room_upload_categories_include_pitch_deck_and_memo(self):
        labels = dict(DataRoomDocument.CATEGORY_CHOICES)
        self.assertEqual(labels['PITCH_DECK'], 'Pitch Deck')
        self.assertEqual(labels['MEMO'], 'Memo')
        self.client.force_login(self.owner)
        response = self.client.get(self.room_url)
        self.assertContains(response, '<option value="PITCH_DECK">Pitch Deck</option>', html=True)

    def test_free_storage_limit_preserves_purchases_and_existing_archive_after_downgrade(self):
        self.assertEqual(FREE_LIMIT_BYTES, 500 * 1024 * 1024)
        self.assertEqual(PREMIUM_LIMIT_BYTES, 5 * 1024 * 1024 * 1024)
        self.founder.is_premium = True
        self.founder.save(update_fields=['is_premium'])
        DataRoomDocument.objects.create(founder=self.founder, file='data_room/old.pdf', label='Old file',
                                        size_bytes=FREE_LIMIT_BYTES)
        self.assertTrue(try_save_report(self.owner, 'order', self.order.id, 'intelligence_memo', 1024))
        self.founder.is_premium = False
        self.founder.save(update_fields=['is_premium'])

        new_order = ZeldaOrder.objects.create(user=self.owner, source_document=self.source,
                                              product='ic_memo', reports=['ic_memo'], amount=499,
                                              status='ready', paid_at=timezone.now())
        self.assertFalse(try_save_report(self.owner, 'order', new_order.id, 'ic_memo', 1024))
        self.assertEqual(DataRoomReportLink.objects.filter(founder=self.founder).count(), 1)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.room_url), 'Tesla, Inc.')
        self.assertEqual(len(self.client.get(URL).json()['purchases']), 2)

    def test_full_room_refuses_new_upload_without_affecting_existing_files(self):
        DataRoomDocument.objects.create(founder=self.founder, file='data_room/old.pdf', label='Old file',
                                        size_bytes=FREE_LIMIT_BYTES)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('matchmaking:data_room_upload', args=[self.owner.username]), {
            'category': 'PITCH_DECK', 'label': 'New deck',
            'file': SimpleUploadedFile('deck.pdf', b'a short file', content_type='application/pdf'),
        }, follow=True)
        self.assertContains(response, 'Data Room storage is full')
        self.assertEqual(DataRoomDocument.objects.filter(founder=self.founder).count(), 1)

    def test_new_paid_report_can_be_bought_when_room_is_full_and_stays_in_library(self):
        DataRoomDocument.objects.create(founder=self.founder, file='data_room/old.pdf', label='Old file',
                                        size_bytes=FREE_LIMIT_BYTES)
        self.assertFalse(try_save_report(self.owner, 'order', self.order.id, 'intelligence_memo', 1024))
        self.client.force_login(self.owner)
        self.assertEqual(len(self.client.get(URL).json()['purchases']), 1)
        self.assertNotContains(self.client.get(self.room_url), 'Tesla, Inc.')


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
