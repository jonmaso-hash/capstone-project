"""
The blocking CI manifest cannot silently drift from the test tree.

On 2026-09-28 a gate reported OK at 1878 tests without ever running
zelda_api.tests_identity_chain_of_custody or
zelda_api.tests_verification_failure_is_visible. Two PRs had already merged
with their own new tests never executed by a local gate. Nothing failed --
the modules simply were not in the manifest, so there was nothing to fail.

What caught it was arithmetic: the test count did not move after 21 tests were
added. A green gate whose total did not change is evidence of a manifest
problem, not of a clean run -- and noticing that is not a process anyone
should have to repeat by hand.

The blocking job (`check` in .github/workflows/ci.yml) runs WHOLE APPS for
every local app except zelda_api, whose modules are enumerated one at a time
until its suite is rehabbed. So new test files are picked up automatically
everywhere except zelda_api, where each one must be wired in by hand -- and a
hand-maintained list is the thing that drifts.

TWO invariants, because the two sets have different origins. One detects
omissions from the filesystem; the other validates references originating in
the manifest, and neither can see what the other's inputs contain:

    unlisted_modules == INTENTIONAL_EXCLUSIONS
    listed_modules   <= existing_modules

Equality, not subset, on the first. With a subset, a name could be added to
the exclusions and a genuinely unwired module would pass -- the hole simply
moves from the manifest into the exclusion list, where nobody looks. Equality
means a new module forces either a ci.yml entry or a named exclusion with a
stated reason, and both appear as a deliberate decision in the diff.

The second invariant does NOT follow from the first: a ci.yml entry naming a
module that does not exist never enters either set, so the equality holds
while the reference rots.

WHY THIS TEST LIVES IN `pages`. `pages` is a whole-app entry, so this file is
discovered automatically. In zelda_api it would itself need a manifest entry,
and a manifest guard that can be omitted from the manifest guards nothing.

PHASE 0 ENDED when INTENTIONAL_EXCLUSIONS became empty: zelda_api.tests, the
last module kept out of the blocking job, was rehabbed (all 418 tests passing,
one process, 756 MB peak) and wired in. The set is now a gate rather than a
scoreboard -- a new exclusion fails the suite, so it cannot be added quietly.
"""
import io
import re
from pathlib import Path

import yaml
from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

CI_PATH = Path(settings.BASE_DIR) / '.github' / 'workflows' / 'ci.yml'

# The blocking job, and the step inside it that runs the suite.
BLOCKING_JOB = 'check'
TEST_STEP = re.compile(r'python\s+manage\.py\s+test\b')

# Modules deliberately left out of the blocking job, each with its reason.
# A module may only be here because running it would break the gate for a
# stated cause -- never because nobody got round to wiring it up. Empty since
# zelda_api.tests was wired in; adding an entry now fails
# test_the_blocking_manifest_has_no_exclusions below.
INTENTIONAL_EXCLUSIONS = {}


def blocking_test_labels(workflow=None):
    """
    The labels the blocking job passes to `manage.py test`, read from ci.yml
    itself -- never a copy kept in step with it by hand, which is precisely
    what drifted.

    Takes an optional parsed workflow so the parsing can be exercised against
    synthetic input. Checking it only against the live file means the branches
    that matter are whichever ones today's file happens to reach.
    """
    if workflow is None:
        workflow = yaml.safe_load(io.open(CI_PATH, encoding='utf-8').read())
    steps = workflow['jobs'][BLOCKING_JOB]['steps']
    commands = [
        step['run'] for step in steps
        if isinstance(step.get('run'), str) and TEST_STEP.search(step['run'])
    ]
    if len(commands) != 1:
        raise AssertionError(
            f'Expected exactly one test-running step in the {BLOCKING_JOB!r} job, '
            f'found {len(commands)}. The manifest guard cannot read a job it does '
            f'not recognise; update this test deliberately rather than leaving it '
            f'looking at the wrong step.')

    # Everything after the flags is a test label.
    tail = TEST_STEP.split(commands[0])[-1]
    return [
        token for token in tail.split()
        if token and not token.startswith('-')
    ]


def manifest_disagreements(listed, on_disk, exclusions):
    """
    The first invariant as a pure function: (missing, stale).

    `missing` -- on disk, not listed, not excluded: an unwired module.
    `stale`   -- excluded but not actually unlisted: either already wired, or
                 deleted. Dropping this half turns the equality into a subset
                 check, and then a name parked in the exclusions lets a
                 genuinely unwired module through. Separated out so BOTH
                 directions can be tested with inputs that contain the case --
                 against the live repo only one of them is ever non-empty.
    """
    unlisted = set(on_disk) - set(listed)
    return (sorted(unlisted - set(exclusions)), sorted(set(exclusions) - unlisted))


MIN_REASON = 40


