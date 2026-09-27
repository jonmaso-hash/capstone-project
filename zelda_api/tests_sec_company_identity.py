"""
A name is not an identity, and two registrants can share one.

Walked live on 2026-09-26: Entity Integrity resolved "Starbucks Corporation"
to CIK 0000887557 while Truth Delta resolved it to 0000829224. Both
subsystems then presented findings about different companies as facts about
one, on adjacent surfaces.

The registrants, from data.sec.gov/submissions (recorded below):

    0000829224   1015 filings, 10-K x10 (newest 2025-11-14),
                 10-Q x33 (newest 2026-07-29), ticker SBUX, Nasdaq
    0000887557     10 filings, NO 10-K, NO 10-Q,
                 Form 4 x1 (2004), SC 13G x3 (newest 2014),
                 no ticker, formerNames ['STARBUCKS CORPORATION']

Two things follow, and neither is fixable by matching names harder.

THE MATCH CAME FROM A FORMER NAME. 0000887557's *former* name is exactly the
string searched. The operating company's current conformed name is
"STARBUCKS CORP", which is not an exact match for "Starbucks Corporation".
So a dormant registrant's historical name beat the live company's current
one, and every name-equality rule in #97 would agree with that result.

NAME EQUALITY CANNOT SEPARATE THEM ANYWAY. Both are literally "STARBUCKS
CORP". No strictness on the name distinguishes a company from a shell that
once shared its name.

What does distinguish them is what they FILE. A registrant that has never
filed a periodic report cannot be the source of a revenue figure, whatever
it is called. That is the source-capability question one level down: `sec:
revenue = can_establish` is a statement about a 10-K filer, not about a name.

Truth Delta got the right answer for the wrong reason -- its search passes
`type=10-K`, which excluded the shell by luck of a query parameter rather
than by any rule. That parameter is also wrong in ordinary cases: foreign
private issuers file 20-F or 40-F, a newly public company may have 10-Qs and
no 10-K yet, and a deregistered company still has old 10-Ks on file.

So the identity is computed from filing history, and it carries what the
registrant can support:

    found                  one registrant, with periodic filings
    ambiguous              several plausible registrants -- refuse
    no_financial_identity  a registrant exists but files nothing periodic
    not_found              no registrant at all

`no_financial_identity` is a first-class outcome, not a weak `found`. For
most Interlink companies it is the CORRECT answer, and a same-named
ownership-forms-only filer must never quietly occupy that slot.
"""
from django.test import SimpleTestCase

from .sec_company_identity import (
    AMBIGUOUS, FOUND, NOT_FOUND, resolve_from_candidates,
)


def submissions(cik, name, forms, tickers=(), former=(), sic='5810'):
    """A data.sec.gov/submissions payload, reduced to what the resolver reads.

    `forms` is [(form, filingDate), ...] newest-first, as EDGAR returns it.
    """
    return {
        'cik': cik.lstrip('0'),
        'name': name,
        'tickers': list(tickers),
        'exchanges': ['Nasdaq'] if tickers else [],
        'sic': sic,
        'formerNames': [{'name': n} for n in former],
        'filings': {'recent': {
            'form': [f for f, _ in forms],
            'filingDate': [d for _, d in forms],
        }},
    }


# --- the two real registrants, recorded 2026-09-26 -----------------------
STARBUCKS_REAL = submissions(
    '0000829224', 'STARBUCKS CORP',
    [('10-Q', '2026-07-29'), ('4', '2026-09-17'), ('10-K', '2025-11-14'),
     ('10-Q', '2025-04-29'), ('8-K', '2025-01-28')],
    tickers=['SBUX'], sic='5810')

STARBUCKS_SHELL = submissions(
    '0000887557', 'STARBUCKS CORP',
    [('SC 13G', '2014-02-14'), ('SC 13G', '2013-02-11'), ('4', '2004-02-19')],
    former=['STARBUCKS CORPORATION'], sic='2090')


