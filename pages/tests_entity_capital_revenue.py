"""
Entity Integrity: capital and revenue evidence from SEC filings (PR C).

EDGAR data -> normalized financing events -> Entity Integrity rows.

Financing history (one row per financing event, then one total):
- Form D amendments point to the filing just before them
  (newOrAmendment/previousAccessionNumber), and every amendment restates the
  whole offering. An offering's amount sold is therefore the newest filing in
  its chain -- amendments are never added together.
- Separate offerings are added into a fundraising total, except pooled-fund
  offerings, business combinations, and offerings whose filer attached a
  clarification of what the sales amounts mean (those are shown, not counted).
- The total is always Public record: Form D is not a complete record of a
  company's capital (SAFEs, loans and grants may not appear), and only the
  recent filings on the SEC company record are read.

Revenue (one row):
- The newest Form D's revenue bracket covers the issuer's most recently
  completed fiscal year. Only a seller's annual revenue -- a figure whose
  period is explicit -- can be Doesn't match, and only against a Form D filed
  within the last 12 months. A founder's "current revenue" has no stated
  period, so it is Public record next to the bracket.
- Decline to Disclose, Not Applicable, and a fund's net asset value range are
  Not applicable; a net asset value range is never read as revenue.
- A company that files annual reports uses the existing 10-K revenue
  extractor, as Public record.

Fixture values come from real filings: CMS Apollo Holdings LP (a five-filing
amendment chain whose amount sold carries a clarification), DiversyFund, Inc.
($25,000 sold, then $1,000,000 in its amendment), IDA Ventures VII LLC (a
venture fund), Storri Labs Opportunities Fund I, LP (net asset value range),
GuideBox Inc. and Heat Safety Solutions (revenue brackets). Nothing here
reaches the network.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from matchmaking.models import Application, SellerApplication
from matchmaking.tests import _mock_embedding_generation
from pages.tests_entity_sec_form_d import (
    CIK, COMPANY_SEARCH_ONE, SEARCH_ONE_FILER, _Response, _patched_sec,
)

User = get_user_model()

CMS_CLARIFICATION = (
    'The Total Amount Sold above is the per-unit amount that would need to be distributed to existing equity '
    'holders before the securities in this offering would be eligible to receive any distributions. '
    '(continued in item 15)'
)


def _days_ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def form_d_xml(*, previous=None, first_sale='2025-07-28', offering='1000000', sold='25000', remaining='975000',
               investors='1', securities=('isDebtType',), other_description=None, industry='Other Real Estate',
               fund_type=None, revenue='Decline to Disclose', net_asset_value=None, business_combination=False,
               clarification=''):
    """A Form D primary_doc.xml with real EDGAR tag names, including the issuer's address and phone."""
    amendment = (f'<isAmendment>true</isAmendment><previousAccessionNumber>{previous}</previousAccessionNumber>'
                 if previous else '<isAmendment>false</isAmendment>')
    fund = (f'<investmentFundInfo><investmentFundType>{fund_type}</investmentFundType><is40Act>false</is40Act>'
            '</investmentFundInfo>' if fund_type else '')
    size = (f'<aggregateNetAssetValueRange>{net_asset_value}</aggregateNetAssetValueRange>' if net_asset_value
            else f'<revenueRange>{revenue}</revenueRange>')
    types = ''.join(f'<{name}>true</{name}>' for name in securities)
    if other_description:
        types += f'<descriptionOfOtherType>{other_description}</descriptionOfOtherType>'
    return f"""<?xml version="1.0"?>
<edgarSubmission>
    <schemaVersion>X0708</schemaVersion>
    <submissionType>{'D/A' if previous else 'D'}</submissionType>
    <primaryIssuer>
        <cik>{CIK}</cik>
        <entityName>Akil-Abree Consulting, LLC</entityName>
        <issuerAddress><street1>746 W. SUNSET DRIVE</street1><city>GLENWOOD</city><zipCode>60425</zipCode></issuerAddress>
        <issuerPhoneNumber>872-222-6287</issuerPhoneNumber>
        <jurisdictionOfInc>ILLINOIS</jurisdictionOfInc>
        <entityType>Limited Liability Company</entityType>
        <yearOfInc><withinFiveYears>true</withinFiveYears><value>2021</value></yearOfInc>
    </primaryIssuer>
    <relatedPersonsList>
        <relatedPersonInfo>
            <relatedPersonName><firstName>David</firstName><lastName>Lockman</lastName></relatedPersonName>
            <relatedPersonRelationshipList><relationship>Executive Officer</relationship></relatedPersonRelationshipList>
        </relatedPersonInfo>
    </relatedPersonsList>
    <offeringData>
        <industryGroup><industryGroupType>{industry}</industryGroupType>{fund}</industryGroup>
        <issuerSize>{size}</issuerSize>
        <federalExemptionsExclusions><item>06b</item></federalExemptionsExclusions>
        <typeOfFiling>
            <newOrAmendment>{amendment}</newOrAmendment>
            <dateOfFirstSale><value>{first_sale}</value></dateOfFirstSale>
        </typeOfFiling>
        <durationOfOffering><moreThanOneYear>true</moreThanOneYear></durationOfOffering>
        <typesOfSecuritiesOffered>{types}</typesOfSecuritiesOffered>
        <businessCombinationTransaction>
            <isBusinessCombinationTransaction>{'true' if business_combination else 'false'}</isBusinessCombinationTransaction>
            <clarificationOfResponse></clarificationOfResponse>
        </businessCombinationTransaction>
        <minimumInvestmentAccepted>25000</minimumInvestmentAccepted>
        <offeringSalesAmounts>
            <totalOfferingAmount>{offering}</totalOfferingAmount>
            <totalAmountSold>{sold}</totalAmountSold>
            <totalRemaining>{remaining}</totalRemaining>
            <clarificationOfResponse>{clarification}</clarificationOfResponse>
        </offeringSalesAmounts>
        <investors>
            <hasNonAccreditedInvestors>false</hasNonAccreditedInvestors>
            <totalNumberAlreadyInvested>{investors}</totalNumberAlreadyInvested>
        </investors>
        <useOfProceeds><grossProceedsUsed><dollarAmount>0</dollarAmount></grossProceedsUsed></useOfProceeds>
    </offeringData>
</edgarSubmission>
"""


