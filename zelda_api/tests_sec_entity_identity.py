"""
A name that EDGAR can find is not an identity.

Truth Delta's SEC client resolves a typed company name to a CIK, and every
financial datapoint it admits as evidence about a company hangs off that one
decision. Today the decision is:

    match = re.search(r'<cik>(\\d+)</cik>', response.text, re.IGNORECASE)
    return match.group(1).zfill(10), None

The FIRST cik in the feed, out of `count=10`, with no check that the company
it belongs to is the company that was asked for.

Probed live against SEC on 2026-09-26:

    asked for 'Acme'        -> 7 CIKs in the feed, code takes 0001092013
    asked for 'Apple'       -> 10 CIKs in the feed, code takes 0000320193
                               (Apple Inc -- correct by EDGAR's ordering,
                               which is luck, not a check)
    asked for 'Pamela'      -> 0 CIKs, not_found (correct)
    asked for 'NVIDIA CORP' -> 1 CIK, <conformed-name>NVIDIA CORP</...>

Why this is the most dangerous defect in the pipeline: revenue and employees
are the only two categories any live source populates, so they are the only
two where `contradicted` is reachable at all. A wrong CIK therefore feeds the
one path that can call a company a liar -- against a claim it never made.

The multi-match feed cannot be fixed by comparing names, because EDGAR does
not put the names in it. It emits Perl array references:

    <entry title="ARRAY(0x5626d4c4cdb8)">
      <company-info name="ARRAY(0x5626d4cae548)">
        <cik>0001092013</cik>

sec_identity.py already works around this for Entity Integrity by refusing
anything that isn't a single top-level <company-info>, and falling back to
full-text search. The evidence path never got the same treatment.

So the rule here is not "check the name". It is NEVER CHOOSE:

    more than one CIK in the feed  -> ambiguous, resolve nothing
    exactly one CIK                -> its conformed-name must match the name
                                      asked for, by the same core-name
                                      normalisation Entity Integrity uses
    no CIK                         -> not_found, unchanged
    timeout / request error        -> transient, unchanged and uncached

`_company_core` is the right comparison because a deck says "Starbucks" while
EDGAR's conformed name is "STARBUCKS CORP" -- the same company, and the suffix
must not defeat the check.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from .truth_delta_sources import SECFilingsIntegration


def feed(*companies):
    """An EDGAR company-search atom feed, in the two real shapes.

    One company: a top-level <company-info> carrying <conformed-name>.
    Several: <entry> elements whose names EDGAR garbles into ARRAY(0x...).
    Both shapes captured from live responses on 2026-09-26.
    """
    if len(companies) == 1:
        cik, name = companies[0]
        return (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            f'<company-info><cik>{cik}</cik>'
            f'<conformed-name>{name}</conformed-name>'
            '<state-of-incorporation>WA</state-of-incorporation>'
            '</company-info></feed>'
        )
    entries = ''.join(
        f'<entry title="ARRAY(0x{i:012x})"><content type="text/xml">'
        f'<company-info name="ARRAY(0x{i:012x})"><cik>{cik}</cik>'
        '</company-info></content></entry>'
        for i, (cik, _name) in enumerate(companies)
    )
    return (
        '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
        + entries + '</feed>'
    )


COMPANY_FACTS = {'facts': {'us-gaap': {}}, 'entityName': 'SOMEONE ELSE INC'}


class FakeResponse:
    def __init__(self, text, status_code=200, payload=None):
        self.text = text
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


class ASingleCikIsNotAnIdentityTests(SimpleTestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.integration = SECFilingsIntegration()

    def resolve(self, name, body, status_code=200):
        with patch.object(self.integration.session, 'get',
                          return_value=FakeResponse(body, status_code)):
            return self.integration.resolve_with_diagnostics(name)

    # --- never choose between entities -----------------------------------
    def test_several_companies_resolve_to_nothing(self):
        """
        The headline defect. 'Acme' really does return seven filers, and the
        current code takes the first one's financials as evidence about a
        private company that merely shares a word with it.
        """
        cik, reason = self.resolve('Acme', feed(
            ('0001092013', 'garbled'), ('0000002070', 'garbled'),
            ('0001049530', 'garbled'), ('0000883702', 'garbled'),
        ))
        self.assertIsNone(cik, 'a CIK was chosen from a feed of four companies')
        self.assertEqual(reason, 'ambiguous')

    def test_even_two_companies_resolve_to_nothing(self):
        cik, reason = self.resolve('Acme', feed(('0001092013', 'g'), ('0000002070', 'g')))
        self.assertIsNone(cik)
        self.assertEqual(reason, 'ambiguous')

    def test_a_lucky_first_hit_is_still_refused(self):
        """
        'Apple' returns ten filers and EDGAR happens to rank Apple Inc first,
        so the current code gets the right answer for the wrong reason. The
        ordering is not a check, and the refusal must not depend on whether
        the first entry happens to be right.
        """
        cik, reason = self.resolve('Apple', feed(
            ('0000320193', 'APPLE INC'), ('0001510976', 'g'), ('0000934330', 'g'),
        ))
        self.assertIsNone(cik)
        self.assertEqual(reason, 'ambiguous')

    # --- a single hit must still be the right company --------------------
    def test_one_company_whose_name_matches_resolves(self):
        """Control: the path that must keep working."""
        cik, reason = self.resolve('NVIDIA CORP', feed(('0001045810', 'NVIDIA CORP')))
        self.assertEqual(cik, '0001045810')
        self.assertIsNone(reason)

    def test_a_legal_suffix_does_not_defeat_the_match(self):
        """A deck says "Starbucks"; EDGAR's conformed name is "STARBUCKS CORP"."""
        cik, reason = self.resolve('Starbucks', feed(('0000829224', 'STARBUCKS CORP')))
        self.assertEqual(cik, '0000829224')
        self.assertIsNone(reason)

    def test_one_company_whose_name_does_not_match_is_refused(self):
        """
        The exact-collision case the spec was written for: a private company
        shares a search prefix with one unrelated filer.
        """
        cik, reason = self.resolve(
            'Bramblewood Foods', feed(('0000111111', 'BRAMBLEWOOD MINING CORP')))
        self.assertIsNone(cik, "an unrelated filer's CIK was accepted")
        self.assertEqual(reason, 'name_mismatch')

    def test_a_single_cik_with_no_name_is_refused(self):
        """
        A shape we do not understand. Every real single-match feed carries
        <conformed-name>, so a lone CIK without one means EDGAR answered with
        something other than what this parser was written against -- and an
        unverifiable CIK is precisely what this function exists to refuse.

        Added because the mutation that accepts an unnamed CIK SURVIVED: the
        branch was written and argued for in the docstring, and nothing
        exercised it.
        """
        cik, reason = self.resolve('Acme', (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<company-info><cik>0001092013</cik></company-info></feed>'
        ))
        self.assertIsNone(cik, 'a CIK with no name attached was accepted')
        self.assertEqual(reason, 'name_mismatch')

    # --- unchanged behaviour ---------------------------------------------
    def test_no_company_is_still_not_found(self):
        cik, reason = self.resolve('Pamela', feed())
        self.assertIsNone(cik)
        self.assertEqual(reason, 'not_found')

    def test_a_non_200_is_still_a_request_error(self):
        cik, reason = self.resolve('Acme', '', status_code=503)
        self.assertIsNone(cik)
        self.assertEqual(reason, 'request_error')

    def test_a_timeout_is_still_transient_and_uncached(self):
        import requests
        with patch.object(self.integration.session, 'get',
                          side_effect=requests.exceptions.Timeout()):
            cik, reason = self.integration.resolve_with_diagnostics('Acme')
        self.assertIsNone(cik)
        self.assertEqual(reason, 'timeout')
        self.assertIsNone(cache.get('sec_edgar_cik_v2:acme'),
                          'a transient failure was cached as an answer')

    # --- caching ----------------------------------------------------------
    def test_an_ambiguous_result_is_cached_like_an_absence(self):
        """
        Ambiguity is a stable fact about EDGAR's index, not a failed attempt:
        re-asking the same question gets the same several companies. Caching
        it keeps a re-run from hammering SEC. It must NOT be treated as
        transient, which is the bucket reserved for timeouts.
        """
        self.resolve('Acme', feed(('0001092013', 'g'), ('0000002070', 'g')))
        self.assertEqual(cache.get('sec_edgar_cik_v2:acme'), (None, 'ambiguous'))

    def test_a_name_mismatch_is_cached_like_an_absence(self):
        self.resolve('Bramblewood Foods', feed(('0000111111', 'BRAMBLEWOOD MINING CORP')))
        self.assertEqual(
            cache.get('sec_edgar_cik_v2:bramblewood foods'), (None, 'name_mismatch'))