class TheOperatingCompanyWinsOverAShellTests(SimpleTestCase):

    def test_starbucks_resolves_to_the_registrant_that_files(self):
        """
        The walk's regression. Both registrants are called STARBUCKS CORP;
        only one has ever filed a periodic report.
        """
        identity = resolve_from_candidates('Starbucks Corporation',
                                           [STARBUCKS_SHELL, STARBUCKS_REAL])
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0000829224')
        self.assertTrue(identity.can_establish_revenue)

    def test_the_shell_alone_resolves_but_cannot_establish_revenue(self):
        """
        Identity and capability are separate questions. A registrant that has
        only ever filed ownership forms IS a registrant -- refusing to
        resolve it would resurrect the annual-report heuristic that broke
        Form D-only private companies. It simply cannot be the source of a
        revenue figure.
        """
        identity = resolve_from_candidates('Starbucks Corporation', [STARBUCKS_SHELL])
        self.assertEqual(identity.status, FOUND)
        self.assertFalse(identity.can_establish_revenue,
                         'a registrant with no periodic filings supplied revenue')
        self.assertTrue(identity.is_stale)

    def test_a_form_d_only_private_company_resolves(self):
        """
        The case that caught the first design. Most Interlink companies are
        here: a real registrant, no periodic reporting, and Entity
        Integrity's whole Form D pathway depends on finding it.
        """
        form_d_only = submissions('0002153610', 'AKIL-ABREE CONSULTING, LLC',
                                  [('D', '2026-05-01')], sic='8742')
        identity = resolve_from_candidates('Akil-Abree Consulting, LLC', [form_d_only])
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0002153610')
        self.assertFalse(identity.can_establish_revenue)

    def test_a_former_name_match_does_not_outrank_a_current_one(self):
        """
        The shell matched because its FORMER name is exactly the string
        searched, while the real company's current name is 'STARBUCKS CORP'.
        Every name-equality rule in #97 would have agreed with the shell.
        """
        identity = resolve_from_candidates('Starbucks Corporation',
                                           [STARBUCKS_SHELL, STARBUCKS_REAL])
        self.assertEqual(identity.cik, '0000829224')
        self.assertEqual(identity.matched_on, 'current_name')


class RefusalAndAbsenceTests(SimpleTestCase):

    def test_two_periodic_filers_with_one_name_are_ambiguous(self):
        """
        Holding companies and debt-issuing subsidiaries do share names. When
        both actually file, filing history cannot separate them either, and
        the resolver must refuse rather than pick.
        """
        a = submissions('0000111111', 'HORIZON GROUP INC',
                        [('10-K', '2025-03-01'), ('10-Q', '2025-08-01')])
        b = submissions('0000222222', 'HORIZON GROUP INC',
                        [('10-K', '2025-02-20'), ('10-Q', '2025-07-15')])
        identity = resolve_from_candidates('Horizon Group Inc', [a, b])
        self.assertEqual(identity.status, AMBIGUOUS)
        self.assertIsNone(identity.cik)

    def test_no_registrant_at_all_is_not_found(self):
        identity = resolve_from_candidates('Bramblewood Foods', [])
        self.assertEqual(identity.status, NOT_FOUND)
        self.assertFalse(identity.can_establish_revenue)

    def test_a_private_company_with_no_filer_is_the_normal_case(self):
        """
        Most Interlink companies have no SEC registrant. That is an honest
        answer about the world, and must not be dressed up as a failure.
        """
        identity = resolve_from_candidates('Pamela\'s Pizza', [])
        self.assertEqual(identity.status, NOT_FOUND)