def cms_apollo_filing(sold, investors, previous=None):
    return form_d_xml(
        previous=previous, first_sale='2022-03-01', offering='Indefinite', sold=sold, remaining='Indefinite',
        investors=investors, securities=('isEquityType', 'isOtherType'), other_description='Profits Interests',
        industry='Other', clarification=CMS_CLARIFICATION,
    )


# The real CMS Apollo Holdings LP chain, newest first: each amendment names the filing before it.
CMS_CHAIN = [
    ('0001936701-26-000003', '2026-09-15', 'D/A', cms_apollo_filing('25541548', '12', previous='0001936701-25-000001')),
    ('0001936701-25-000001', '2025-09-09', 'D/A', cms_apollo_filing('25541548', '12', previous='0001591852-24-000001')),
    ('0001591852-24-000001', '2024-09-04', 'D/A', cms_apollo_filing('24142798', '12', previous='0001936701-23-000001')),
    ('0001936701-23-000001', '2023-08-01', 'D/A', cms_apollo_filing('22553036', '11', previous='0001936701-22-000002')),
    ('0001936701-22-000002', '2022-08-16', 'D', cms_apollo_filing('8885405', '6')),
]

# The real DiversyFund, Inc. offering: $25,000 sold, then $1,000,000 in the amendment.
DIVERSY_CHAIN = [
    ('0001716191-26-000003', '2026-09-15', 'D/A', form_d_xml(
        previous='0001716191-25-000003', sold='1000000', remaining='0', investors='20')),
    ('0001716191-25-000003', '2025-08-11', 'D', form_d_xml(sold='25000', investors='1')),
]

# A second, separate offering (values from GuideBox Inc.'s Form D).
GUIDEBOX_OFFERING = ('0001625786-14-000001', '2014-11-21', 'D', form_d_xml(
    first_sale='2014-11-14', offering='500000', sold='125000', remaining='375000', industry='Computers',
    revenue='$1 - $1,000,000'))

# IDA Ventures VII LLC: a venture fund's offering.
VENTURE_FUND_OFFERING = ('0002148541-26-000001', '2026-06-01', 'D', form_d_xml(
    first_sale='2026-05-20', offering='2185000', sold='2185000', remaining='0', investors='28',
    securities=('isPooledInvestmentFundType',), industry='Pooled Investment Fund', fund_type='Venture Capital Fund'))

# Storri Labs Opportunities Fund I, LP: reports a net asset value range instead of revenue.
NET_ASSET_VALUE_FILING = form_d_xml(
    previous='0002081829-25-000004', first_sale='2021-09-01', offering='Indefinite', sold='5198797',
    remaining='Indefinite', investors='7', securities=('isPooledInvestmentFundType',),
    industry='Pooled Investment Fund', fund_type='Hedge Fund', net_asset_value='Decline to Disclose')


