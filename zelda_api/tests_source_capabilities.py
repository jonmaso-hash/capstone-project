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
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

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


class TheGateBlocksAnUndeclaredWriteTests(TestCase):
    """
    The registry has to be load-bearing, not documentation. These run the real
    `create_observed_datapoints` and check what reached the database.

    A helper returning False proves nothing on its own: the previous PR
    shipped `engine_version` with neither create call setting it, and every
    unit test passed. So the assertion is on stored rows.
    """

    def setUp(self):
        from .vector_models import DocumentSource
        self.user = get_user_model().objects.create_user('cap_owner', password='x')
        self.document = DocumentSource.objects.create(
            filename='deck.pdf', source_entity='Subject Co', uploaded_by=self.user,
            document_type='pitch_deck', status='analyzed',
        )

    def write_with(self, source_type, extractors):
        """
        Runs the real writing path with one fake source whose extractors
        return whatever the test wants, so the only thing under test is
        whether the declared capability gates the write.
        """
        from .truth_delta_sources import DataSourceManager
        from .truth_delta_models import ObservedDatapoint

        class FakeIntegration:
            source_name = 'Fake'
            last_failure_reason = None

            def authenticate(self):
                return True

            def fetch_company_data(self, company_name, domain=None):
                return {'something': True}

            def extract_time_period(self, data):
                return 'FY2025'

        FakeIntegration.source_type = source_type
        for name, value in extractors.items():
            setattr(FakeIntegration, name, (lambda v: (lambda self, data: v))(value))

        with mock.patch.object(DataSourceManager, 'INTEGRATIONS', {source_type: FakeIntegration}):
            DataSourceManager.create_observed_datapoints(self.document, 'Subject Co')
        return set(
            ObservedDatapoint.objects.filter(document=self.document)
            .values_list('category', flat=True)
        )

    def test_a_declared_category_is_written(self):
        """Positive control. Without it, the test below could pass because
        nothing is ever written for any reason."""
        stored = self.write_with('sec', {
            'extract_revenue': (416_000_000_000.0, '$'),
            'extract_customers': None,
            'extract_employees': None,
            'extract_funding': None,
        })
        self.assertIn('revenue', stored)

    def test_an_undeclared_category_is_refused_even_when_extracted(self):
        """
        The gate. SEC declares `customers` unavailable, so a value arriving
        from that source must not become evidence -- however plausible the
        number is.
        """
        stored = self.write_with('sec', {
            'extract_revenue': None,
            'extract_customers': 218,
            'extract_employees': None,
            'extract_funding': None,
        })
        self.assertNotIn(
            'customers', stored,
            'a source wrote a datapoint for a category it is not allowed to establish',
        )

    def test_an_informational_source_cannot_write_at_all(self):
        """News supplies context. Even if an extractor started returning a
        number, it must not become a comparable observation."""
        stored = self.write_with('news', {
            'extract_revenue': (1_000_000.0, '$'),
            'extract_customers': 42,
            'extract_employees': 7,
            'extract_funding': 500_000.0,
        })
        self.assertEqual(stored, set())

    def test_a_corroborating_source_cannot_establish(self):
        """Crunchbase may support a claim, not originate one."""
        stored = self.write_with('crunchbase', {
            'extract_revenue': (1_000_000.0, '$'),
            'extract_customers': None,
            'extract_employees': 30,
            'extract_funding': None,
        })
        self.assertEqual(stored, set())