def exclusions_without_reasons(exclusions, minimum=MIN_REASON):
    """
    Exclusions whose stated reason is too thin to distinguish deliberate debt
    from an oversight. "Nobody wired it up" is not a reason, and an exclusion
    list without this check quietly becomes a parking space.
    """
    return sorted(
        module for module, reason in exclusions.items()
        if len((reason or '').strip()) < minimum)


def _local_app_labels():
    """
    Apps that live in this repository, as opposed to Django's own and
    third-party packages. Derived from each app's path rather than from a
    hardcoded list, so a new app cannot be missed by this test either.
    """
    root = Path(settings.BASE_DIR).resolve()
    local = set()
    for config in apps.get_app_configs():
        try:
            path = Path(config.path).resolve()
        except (OSError, ValueError):
            continue
        if root in path.parents and '.venv' not in path.parts and 'venv' not in path.parts:
            local.add(config.label)
    return local


def _zelda_test_modules_on_disk():
    """Every zelda_api test module present in the working tree."""
    zelda = Path(settings.BASE_DIR) / 'zelda_api'
    return {f'zelda_api.{path.stem}' for path in zelda.glob('tests*.py')}


class TheGuardCanActuallyReadTheManifestTests(SimpleTestCase):
    """
    Positive controls. Every assertion in this file compares sets derived by
    parsing; if a parse silently returned nothing, the comparisons would pass
    for the worst possible reason -- which is the same failure this whole file
    exists to prevent, one level up.
    """

    def test_the_workflow_file_is_where_this_test_thinks_it_is(self):
        self.assertTrue(CI_PATH.is_file(), f'{CI_PATH} not found')

    def test_labels_are_parsed_from_the_blocking_job(self):
        labels = blocking_test_labels()
        self.assertGreater(len(labels), 25,
                           f'parsed only {len(labels)} labels from ci.yml; the guard is '
                           f'reading the wrong thing')

    def test_both_kinds_of_label_are_present(self):
        """
        The manifest mixes whole-app labels with dotted module labels. If only
        one kind parsed, half of this file's assertions would be vacuous.
        """
        labels = blocking_test_labels()
        self.assertTrue([l for l in labels if '.' not in l], 'no app labels parsed')
        self.assertTrue([l for l in labels if l.startswith('zelda_api.')],
                        'no zelda_api module labels parsed')

    def test_test_modules_are_discovered_on_disk(self):
        self.assertGreater(len(_zelda_test_modules_on_disk()), 20)

    def test_local_apps_are_distinguished_from_dependencies(self):
        local = _local_app_labels()
        self.assertIn('zelda_api', local)
        self.assertIn('pages', local)
        self.assertNotIn('admin', local)
        self.assertNotIn('rest_framework', local)


class TheManifestMatchesTheTestTreeTests(SimpleTestCase):

    def test_every_unlisted_module_is_a_named_intentional_exclusion(self):
        """
        INVARIANT 1, as equality. Catches an unwired module with no exclusion,
        an exclusion for a module that is in fact wired, and an exclusion for a
        module that has been deleted -- all three fall out of set equality
        rather than needing to be anticipated one at a time.
        """
        listed = {l for l in blocking_test_labels() if l.startswith('zelda_api.')}
        missing, stale = manifest_disagreements(
            listed, _zelda_test_modules_on_disk(), INTENTIONAL_EXCLUSIONS)
        self.assertEqual(
            (missing, stale), ([], []),
            'The blocking manifest and the test tree disagree.\n'
            f'  Not in ci.yml and not excluded (add to the check job): {missing}\n'
            f'  Excluded but already listed, or deleted (drop the exclusion): {stale}')

    def test_every_listed_module_exists(self):
        """
        INVARIANT 2. This does NOT follow from the equality above: a ci.yml
        entry naming a module that does not exist appears in neither set there,
        so the equality holds while the reference rots -- and `manage.py test`
        would fail the gate with a label error instead of a readable message.
        """
        listed = {l for l in blocking_test_labels() if l.startswith('zelda_api.')}
        self.assertEqual(
            sorted(listed - _zelda_test_modules_on_disk()), [],
            'ci.yml names zelda_api test modules that do not exist')

    def test_every_local_app_except_zelda_api_is_covered_wholesale(self):
        """
        The other half of the job's stated design. Whole-app entries are what
        make new test files outside zelda_api automatic; an app dropped from
        the manifest would take its entire suite out of the gate silently. A
        MISSPELLED app label fails loudly on its own (manage.py test rejects an
        unknown label), but an ABSENT one fails nothing -- so absence is what
        this checks.
        """
        listed_apps = {l for l in blocking_test_labels() if '.' not in l}
        expected = _local_app_labels() - {'zelda_api'}
        self.assertEqual(
            sorted(expected - listed_apps), [],
            'local apps are missing from the blocking job, so their whole '
            'suites do not gate merges')