def company_record(filings):
    """An SEC submissions record whose recent filings are [(accession, filing date, form, ...)]."""
    return {
        'cik': CIK, 'name': 'Akil-Abree Consulting, LLC', 'stateOfIncorporation': 'IL',
        'filings': {'recent': {
            'accessionNumber': [f[0] for f in filings], 'filingDate': [f[1] for f in filings],
            'form': [f[2] for f in filings], 'primaryDocument': ['xslFormDX01/primary_doc.xml'] * len(filings),
        }, 'files': []},
    }


ANNUAL_REPORT_FACTS = {
    'facts': {'us-gaap': {'Revenues': {'units': {'USD': [
        {'val': 900_000_000, 'end': '2023-12-31', 'form': '10-K', 'fy': 2023},
        {'val': 1_100_000_000, 'end': '2024-12-31', 'form': '10-K', 'fy': 2024},
        {'val': 300_000_000, 'end': '2025-03-31', 'form': '10-Q', 'fy': 2025},
    ]}}}},
}


class _Filings:
    """Answers SEC requests for one filer from fixtures and records what was asked."""

    def __init__(self, filings, facts=None, fail_accession=None):
        self.record = company_record(filings)
        self.documents = {accession.replace('-', ''): xml for accession, _date, _form, *rest in filings
                          for xml in rest[:1]}
        self.facts, self.fail_accession = facts, fail_accession
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None, **kwargs):
        self.calls.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {}), 'timeout': timeout})
        if 'browse-edgar' in url:
            return _Response(text=COMPANY_SEARCH_ONE)
        if 'efts.sec.gov' in url:
            return _Response(payload=SEARCH_ONE_FILER)
        if 'data.sec.gov/submissions' in url:
            return _Response(payload=self.record)
        if 'api/xbrl/companyfacts' in url:
            return _Response(payload=self.facts) if self.facts else _Response(503, text='Service Unavailable')
        if url.endswith('primary_doc.xml'):
            if self.fail_accession and self.fail_accession.replace('-', '') in url:
                return _Response(503, text='Service Unavailable')
            for digits, xml in self.documents.items():
                if f'/{digits}/' in url:
                    return _Response(text=xml)
        return _Response(404, text='not found')

    def form_d_fetches(self):
        return [call['url'] for call in self.calls if call['url'].endswith('primary_doc.xml')]


def _parse(xml):
    from zelda_api.sec_identity import parse_form_d
    return parse_form_d(xml)


def _events(filings):
    from zelda_api.sec_financing import financing_events
    return financing_events([(accession, filing_date, _parse(xml)) for accession, filing_date, _form, xml in filings])


# --------------------------------------------------------------------------
# Raw facts: what a Form D says about its offering
# --------------------------------------------------------------------------

class FormDOfferingParsingTests(SimpleTestCase):

    def test_an_amendment_names_the_filing_before_it(self):
        form_d = _parse(CMS_CHAIN[0][3])
        self.assertTrue(form_d.is_amendment)
        self.assertEqual(form_d.previous_accession, '0001936701-25-000001')
        original = _parse(CMS_CHAIN[-1][3])
        self.assertFalse(original.is_amendment)
        self.assertIsNone(original.previous_accession)

    def test_the_offering_amounts_investors_and_securities_are_read(self):
        form_d = _parse(CMS_CHAIN[0][3])
        self.assertEqual(form_d.date_of_first_sale, '2022-03-01')
        self.assertEqual(form_d.total_amount_sold, 25541548)
        self.assertIsNone(form_d.total_offering_amount)
        self.assertTrue(form_d.offering_amount_indefinite)
        self.assertEqual(form_d.investor_count, 12)
        self.assertEqual(form_d.security_types, ['Equity', 'Other: Profits Interests'])
        self.assertFalse(form_d.is_business_combination)
        self.assertIn('per-unit amount', form_d.sales_clarification)

    def test_a_numeric_offering_amount_and_a_debt_offering_are_read(self):
        form_d = _parse(DIVERSY_CHAIN[0][3])
        self.assertEqual(form_d.total_offering_amount, 1000000)
        self.assertFalse(form_d.offering_amount_indefinite)
        self.assertEqual(form_d.total_amount_sold, 1000000)
        self.assertEqual(form_d.security_types, ['Debt'])
        self.assertIsNone(form_d.sales_clarification)

    def test_a_fund_and_its_issuer_size_are_read_without_mixing_net_asset_value_into_revenue(self):
        venture = _parse(VENTURE_FUND_OFFERING[3])
        self.assertEqual(venture.industry_group, 'Pooled Investment Fund')
        self.assertEqual(venture.fund_type, 'Venture Capital Fund')
        self.assertEqual(venture.security_types, ['Pooled investment fund interests'])
        self.assertEqual(venture.revenue_range, 'Decline to Disclose')

        hedge = _parse(NET_ASSET_VALUE_FILING)
        self.assertIsNone(hedge.revenue_range)
        self.assertEqual(hedge.net_asset_value_range, 'Decline to Disclose')

        bracket = _parse(GUIDEBOX_OFFERING[3])
        self.assertEqual(bracket.revenue_range, '$1 - $1,000,000')
        self.assertIsNone(bracket.net_asset_value_range)

    def test_a_business_combination_is_read(self):
        self.assertTrue(_parse(form_d_xml(business_combination=True)).is_business_combination)

    def test_form_d_filings_lists_every_d_and_amendment_newest_first(self):
        from zelda_api.sec_identity import form_d_filings
        record = company_record([
            ('a-10k', '2026-01-01', '10-K'), ('a-d-old', '2023-05-01', 'D'),
            ('a-d-amend', '2025-02-01', 'D/A'), ('a-8k', '2026-03-01', '8-K'),
        ])
        self.assertEqual(form_d_filings(record), [
            {'accession': 'a-d-amend', 'filing_date': '2025-02-01', 'form': 'D/A'},
            {'accession': 'a-d-old', 'filing_date': '2023-05-01', 'form': 'D'},
        ])