class TheIdentityCarriesWhatTheRegistrantCanSupportTests(SimpleTestCase):

    def test_a_foreign_private_issuer_filing_20f_still_reports_annually(self):
        """
        `type=10-K` would drop this company entirely. Annual reporting is the
        capability that matters, not one form number.
        """
        fpi = submissions('0000333333', 'NORDWIND AG',
                          [('20-F', '2026-04-30'), ('6-K', '2026-08-01')], sic='3714')
        identity = resolve_from_candidates('Nordwind AG', [fpi])
        self.assertEqual(identity.status, FOUND)
        self.assertTrue(identity.can_establish_revenue)

    def test_a_newly_public_company_with_quarterlies_but_no_annual_yet(self):
        newly = submissions('0000444444', 'MERIDIAN LABS INC',
                            [('10-Q', '2026-08-10'), ('S-1', '2026-02-01')])
        identity = resolve_from_candidates('Meridian Labs Inc', [newly])
        self.assertEqual(identity.status, FOUND)
        self.assertTrue(identity.can_establish_revenue)

    def test_a_deregistered_company_resolves_but_its_revenue_is_stale(self):
        """
        A Form 15 deregistration with old 10-Ks still on file. The registrant
        is real; its financial data is historical, and a comparison against a
        current claim must know that.
        """
        gone = submissions('0000555555', 'CALDER MILLS INC',
                           [('15-12B', '2019-06-01'), ('10-K', '2018-03-15')])
        identity = resolve_from_candidates('Calder Mills Inc', [gone])
        self.assertEqual(identity.status, FOUND)
        self.assertTrue(identity.is_stale)

    def test_a_current_filer_is_not_stale(self):
        """Control: staleness must distinguish, not flag everything."""
        identity = resolve_from_candidates('Starbucks Corporation', [STARBUCKS_REAL])
        self.assertFalse(identity.is_stale)

    def test_a_ticker_raises_confidence_but_is_never_required(self):
        """
        Private companies with registered debt file 10-Ks and have no ticker.
        Those are closer to Interlink's market than SBUX is, so absence of a
        ticker must not count against a registrant.
        """
        no_ticker = submissions('0000666666', 'RIDGEWAY HOLDINGS LLC',
                                [('10-K', '2026-03-01'), ('10-Q', '2026-08-01')])
        identity = resolve_from_candidates('Ridgeway Holdings LLC', [no_ticker])
        self.assertEqual(identity.status, FOUND)
        self.assertTrue(identity.can_establish_revenue)
        self.assertFalse(identity.has_ticker)
        self.assertTrue(resolve_from_candidates(
            'Starbucks Corporation', [STARBUCKS_REAL]).has_ticker)


class EveryFindingNamesItsRegistrantTests(SimpleTestCase):
    """
    The walk's deeper lesson: "No annual report was found" was TRUE of
    0000887557. It was wrong only because it was presented as a fact about
    Starbucks. A finding that names the registrant it was computed against
    turns this class of bug into visible output instead of a plausible
    finding.
    """

    def test_the_identity_exposes_the_cik_for_attribution(self):
        identity = resolve_from_candidates('Starbucks Corporation',
                                           [STARBUCKS_SHELL, STARBUCKS_REAL])
        self.assertEqual(identity.cik, '0000829224')
        self.assertEqual(identity.name, 'STARBUCKS CORP')

    def test_a_refusal_has_no_cik_to_attribute_to(self):
        a = submissions('0000111111', 'HORIZON GROUP INC', [('10-K', '2025-03-01')])
        b = submissions('0000222222', 'HORIZON GROUP INC', [('10-K', '2025-02-20')])
        identity = resolve_from_candidates('Horizon Group Inc', [a, b])
        self.assertIsNone(identity.cik, 'an ambiguous result must not name a registrant')


