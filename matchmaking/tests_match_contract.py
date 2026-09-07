"""
Match Score contract v1 - the invariants, asserted directly.

Every case here corresponds to a defect the cold-contact audit measured,
or to a rule the contract states. These are the tests that must fail if
someone reintroduces a stand-in for missing data, lets one signal carry a
Strong band, or renders the internal score to a user.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .match_components import (
    DEAL_SIZE, DEAL_STRUCTURE, INDUSTRY, SECTOR, SEMANTIC, SPARSE, STAGE,
    deal_signals, deal_structure_signal, sector_signal, semantic_signal,
    sparse_signal, stage_signal, venture_signals,
)
from .match_score import (
    COVERAGE, DECLARED, INFERRED, Band, CONTRACT_VERSION, Signal, build_result,
    derive_band, independent_count, internal_score,
)
from .models import Application, BuyerApplication, InvestorApplication, SellerApplication

User = get_user_model()


def declared(key, value, family=None, derived=frozenset()):
    return Signal(key, value, family or key, DECLARED, derived)


def inferred(key, value, family=None, derived=frozenset()):
    return Signal(key, value, family or key, INFERRED, derived)


class BandDerivationTests(TestCase):
    """Strong / Notable / Possible / Unranked, and what each requires."""

    def test_no_signals_is_unranked(self):
        self.assertEqual(derive_band([declared('a', None), declared('b', None)]), Band.UNRANKED)

    def test_single_declared_signal_is_notable_never_strong(self):
        # The stage-alone = 60 defect: one declared field must not read as
        # a strong match no matter how well it scores.
        band = derive_band([declared('stage', 100.0), declared('sector', None)])
        self.assertEqual(band, Band.NOTABLE)
        self.assertLess(band, Band.STRONG)

    def test_two_independent_declared_signals_reach_strong(self):
        band = derive_band([declared('sector', 100.0), declared('stage', 100.0)])
        self.assertEqual(band, Band.STRONG)

    def test_inferred_only_is_possible_not_notable(self):
        # Nothing either party declared: real evidence, but not a claim
        # anyone made, so it cannot clear the declared-fit requirement.
        self.assertEqual(derive_band([inferred('semantic', 90.0)]), Band.POSSIBLE)

    def test_strong_requires_a_declared_signal_not_just_two_inferred(self):
        band = derive_band([inferred('semantic', 90.0, 'semantic'),
                            inferred('other', 90.0, 'other')])
        self.assertEqual(band, Band.POSSIBLE)

    def test_bands_are_ordered_so_consumers_can_use_thresholds(self):
        self.assertTrue(Band.STRONG > Band.NOTABLE > Band.POSSIBLE > Band.UNRANKED)


class IndependenceTests(TestCase):
    """R7 - correlated evidence cannot count twice."""

    def test_same_family_twice_counts_once(self):
        self.assertEqual(independent_count([declared('a', 100.0, 'sector'),
                                            declared('b', 100.0, 'sector')]), 1)

    def test_semantic_derived_from_sector_is_not_independent_of_sector(self):
        sector = declared('sector', 100.0, 'sector')
        semantic = inferred('semantic', 90.0, 'semantic', frozenset({'sector'}))
        self.assertEqual(independent_count([sector, semantic]), 1)
        self.assertEqual(derive_band([sector, semantic]), Band.NOTABLE)

    def test_semantic_not_derived_from_sector_is_independent(self):
        sector = declared('sector', 100.0, 'sector')
        semantic = inferred('semantic', 90.0, 'semantic')
        self.assertEqual(independent_count([sector, semantic]), 2)
        self.assertEqual(derive_band([sector, semantic]), Band.STRONG)

    def test_independent_count_is_exhaustive_not_greedy(self):
        # A greedy left-to-right pass that takes 'a' first would find only
        # 2 here; the true maximum independent set is 3.
        signals = [
            declared('a', 100.0, 'sector'),
            declared('b', 100.0, 'stage'),
            inferred('c', 100.0, 'semantic', frozenset({'sector'})),
            declared('d', 100.0, 'geography'),
        ]
        self.assertEqual(independent_count(signals), 3)

    def test_absent_signals_never_count_toward_independence(self):
        self.assertEqual(independent_count([declared('a', 100.0, 'sector'),
                                            declared('b', None, 'stage')]), 1)


class AbsenceSemanticsTests(TestCase):
    """R1 and R2 - the ai_score = 50.0 defect and the renormalisation trap."""

    def test_absence_lowers_the_score_rather_than_redistributing(self):
        both = internal_score([declared('a', 100.0, 'sector'), declared('b', 100.0, 'stage')])
        one = internal_score([declared('a', 100.0, 'sector'), declared('b', None, 'stage')])
        self.assertEqual(both, 100.0)
        self.assertEqual(one, 50.0)
        self.assertLess(one, both, 'a missing component must not hand its share to the survivors')

    def test_coverage_signals_never_move_the_score(self):
        with_coverage = internal_score([declared('a', 100.0, 'sector'),
                                        Signal('sparse', 100.0, 'sparse', COVERAGE)])
        without = internal_score([declared('a', 100.0, 'sector')])
        self.assertEqual(with_coverage, without)

    def test_coverage_signals_do_count_toward_basis(self):
        result = build_result([declared('a', None, 'sector'),
                               Signal('sparse', 40.0, 'sparse', COVERAGE)])
        self.assertEqual(result.basis, 1)
        self.assertEqual(result.band, Band.UNRANKED, 'coverage alone is not fit')

    def test_no_signals_scores_zero_not_a_midpoint(self):
        self.assertEqual(internal_score([declared('a', None), declared('b', None)]), 0.0)


class FullBasisAndPersistenceTests(TestCase):
    """Truth-table rows that gate alerting and snapshot writes."""

    def test_full_basis_requires_every_strength_component_present(self):
        complete = build_result([declared('a', 100.0, 'sector'), declared('b', 80.0, 'stage')])
        partial = build_result([declared('a', 100.0, 'sector'), declared('b', None, 'stage')])
        self.assertTrue(complete.full_basis)
        self.assertFalse(partial.full_basis)

    def test_strong_but_thin_basis_is_not_alertable(self):
        result = build_result([declared('a', 100.0, 'sector'),
                               declared('b', 100.0, 'stage'),
                               inferred('c', None, 'semantic')])
        self.assertEqual(result.band, Band.STRONG)
        self.assertFalse(result.full_basis, 'Strong is not enough for an outbound push')

    def test_no_evidence_pairing_is_not_persistable(self):
        result = build_result([declared('a', None, 'sector'), declared('b', None, 'stage')])
        self.assertEqual(result.band, Band.UNRANKED)
        self.assertFalse(result.persistable,
                         'an empty-basis prediction corrupts the grading dataset')

    def test_a_real_pairing_is_persistable(self):
        self.assertTrue(build_result([declared('a', 100.0, 'sector')]).persistable)

    def test_result_carries_the_contract_version(self):
        result = build_result([declared('a', 100.0, 'sector')])
        self.assertEqual(result.contract_version, CONTRACT_VERSION)
        self.assertEqual(result.as_dict()['match_contract_version'], 'v1')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VentureComponentTests(TestCase):
    """The venture roster against real model instances."""

    def setUp(self):
        self.founder_user = User.objects.create_user('mc_founder', password='x')
        self.investor_user = User.objects.create_user('mc_investor', password='x')

    def _app(self, sector='Climate Tech', stage='Seed', description='Forecasting for solar operators.'):
        return Application.objects.create(
            user=self.founder_user, company_name='NW', founder_name='F', email='f@t.com',
            description=description, sector=sector, stage=stage, raising_amount=4_000_000,
        )

    def _inv(self, focus='Climate Tech, energy software', stage='Seed'):
        return InvestorApplication.objects.create(
            user=self.investor_user, full_name='I', company_name='Fund', email='i@t.com',
            investment_focus=focus, investment_stage=stage,
        )

    def test_sector_absent_when_either_side_is_blank(self):
        self.assertIsNone(sector_signal(self._app(sector=''), self._inv()).value)

    def test_sector_exact_match_scores_full(self):
        self.assertEqual(sector_signal(self._app(), self._inv()).value, 100.0)

    def test_sector_outside_focus_scores_zero_not_none(self):
        # A stated mismatch is evidence; only an unstated field is None.
        signal = sector_signal(self._app(sector='Cookware'), self._inv())
        self.assertEqual(signal.value, 0.0)
        self.assertTrue(signal.present)

    def test_stage_punctuation_still_matches(self):
        self.assertEqual(stage_signal(self._app(stage='series-A'), self._inv(stage='Series A')).value, 100.0)

    def test_semantic_is_none_without_vectors(self):
        signal = semantic_signal(self._app(), self._inv())
        self.assertIsNone(signal.value)
        self.assertEqual(signal.party, INFERRED)

    def test_semantic_declares_the_families_its_text_already_asserts(self):
        app = self._app(description='We are a Climate Tech company raising at Seed.')
        signal = semantic_signal(app, self._inv())
        self.assertIn(SECTOR, signal.derived_from)
        self.assertIn(STAGE, signal.derived_from)

    def test_semantic_over_neutral_text_asserts_no_families(self):
        app = self._app(description='Forecasting software for community solar operators.')
        self.assertEqual(semantic_signal(app, self._inv()).derived_from, frozenset())

    def test_sparse_is_coverage_not_fit(self):
        self.assertEqual(sparse_signal(self._app(), self._inv()).party, COVERAGE)

    def test_roster_is_stable_so_absence_can_lower_the_score(self):
        self.assertEqual([s.key for s in venture_signals(self._app(), self._inv())],
                         [SECTOR, STAGE, SEMANTIC, SPARSE])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DealComponentTests(TestCase):
    """R4 - the NO_PREFERENCE defect, and the M&A roster."""

    def setUp(self):
        self.seller_user = User.objects.create_user('mc_seller', password='x')
        self.buyer_user = User.objects.create_user('mc_buyer', password='x')

    def _seller(self, industry='Facilities Services', asking=3_400_000, structure='Asset sale'):
        return SellerApplication.objects.create(
            user=self.seller_user, company_name='Meridian', seller_name='S', email='s@t.com',
            description='Signage installer.', industry=industry, asking_price=asking,
            deal_structure=structure,
        )

    def _buyer(self, thesis='Buy profitable facilities services businesses.',
               lo=2_000_000, hi=6_000_000, preference='NO_PREFERENCE'):
        return BuyerApplication.objects.create(
            user=self.buyer_user, full_name='B', company_name='Hale', email='b@t.com',
            acquisition_thesis=thesis, budget_min=lo, budget_max=hi,
            preferred_deal_structure=preference,
        )

    def test_no_preference_is_none_not_a_match(self):
        signal = deal_structure_signal(self._seller(), self._buyer(preference='NO_PREFERENCE'))
        self.assertIsNone(signal.value, 'an unstated preference is not evidence of agreement')

    def test_no_preference_cannot_carry_a_pairing_to_strong(self):
        # industry + NO_PREFERENCE used to reach 65 of 100 on two fields.
        signals = deal_signals(self._seller(asking=0), self._buyer(preference='NO_PREFERENCE'))
        self.assertEqual(derive_band(signals), Band.NOTABLE)
        self.assertLess(derive_band(signals), Band.STRONG)

    def test_matching_structure_is_a_real_signal(self):
        self.assertEqual(
            deal_structure_signal(self._seller(structure='Asset sale'),
                                  self._buyer(preference='Asset sale')).value, 100.0)

    def test_unpriced_business_is_unstated_not_a_mismatch(self):
        # asking_price is NOT NULL with default=0, so an unpriced seller
        # stores 0 - the same 'absent looks like a number' trap that hid
        # well-capitalised founders before PR #18.
        signals = {s.key: s for s in deal_signals(self._seller(asking=0), self._buyer())}
        self.assertIsNone(signals[DEAL_SIZE].value)

    def test_industry_and_deal_size_together_reach_strong(self):
        signals = deal_signals(self._seller(), self._buyer())
        self.assertEqual(derive_band(signals), Band.STRONG)
        self.assertEqual(independent_count(signals), 2)