# --------------------------------------------------------------------------
# Normalized financing events
# --------------------------------------------------------------------------

class FinancingEventTests(SimpleTestCase):

    def test_a_five_filing_amendment_chain_is_one_financing_event_described_by_its_newest_filing(self):
        events = _events(CMS_CHAIN)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.accession, '0001936701-26-000003')
        self.assertEqual(event.amount_sold, 25541548)
        self.assertEqual(event.first_filed, '2022-08-16')
        self.assertEqual(event.last_amended, '2026-09-15')
        self.assertEqual(event.filing_count, 5)
        self.assertFalse(event.earlier_filings_missing)

    def test_amounts_are_never_added_across_amendments(self):
        event = _events(DIVERSY_CHAIN)[0]
        self.assertEqual(event.amount_sold, 1000000)  # not $1,025,000

    def test_the_chain_is_followed_link_by_link_whatever_order_the_filings_arrive_in(self):
        shuffled = [CMS_CHAIN[2], CMS_CHAIN[4], CMS_CHAIN[0], CMS_CHAIN[3], CMS_CHAIN[1]]
        events = _events(shuffled)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].accession, '0001936701-26-000003')

    def test_an_offering_with_no_amendments_has_no_last_amended_date(self):
        event = _events([GUIDEBOX_OFFERING])[0]
        self.assertEqual(event.first_filed, '2014-11-21')
        self.assertIsNone(event.last_amended)
        self.assertEqual(event.filing_count, 1)

    def test_separate_offerings_are_separate_events_newest_first(self):
        events = _events(DIVERSY_CHAIN + [GUIDEBOX_OFFERING])
        self.assertEqual([event.accession for event in events], ['0001716191-26-000003', '0001625786-14-000001'])

    def test_an_amendment_whose_earlier_filing_isnt_among_the_recent_filings_is_still_one_event(self):
        events = _events(DIVERSY_CHAIN[:1])
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].earlier_filings_missing)
        self.assertEqual(events[0].amount_sold, 1000000)

    def test_a_pointer_loop_ends(self):
        a = ('0000000001-26-000001', '2026-01-01', 'D/A', form_d_xml(previous='0000000001-26-000002'))
        b = ('0000000001-26-000002', '2026-02-01', 'D/A', form_d_xml(previous='0000000001-26-000001'))
        self.assertEqual(len(_events([a, b])), 1)

    def test_pooled_funds_business_combinations_and_clarified_amounts_are_not_counted(self):
        from zelda_api.sec_financing import capital_total
        fund = _events([VENTURE_FUND_OFFERING])[0]
        self.assertFalse(fund.counts_toward_total)
        self.assertEqual(fund.excluded_reason, 'pooled_fund')

        combination = _events([('0000000009-26-000001', '2026-01-05', 'D', form_d_xml(
            sold='4000000', business_combination=True))])[0]
        self.assertFalse(combination.counts_toward_total)
        self.assertEqual(combination.excluded_reason, 'business_combination')

        clarified = _events(CMS_CHAIN)[0]
        self.assertFalse(clarified.counts_toward_total)
        self.assertEqual(clarified.excluded_reason, 'clarified')

        company = _events(DIVERSY_CHAIN + [GUIDEBOX_OFFERING])
        total, counted, excluded = capital_total(company + [fund, combination, clarified])
        self.assertEqual(total, 1125000)
        self.assertEqual(len(counted), 2)
        self.assertEqual(len(excluded), 3)

    def test_revenue_brackets_are_read_exactly_as_the_form_prints_them(self):
        from zelda_api.sec_financing import revenue_bounds
        self.assertEqual(revenue_bounds('No Revenues'), (0, 0))
        self.assertEqual(revenue_bounds('$1 - $1,000,000'), (1, 1000000))
        self.assertEqual(revenue_bounds('$1,000,001 - $5,000,000'), (1000001, 5000000))
        self.assertEqual(revenue_bounds('$5,000,001 - $25,000,000'), (5000001, 25000000))
        self.assertEqual(revenue_bounds('$25,000,001 - $100,000,000'), (25000001, 100000000))
        self.assertEqual(revenue_bounds('Over $100,000,000'), (100000001, None))
        for not_a_bracket in ('Decline to Disclose', 'Not Applicable', '$5M', '', None):
            self.assertIsNone(revenue_bounds(not_a_bracket))


