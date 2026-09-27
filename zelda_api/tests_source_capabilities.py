"""
What a source is allowed to establish must be written down, not inferred.

Today it is prose. `SECFilingsIntegration.extract_customers` returns None with
the comment "Not a standard XBRL concept"; `extract_funding` returns None with
"SEC filers are typically past the funding-raised framing". Those are
capability declarations living in comments, enforced by nothing.

That is how 15 claim categories became 2 populated ones:

    15  named in ClaimedDatapoint.CATEGORY_CHOICES
     5  reachable from a deck
     4  writable as observations
     2  populated by any live source (revenue, employees -- SEC only)

Each narrowing happened silently, because no layer stated what a source could
answer for. A category is a promise the source layer never signed.

So: source x claim -> one of four roles, declared explicitly.

    can_establish        authoritative for this claim
    can_corroborate      may support a claim established elsewhere
    informational_only   provides context, never a claim
    unavailable          cannot speak to this claim at all

Two properties matter more than the table itself.

DECLARATION IS EXHAUSTIVE. A missing entry is an error, never a default.
A default would recreate exactly the silent narrowing above -- the registry
would look complete while saying nothing about the categories nobody
remembered.

THE DECLARATION MUST AGREE WITH THE CODE. A registry that drifts from the
extractors is worse than none: it documents a capability the implementation
does not have. So the tests compare the declaration against what the
extractors actually do, rather than trusting the table.

And the registry must be CONSULTED. A contract nobody reads is inert -- the
same defect as `engine_version` shipping without either `objects.create` call
setting it, caught one PR ago. `create_observed_datapoints` therefore asks
before it writes, and a mutation proves it.
"""
from django.test import SimpleTestCase

from .source_capabilities import (
    CAN_CORROBORATE, CAN_ESTABLISH, INFORMATIONAL_ONLY, ROLES, UNAVAILABLE,
    OBSERVABLE_CATEGORIES, capability_for, may_establish,
)
from .truth_delta_sources import DataSourceManager


class TheContractIsExplicitTests(SimpleTestCase):

    def test_every_integration_has_a_declaration(self):
        """
        A source the manager can run but the registry has never heard of would
        write datapoints under no contract at all.
        """
        for source_type in DataSourceManager.INTEGRATIONS:
            with self.subTest(source=source_type):
                self.assertIsNotNone(
                    capability_for(source_type, 'revenue'),
                    f'{source_type} runs but declares no capabilities',
                )

    def test_every_source_declares_every_observable_category(self):
        """
        Exhaustive by construction. A missing entry must raise, not default:
        defaulting is how a registry stays green while saying nothing about
        the categories nobody remembered.
        """
        for source_type in DataSourceManager.INTEGRATIONS:
            for category in OBSERVABLE_CATEGORIES:
                with self.subTest(source=source_type, category=category):
                    self.assertIn(capability_for(source_type, category), ROLES)

    def test_an_undeclared_pair_raises_rather_than_defaulting(self):
        with self.assertRaises(KeyError):
            capability_for('a_source_that_does_not_exist', 'revenue')
        with self.assertRaises(KeyError):
            capability_for('sec', 'a_category_that_does_not_exist')

    def test_roles_are_the_four_named_ones(self):
        """No ad-hoc strings: a typo must not silently become a new role."""
        self.assertEqual(
            ROLES,
            frozenset({CAN_ESTABLISH, CAN_CORROBORATE, INFORMATIONAL_ONLY, UNAVAILABLE}),
        )


class TheDeclarationAgreesWithTheCodeTests(SimpleTestCase):
    """
    The half that makes the registry worth having. A table that drifts from
    the extractors documents a capability the implementation does not have.
    """

    EXTRACTOR = {
        'revenue': 'extract_revenue',
        'customers': 'extract_customers',
        'employees': 'extract_employees',
        'funding_raised': 'extract_funding',
    }

    def test_an_unavailable_category_has_an_extractor_that_yields_nothing(self):
        """
        SEC declares customers and funding_raised unavailable, and its
        extractors return None by construction. If someone implements one
        without updating the registry, this fails.
        """
        payload = {'facts': {'us-gaap': {}, 'dei': {}}, 'entityName': 'X'}
        for source_type, integration_class in DataSourceManager.INTEGRATIONS.items():
            integration = integration_class()
            for category, method in self.EXTRACTOR.items():
                if capability_for(source_type, category) != UNAVAILABLE:
                    continue
                with self.subTest(source=source_type, category=category):
                    self.assertIsNone(
                        getattr(integration, method)(payload),
                        f'{source_type} declares {category} unavailable but '
                        f'{method} returned a value',
                    )

    def test_no_source_claims_a_category_the_pipeline_cannot_store(self):
        """
        `market_size` is extractable as a claim and has no observed slot at
        all. A source declaring it establishable would promise evidence the
        pipeline has nowhere to put -- the 15/5/4/2 drift in miniature.
        """
        for source_type in DataSourceManager.INTEGRATIONS:
            with self.subTest(source=source_type):
                with self.assertRaises(KeyError):
                    capability_for(source_type, 'market_size')

    def test_an_informational_source_establishes_nothing(self):
        """
        News is live when configured, and every extract_* returns None; its
        own docstring says headlines are "not a claim source itself". The
        registry must say the same thing.
        """
        for category in OBSERVABLE_CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(capability_for('news', category), INFORMATIONAL_ONLY)
                self.assertFalse(may_establish('news', category))

    def test_sec_establishes_exactly_what_it_populates(self):
        """
        The two categories any live source actually fills. Pinned so a
        widening is a deliberate act that fails this test first.
        """
        self.assertTrue(may_establish('sec', 'revenue'))
        self.assertTrue(may_establish('sec', 'employees'))
        self.assertFalse(may_establish('sec', 'customers'))
        self.assertFalse(may_establish('sec', 'funding_raised'))


class TheContractIsConsultedTests(SimpleTestCase):
    """
    A registry nobody reads is inert. `may_establish` is the gate the writing
    path asks before it stores a datapoint.
    """

    def test_may_establish_is_true_only_for_can_establish(self):
        self.assertTrue(may_establish('sec', 'revenue'))
        self.assertFalse(may_establish('sec', 'customers'))
        self.assertFalse(may_establish('news', 'revenue'))

    def test_corroborating_is_not_establishing(self):
        """
        The distinction the four roles exist for: a source may support a
        claim without being allowed to be its origin.
        """
        self.assertNotEqual(CAN_CORROBORATE, CAN_ESTABLISH)
        self.assertFalse(may_establish('crunchbase', 'employees'))
        self.assertEqual(capability_for('crunchbase', 'employees'), CAN_CORROBORATE)