class NoIdentityMeansNoEvidenceTests(SimpleTestCase):
    """
    The point of all of it: an unresolved company contributes no datapoints,
    so it cannot reach the comparison layer, so it cannot produce a
    contradiction. Asserted at the fetch boundary rather than the resolver,
    because that is the surface the engine actually calls.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.integration = SECFilingsIntegration()

    def fetch(self, name, search_feed):
        """
        The search call answers with `search_feed`; ANY later call answers
        with a valid companyfacts payload.

        That second response matters. Without it the companyfacts fetch
        raises on a response that cannot be parsed as JSON, the bare
        `except Exception` returns {}, and the test passes whether or not a
        CIK was wrongly resolved -- proving nothing. With it, resolving the
        wrong CIK returns a real payload and the assertion fails, which is
        what makes this test able to see the defect.
        """
        responses = [FakeResponse(search_feed),
                     FakeResponse('', payload=dict(COMPANY_FACTS))]
        with patch.object(self.integration.session, 'get',
                          side_effect=lambda *a, **k: responses.pop(0) if responses
                          else FakeResponse('', payload=dict(COMPANY_FACTS))):
            return self.integration.fetch_company_data(name)

    def test_the_fetch_harness_can_see_a_resolved_company(self):
        """
        Positive control for the two tests below: when the company DOES
        resolve, this harness returns the payload. Without this, an
        assertEqual({}) could be passing because the harness never returns
        anything.
        """
        data = self.fetch('NVIDIA CORP', feed(('0001045810', 'NVIDIA CORP')))
        self.assertEqual(data.get('_cik'), '0001045810')

    def test_an_ambiguous_company_yields_no_company_data(self):
        self.assertEqual(self.fetch('Acme', feed(('1', 'g'), ('2', 'g'))), {})

    def test_a_mismatched_company_yields_no_company_data(self):
        self.assertEqual(
            self.fetch('Bramblewood Foods', feed(('0000111111', 'BRAMBLEWOOD MINING CORP'))),
            {})