# --------------------------------------------------------------------------
# Entity Integrity rows
# --------------------------------------------------------------------------

class _RowsMixin:

    def setUp(self):
        _mock_embedding_generation(self)
        self.founder_user = User.objects.create_user('capital_founder', password='x')
        self.founder = Application.objects.create(
            user=self.founder_user, company_name='Akil-Abree Consulting, LLC', founder_name='David Lockman',
            email='d@t.com', description='test', sector='Consulting', stage='Seed',
            years_in_business=date.today().year - 2021, company_website='',
        )

    def _seller(self, annual_revenue=None):
        seller_user = User.objects.create_user('capital_seller', password='x')
        return SellerApplication.objects.create(
            user=seller_user, company_name='Akil-Abree Consulting LLC', seller_name='David Lockman', email='s@t.com',
            description='test', industry='Consulting', years_in_business=0, company_website='',
            annual_revenue=annual_revenue,
        )

    def _rows(self, sec, subject=None):
        from zelda_api import entity_verification, sec_identity
        with _patched_sec(sec), mock.patch.object(sec_identity.time, 'sleep'), \
                mock.patch.object(entity_verification, 'fetch_public_page'), \
                mock.patch.object(entity_verification, 'lookup_domain_creation_date', return_value=(None, '')):
            return entity_verification.collect_findings(subject or self.founder)

    @staticmethod
    def _one(rows, check):
        found = [row for row in rows if row['check'] == check]
        if len(found) != 1:
            raise AssertionError(f'expected one {check} row, found {len(found)}: {[row["check"] for row in rows]}')
        return found[0]

    @staticmethod
    def _offerings(rows):
        return [row for row in rows if row['check'] == 'sec_offering']