class TheCandidateSearchMustNotStopEarlyTests(SimpleTestCase):

    def setUp(self):
        # resolve_company_identity caches, and these classes share one
        # process-wide cache. Without this the suite is order-dependent:
        # the truncation test showed up as a killer for six unrelated
        # mutations because a neighbour had cached its answer first.
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
    """
    Found by running the resolver against live EDGAR; no fixture could have
    shown it.

    EDGAR's conformed name abbreviates, so the operating company is
    "STARBUCKS CORP" and searching "Starbucks Corporation" does NOT match it.
    It matches the shell, whose FORMER name is exactly that string. The
    operating company only appears under the suffix-stripped phrase.

    The first implementation stopped at the first query that returned
    anything, so it found the shell, never searched "Starbucks", and reported
    no_financial_identity for a company with 1015 filings -- swapping a
    wrong-company bug for a missing-company bug.
    """

    def test_candidates_are_gathered_from_every_name_variant(self):
        from unittest import mock
        from . import sec_company_identity as sci

        feeds = {
            'Starbucks Corporation': '<feed><cik>0000887557</cik></feed>',
            'Starbucks': '<feed><cik>0000887557</cik><cik>0000829224</cik></feed>',
        }
        calls = []

        class FakeResponse:
            def __init__(self, text):
                self.text = text

        def fake_get(url, params=None):
            calls.append(params['company'])
            return FakeResponse(feeds.get(params['company'], '<feed></feed>'))

        from . import sec_identity
        with mock.patch.object(sec_identity, '_get', side_effect=fake_get):
            found = sci.candidate_ciks('Starbucks Corporation')

        ciks, truncated = found
        self.assertEqual(calls, ['Starbucks Corporation', 'Starbucks'],
                         'the suffix-stripped phrase was not searched')
        self.assertIn('0000829224', ciks,
                      'the operating company was never offered as a candidate')
        self.assertIn('0000887557', ciks)
        self.assertFalse(truncated)

    def test_a_name_matching_more_registrants_than_we_fetch_is_ambiguous(self):
        """
        Truncation must not be silent. Searching "Meta" really does return
        dozens of Form D shells -- Meta Co, Meta Burger, Meta Athlete -- and
        Meta Platforms is not among the first ten. Ranking that sample picks
        the best of an arbitrary subset and calls it an identity; "Meta Co"
        even matches exactly, because `_company_core` strips "Co" as a legal
        suffix.

        A name we have only sampled has not been resolved.
        """
        from unittest import mock

        from . import sec_company_identity as sci
        from . import sec_identity

        many = ''.join(f'<cik>{i:010d}</cik>' for i in range(1, 26))

        class FakeResponse:
            text = f'<feed>{many}</feed>'

        with mock.patch.object(sec_identity, '_get', return_value=FakeResponse()):
            ciks, truncated = sci.candidate_ciks('Meta')
        self.assertTrue(truncated, 'a truncated candidate list was reported as complete')
        self.assertEqual(len(ciks), sci.MAX_CANDIDATES)

        with mock.patch.object(sci, 'candidate_ciks', return_value=(ciks, True)):
            identity = sci.resolve_company_identity('Meta')
        self.assertEqual(identity.status, AMBIGUOUS)
        self.assertIsNone(identity.cik)


class EachRankingSignalDecidesOnItsOwnTests(SimpleTestCase):
    """
    The Starbucks fixtures differ on every axis at once -- current-name,
    activity, periodic reporting and ticker -- so the real company wins even
    if any one signal is removed. Mutations that zeroed each signal
    individually all SURVIVED against them.

    These isolate one signal at a time: two candidates identical except for
    the dimension under test. Remove that signal and the pair ties, which
    resolves to AMBIGUOUS rather than to the right company -- so each test
    fails when its signal stops counting.
    """

    def test_a_current_name_match_beats_a_former_name_match(self):
        current = submissions('0000111111', 'CALDER MILLS INC',
                              [('10-K', '2026-03-01')], tickers=['CMI'])
        former = submissions('0000222222', 'SOMETHING ELSE INC',
                             [('10-K', '2026-03-01')], tickers=['SEI'],
                             former=['CALDER MILLS INC'])
        identity = resolve_from_candidates('Calder Mills Inc', [former, current])
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0000111111')
        self.assertEqual(identity.matched_on, 'current_name')

    def test_a_recently_active_registrant_beats_a_dormant_one(self):
        active = submissions('0000111111', 'HARBOR BAKERY LLC',
                             [('D', '2026-05-01')])
        dormant = submissions('0000222222', 'HARBOR BAKERY LLC',
                              [('D', '2011-05-01')])
        identity = resolve_from_candidates('Harbor Bakery LLC', [dormant, active])
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0000111111')

    def test_a_periodic_filer_beats_a_registrant_that_files_nothing_periodic(self):
        reporting = submissions('0000111111', 'RIDGEWAY HOLDINGS LLC',
                                [('10-K', '2026-03-01')])
        ownership_only = submissions('0000222222', 'RIDGEWAY HOLDINGS LLC',
                                     [('SC 13G', '2026-03-01')])
        identity = resolve_from_candidates('Ridgeway Holdings LLC',
                                           [ownership_only, reporting])
        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0000111111')
        self.assertTrue(identity.can_establish_revenue)