class TheRemainingDebtIsCountableTests(SimpleTestCase):

    def test_every_exclusion_states_a_reason(self):
        """
        "Nobody wired it up" is not a reason. An exclusion has to say what
        would break, so that a future reader can tell deliberate debt from an
        oversight -- and so the list cannot quietly become a parking space.
        """
        self.assertEqual(
            exclusions_without_reasons(INTENTIONAL_EXCLUSIONS), [],
            'an exclusion is listed without a substantive reason')

    def test_the_blocking_manifest_has_no_exclusions(self):
        """
        Phase 0 is complete, so this is a gate and no longer a scoreboard: it
        used to tolerate one exclusion and report the count. Re-excluding a
        module is a decision to take a suite out of the merge gate, and it
        should have to say so by changing this test, not by adding a line to a
        dict that is easy to read past in a diff.
        """
        self.assertEqual(
            sorted(INTENTIONAL_EXCLUSIONS), [],
            'a module has been excluded from the blocking CI job again')


class TheContractLogicItselfIsTestedTests(SimpleTestCase):
    """
    The live repository exercises only one side of each check: no exclusion is
    currently stale, the one reason is long, and the parser works. So a
    mutation weakening any of those is a no-op against real data and survives
    while looking covered.

    Four mutations survived the first battery for exactly that reason. These
    tests feed the contract inputs that contain the case, so the LOGIC is
    verified rather than today's happy state.
    """

    ON_DISK = {'zelda_api.tests_a', 'zelda_api.tests_b', 'zelda_api.tests_c'}

    def test_an_unwired_module_is_reported_missing(self):
        missing, stale = manifest_disagreements(
            listed={'zelda_api.tests_a'}, on_disk=self.ON_DISK,
            exclusions={'zelda_api.tests_b': 'reason'})
        self.assertEqual(missing, ['zelda_api.tests_c'])
        self.assertEqual(stale, [])

    def test_an_exclusion_for_an_already_wired_module_is_reported_stale(self):
        """
        The half a subset check silently drops. Without it, a name parked in
        the exclusions lets a genuinely unwired module through.
        """
        missing, stale = manifest_disagreements(
            listed={'zelda_api.tests_a', 'zelda_api.tests_b', 'zelda_api.tests_c'},
            on_disk=self.ON_DISK,
            exclusions={'zelda_api.tests_a': 'reason'})
        self.assertEqual(stale, ['zelda_api.tests_a'])

    def test_an_exclusion_for_a_deleted_module_is_reported_stale(self):
        missing, stale = manifest_disagreements(
            listed=set(self.ON_DISK), on_disk=self.ON_DISK,
            exclusions={'zelda_api.tests_gone': 'reason'})
        self.assertEqual(stale, ['zelda_api.tests_gone'])

    def test_a_clean_manifest_reports_nothing(self):
        """Positive control: the function is capable of returning agreement."""
        missing, stale = manifest_disagreements(
            listed={'zelda_api.tests_a', 'zelda_api.tests_b'},
            on_disk=self.ON_DISK,
            exclusions={'zelda_api.tests_c': 'reason'})
        self.assertEqual((missing, stale), ([], []))

    def test_a_thin_reason_is_rejected(self):
        """
        Exercises the threshold that the one real exclusion's long reason makes
        unreachable. Without a short reason in the inputs, lowering the
        threshold is a no-op and the mutation survives -- it did.
        """
        self.assertEqual(
            exclusions_without_reasons({'zelda_api.tests_x': 'no time'}),
            ['zelda_api.tests_x'])

    def test_a_substantive_reason_is_accepted(self):
        """Paired positive: the check is capable of passing something."""
        self.assertEqual(
            exclusions_without_reasons({'zelda_api.tests_x': 'x' * (MIN_REASON + 1)}),
            [])

    def test_the_parser_reads_labels_out_of_a_workflow(self):
        """
        Exercises parsing against synthetic YAML, so an empty-returning parser
        fails here regardless of what the live ci.yml happens to contain.
        """
        workflow = {'jobs': {BLOCKING_JOB: {'steps': [
            {'name': 'Install', 'run': 'pip install -r requirements.txt'},
            {'name': 'Run test suite (excludes zelda_api)',
             'run': 'python manage.py test --verbosity=2 accounts pages zelda_api.tests_x'},
        ]}}}
        self.assertEqual(blocking_test_labels(workflow),
                         ['accounts', 'pages', 'zelda_api.tests_x'])

    def test_the_parser_refuses_a_workflow_it_cannot_recognise(self):
        """
        Two test steps, or none, means the guard is looking at the wrong thing.
        It must refuse rather than quietly return a partial list.
        """
        for steps in ([], [{'run': 'python manage.py test a'}, {'run': 'python manage.py test b'}]):
            with self.subTest(steps=len(steps)):
                with self.assertRaises(AssertionError):
                    blocking_test_labels({'jobs': {BLOCKING_JOB: {'steps': steps}}})