class CapitalHistoryRowTests(_RowsMixin, TestCase):

    def test_an_amendment_chain_is_one_offering_row_with_its_current_record(self):
        sec = _Filings(DIVERSY_CHAIN)
        rows = self._rows(sec)
        offerings = self._offerings(rows)
        self.assertEqual(len(offerings), 1)
        row = offerings[0]
        self.assertEqual(row['result'], 'public_record')
        self.assertIn('$1,000,000', row['evidence'])
        self.assertNotIn('$1,025,000', row['evidence'])
        self.assertIn('2025-07-28', row['evidence'])   # date of first sale
        self.assertIn('20 investors', row['evidence'])
        self.assertIn('Debt', row['evidence'])
        self.assertIn('2025-08-11', row['evidence'])   # first filed
        self.assertIn('2026-09-15', row['evidence'])   # last amended
        self.assertIn('000171619126000003', row['source_url'])

    def test_every_form_d_is_fetched_once(self):
        sec = _Filings(CMS_CHAIN)
        self._rows(sec)
        fetches = sec.form_d_fetches()
        self.assertEqual(len(fetches), 5)
        self.assertEqual(len(set(fetches)), 5)

    def test_separate_offerings_add_up_and_the_profile_claim_sits_beside_the_total(self):
        self.founder.prior_amount_raised = Decimal('1500000')
        self.founder.save()
        rows = self._rows(_Filings(DIVERSY_CHAIN + [GUIDEBOX_OFFERING]))
        self.assertEqual(len(self._offerings(rows)), 2)
        total = self._one(rows, 'sec_capital_raised')
        self.assertEqual(total['result'], 'public_record')
        self.assertIn('$1,500,000', total['claim'])
        self.assertIn('$1,125,000', total['evidence'])

    def test_a_gap_between_the_claim_and_the_filings_is_still_public_record(self):
        self.founder.prior_amount_raised = Decimal('9000000')
        self.founder.save()
        total = self._one(self._rows(_Filings([GUIDEBOX_OFFERING])), 'sec_capital_raised')
        self.assertEqual(total['result'], 'public_record')
        self.assertIn('$9,000,000', total['claim'])
        self.assertIn('$125,000', total['evidence'])

    def test_zero_or_blank_prior_capital_is_no_claim(self):
        for amount in (Decimal('0'), None):
            with self.subTest(amount=amount):
                Application.objects.filter(pk=self.founder.pk).update(prior_amount_raised=amount or 0)
                self.founder.refresh_from_db()
                total = self._one(self._rows(_Filings([GUIDEBOX_OFFERING])), 'sec_capital_raised')
                self.assertIn('not claimed', total['claim'])
                self.assertNotIn('$0', total['claim'])
                self.assertEqual(total['result'], 'public_record')

    def test_the_total_says_form_d_is_incomplete_and_only_recent_filings_were_read(self):
        total = self._one(self._rows(_Filings([GUIDEBOX_OFFERING])), 'sec_capital_raised')
        self.assertIn('SAFE', total['evidence'])
        self.assertIn('Older filings may not be included', total['evidence'])

    def test_a_venture_fund_offering_is_shown_but_not_counted(self):
        rows = self._rows(_Filings([VENTURE_FUND_OFFERING, GUIDEBOX_OFFERING]))
        fund_row = next(row for row in self._offerings(rows) if '000214854126000001' in row['source_url'])
        self.assertIn('Venture Capital Fund', fund_row['evidence'])
        self.assertIn('not counted', fund_row['evidence'])
        self.assertIn('$125,000', self._one(rows, 'sec_capital_raised')['evidence'])
        self.assertNotIn('$2,310,000', self._one(rows, 'sec_capital_raised')['evidence'])

    def test_a_business_combination_is_shown_but_not_counted(self):
        combination = ('0000000009-26-000001', '2026-01-05', 'D', form_d_xml(sold='4000000', business_combination=True))
        rows = self._rows(_Filings([combination, GUIDEBOX_OFFERING]))
        combination_row = next(row for row in self._offerings(rows) if '000000000926000001' in row['source_url'])
        self.assertIn('business combination', combination_row['evidence'])
        self.assertIn('not counted', combination_row['evidence'])
        self.assertNotIn('$4,125,000', self._one(rows, 'sec_capital_raised')['evidence'])

    def test_an_amount_the_filer_clarifies_is_quoted_and_not_counted(self):
        # CMS Apollo's "amount sold" is a distribution threshold for profits
        # interests, not money raised -- reading it as fundraising would widen
        # what the field means.
        rows = self._rows(_Filings(CMS_CHAIN))
        offering = self._one(rows, 'sec_offering')
        self.assertIn('$25,541,548', offering['evidence'])
        self.assertIn('per-unit amount', offering['evidence'])
        self.assertIn('not counted', offering['evidence'])
        for older in ('8,885,405', '22,553,036', '24,142,798'):
            self.assertNotIn(older, offering['evidence'])
        self.assertIn('indefinite', offering['evidence'].lower())
        self.assertIn('Profits Interests', offering['evidence'])
        self.assertNotIn('$25,541,548', self._one(rows, 'sec_capital_raised')['evidence'])

    def test_missing_earlier_filings_are_mentioned(self):
        offering = self._one(self._rows(_Filings(DIVERSY_CHAIN[:1])), 'sec_offering')
        self.assertIn('Earlier filings for this offering', offering['evidence'])

    def test_a_filer_without_a_form_d_has_no_offering_rows(self):
        rows = self._rows(_Filings([('0000320193-26-000001', '2026-01-01', '10-K')], facts=ANNUAL_REPORT_FACTS))
        self.assertEqual(self._offerings(rows), [])
        self.assertEqual(self._one(rows, 'sec_capital_raised')['result'], 'not_applicable')

    def test_sec_failing_partway_through_the_filings_couldnt_be_checked(self):
        rows = self._rows(_Filings(DIVERSY_CHAIN, fail_accession='0001716191-25-000003'))
        self.assertEqual(self._offerings(rows), [])
        self.assertEqual(self._one(rows, 'sec_capital_raised')['result'], 'couldnt_check')
        self.assertEqual(self._one(rows, 'sec_filer')['result'], 'matches')

    def test_only_the_newest_form_d_filings_are_read_and_the_row_says_so(self):
        from zelda_api import sec_identity
        many = [(f'0000000001-26-{n:06d}', _days_ago(n), 'D', form_d_xml(sold='1000')) for n in range(1, 26)]
        sec = _Filings(many)
        rows = self._rows(sec)
        self.assertEqual(len(sec.form_d_fetches()), sec_identity.MAX_FORM_D_FILINGS)
        self.assertIn(f'newest {sec_identity.MAX_FORM_D_FILINGS}', self._one(rows, 'sec_capital_raised')['evidence'])

    def test_a_business_for_sale_gets_the_capital_rows_without_a_prior_capital_claim(self):
        rows = self._rows(_Filings([GUIDEBOX_OFFERING]), subject=self._seller())
        self.assertEqual(len(self._offerings(rows)), 1)
        self.assertIn('not on the profile', self._one(rows, 'sec_capital_raised')['claim'])