class AnAliasRenamesTheSubjectTests(SimpleTestCase):

    def setUp(self):
        # resolve_company_identity caches, and these classes share one
        # process-wide cache. Without this the suite is order-dependent:
        # the truncation test showed up as a killer for six unrelated
        # mutations because a neighbour had cached its answer first.
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
    """
    A brand name that shares no root with the registered legal name is
    unreachable by suffix-stripping: EDGAR registers "Meta Platforms, Inc."
    and nothing about "Meta" reaches it.

    The alias has to rename the SUBJECT, not merely the query. Renaming only
    the query searches "Meta Platforms" and then rejects every candidate for
    failing to match "Meta" -- which is what happened live, resolving a real
    company to nothing.
    """

    def test_candidates_are_matched_against_the_alias_not_the_brand(self):
        from unittest import mock

        from . import sec_company_identity as sci
        from . import sec_identity

        platforms = submissions('0001326801', 'Meta Platforms, Inc.',
                                [('10-K', '2026-01-29'), ('10-Q', '2026-07-30')],
                                tickers=['META'])

        with mock.patch.object(sci, 'candidate_ciks', return_value=(['0001326801'], False)), \
             mock.patch.object(sec_identity, 'company_record', return_value=platforms):
            identity = sci.resolve_company_identity('Meta')

        self.assertEqual(identity.status, FOUND)
        self.assertEqual(identity.cik, '0001326801')

    def test_a_configured_alias_is_not_broadened_back_to_the_brand(self):
        """
        Broadening past the alias buries the answer it exists to find.
        Searching "Meta Platforms" offers one registrant; adding "Meta" to
        the same resolution offers dozens of Form D shells, which trips the
        truncation guard and turns a resolvable company into ambiguous.

        Added because the mutation that restores broadening SURVIVED once
        the suite's cache flakiness was fixed -- nothing had been testing it.
        """
        from unittest import mock

        from . import sec_company_identity as sci
        from . import sec_identity

        feeds = {
            'Meta Platforms': '<feed><cik>0001326801</cik></feed>',
            'Meta': '<feed>' + ''.join(
                f'<cik>{i:010d}</cik>' for i in range(1, 26)) + '</feed>',
        }

        class FakeResponse:
            def __init__(self, text):
                self.text = text

        def fake_get(url, params=None):
            return FakeResponse(feeds.get(params['company'], '<feed></feed>'))

        with mock.patch.object(sec_identity, '_get', side_effect=fake_get):
            ciks, truncated = sci.candidate_ciks('Meta')

        self.assertEqual(ciks, ['0001326801'],
                         'the alias was broadened back to the brand name')
        self.assertFalse(truncated)

    def test_a_name_with_no_alias_is_matched_against_itself(self):
        """Control: aliasing must not leak into ordinary resolution."""
        from unittest import mock

        from . import sec_company_identity as sci
        from . import sec_identity

        with mock.patch.object(sci, 'candidate_ciks', return_value=(['0000829224'], False)), \
             mock.patch.object(sec_identity, 'company_record', return_value=STARBUCKS_REAL):
            identity = sci.resolve_company_identity('Starbucks Corporation')
        self.assertEqual(identity.cik, '0000829224')