class RevenueRowTests(_RowsMixin, TestCase):

    def _bracket_filing(self, revenue, days_ago, accession='0001096906-26-000234'):
        # Values from Heat Safety Solutions, LLC Series 1's Form D.
        return (accession, _days_ago(days_ago), 'D', form_d_xml(
            first_sale='2024-12-31', offering='5000000', sold='5000000', remaining='0', investors='69',
            securities=('isEquityType',), industry='Other Technology', revenue=revenue))

    def test_a_founders_current_revenue_is_public_record_beside_the_bracket_even_far_outside_it(self):
        for amount in ('600000', '50000000'):
            with self.subTest(amount=amount):
                self.founder.current_revenue = Decimal(amount)
                self.founder.save()
                row = self._one(self._rows(_Filings([self._bracket_filing('$1 - $1,000,000', 30)])), 'sec_revenue')
                self.assertEqual(row['result'], 'public_record')
                self.assertIn(f'${int(amount):,}', row['claim'])
                self.assertIn('period', row['claim'])
                self.assertIn('$1 - $1,000,000', row['evidence'])
                self.assertIn(_days_ago(30), row['evidence'])
                self.assertIn('fiscal year', row['evidence'])

    def test_a_sellers_annual_revenue_inside_a_recent_bracket_is_public_record(self):
        seller = self._seller(annual_revenue=Decimal('3000000'))
        row = self._one(self._rows(_Filings([self._bracket_filing('$1,000,001 - $5,000,000', 30)]), subject=seller), 'sec_revenue')
        self.assertEqual(row['result'], 'public_record')
        self.assertIn('$3,000,000', row['claim'])

    def test_a_sellers_annual_revenue_outside_a_recent_bracket_doesnt_match_and_gives_the_filing_date(self):
        seller = self._seller(annual_revenue=Decimal('12000000'))
        row = self._one(self._rows(_Filings([self._bracket_filing('$1,000,001 - $5,000,000', 30)]), subject=seller), 'sec_revenue')
        self.assertEqual(row['result'], 'doesnt_match')
        self.assertIn('$1,000,001 - $5,000,000', row['evidence'])
        self.assertIn(_days_ago(30), row['evidence'])

    def test_a_bracket_filed_more_than_twelve_months_ago_is_only_public_record(self):
        seller = self._seller(annual_revenue=Decimal('12000000'))
        for days, result in ((365, 'doesnt_match'), (366, 'public_record'), (900, 'public_record')):
            with self.subTest(days=days):
                row = self._one(self._rows(
                    _Filings([self._bracket_filing('$1,000,001 - $5,000,000', days)]), subject=seller), 'sec_revenue')
                self.assertEqual(row['result'], result)
                self.assertIn(_days_ago(days), row['evidence'])

    def test_the_edges_of_the_brackets(self):
        cases = [
            ('No Revenues', '0', 'public_record'),
            ('No Revenues', '500', 'doesnt_match'),
            ('$1 - $1,000,000', '1000000', 'public_record'),
            ('$1 - $1,000,000', '1000001', 'doesnt_match'),
            ('Over $100,000,000', '150000000', 'public_record'),
        ]
        seller = self._seller()
        for bracket, amount, result in cases:
            with self.subTest(bracket=bracket, amount=amount):
                SellerApplication.objects.filter(pk=seller.pk).update(annual_revenue=Decimal(amount))
                seller.refresh_from_db()
                row = self._one(self._rows(_Filings([self._bracket_filing(bracket, 30)]), subject=seller), 'sec_revenue')
                self.assertEqual(row['result'], result)

    def test_declined_or_not_applicable_revenue_is_not_applicable(self):
        seller = self._seller(annual_revenue=Decimal('3000000'))
        for bracket in ('Decline to Disclose', 'Not Applicable'):
            with self.subTest(bracket=bracket):
                row = self._one(self._rows(_Filings([self._bracket_filing(bracket, 30)]), subject=seller), 'sec_revenue')
                self.assertEqual(row['result'], 'not_applicable')

    def test_a_funds_net_asset_value_is_never_read_as_revenue(self):
        seller = self._seller(annual_revenue=Decimal('3000000'))
        filing = ('0001879709-26-000002', _days_ago(30), 'D/A', NET_ASSET_VALUE_FILING)
        row = self._one(self._rows(_Filings([filing]), subject=seller), 'sec_revenue')
        self.assertEqual(row['result'], 'not_applicable')
        self.assertIn('net asset value', row['evidence'])

    def test_the_newest_form_d_across_offerings_supplies_the_bracket(self):
        seller = self._seller(annual_revenue=Decimal('3000000'))
        older = self._bracket_filing('$1,000,001 - $5,000,000', 700, accession='0001096906-24-000100')
        newer = self._bracket_filing('$1 - $1,000,000', 30, accession='0001096906-26-000200')
        row = self._one(self._rows(_Filings([newer, older]), subject=seller), 'sec_revenue')
        self.assertEqual(row['result'], 'doesnt_match')
        self.assertIn('$1 - $1,000,000', row['evidence'])
        self.assertIn('000109690626000200', row['source_url'])

    def test_no_revenue_on_the_profile_shows_the_bracket_as_public_record(self):
        row = self._one(self._rows(_Filings([self._bracket_filing('$1 - $1,000,000', 30)])), 'sec_revenue')
        self.assertEqual(row['result'], 'public_record')
        self.assertIn('not on the profile', row['claim'])

    def test_an_annual_report_filer_uses_the_existing_10k_revenue_extractor_as_public_record(self):
        from zelda_api.truth_delta_sources import SECFilingsIntegration
        seller = self._seller(annual_revenue=Decimal('12000000'))
        sec = _Filings([('0000320193-26-000001', '2026-01-01', '10-K')], facts=ANNUAL_REPORT_FACTS)
        with mock.patch.object(SECFilingsIntegration, 'extract_revenue', autospec=True,
                               side_effect=SECFilingsIntegration.extract_revenue) as extract:
            row = self._one(self._rows(sec, subject=seller), 'sec_revenue')
        self.assertTrue(extract.called)
        self.assertEqual(row['result'], 'public_record')
        self.assertIn('$1,100,000,000', row['evidence'])
        self.assertIn('FY2024', row['evidence'])
        facts_calls = [call for call in sec.calls if 'companyfacts' in call['url']]
        self.assertEqual(len(facts_calls), 1)
        self.assertIn('@', facts_calls[0]['headers'].get('User-Agent', ''))
        self.assertFalse(any(call['params'].get('type') == '10-K' for call in sec.calls))

    def test_annual_report_figures_that_cant_be_fetched_couldnt_be_checked(self):
        sec = _Filings([('0000320193-26-000001', '2026-01-01', '10-K')], facts=None)
        self.assertEqual(self._one(self._rows(sec), 'sec_revenue')['result'], 'couldnt_check')

    def test_a_filer_with_neither_a_form_d_nor_an_annual_report_has_revenue_not_applicable(self):
        sec = _Filings([('0002153610-26-000009', '2026-01-01', '8-K')])
        self.assertEqual(self._one(self._rows(sec), 'sec_revenue')['result'], 'not_applicable')


class CapitalRevenueSafetyTests(_RowsMixin, TestCase):

    def test_editing_revenue_or_prior_capital_starts_a_fresh_check(self):
        from zelda_api.entity_verification import inputs_hash
        before = inputs_hash(self.founder)
        self.founder.current_revenue = Decimal('250000')
        self.assertNotEqual(inputs_hash(self.founder), before)
        middle = inputs_hash(self.founder)
        self.founder.prior_amount_raised = Decimal('750000')
        self.assertNotEqual(inputs_hash(self.founder), middle)

        seller = self._seller()
        seller_before = inputs_hash(seller)
        seller.annual_revenue = Decimal('4000000')
        self.assertNotEqual(inputs_hash(seller), seller_before)

    def test_addresses_and_phone_numbers_are_never_shown_and_nothing_is_verified_or_scored(self):
        self.founder.prior_amount_raised = Decimal('1500000')
        self.founder.current_revenue = Decimal('600000')
        self.founder.save()
        everything = json.dumps(self._rows(_Filings(CMS_CHAIN + DIVERSY_CHAIN + [VENTURE_FUND_OFFERING])))
        for private in ('746', 'SUNSET', '872-222', '60425'):
            self.assertNotIn(private, everything)
        self.assertNotIn('verified', everything.lower())
        self.assertNotIn('score', everything.lower())
