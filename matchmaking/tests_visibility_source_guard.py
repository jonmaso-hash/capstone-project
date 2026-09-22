"""
Every read of a controlled profile field must go through the visibility authority.

This guard should have shipped with per-field visibility. It was in the plan,
under Tests, and was never built -- so the surface inventory came instead from
a search capped at 25 results, and surfaces rendering controlled fields with no
check reached main: the anonymous founder bulletin board, the anonymous search
results page, the investor shortlist, the memo detail page and the application
detail page. Mutation testing could not catch them, because a mutation can only
kill tests that exist, and none of those surfaces had one.

So this test does not trust a list. It scans the source for every read of a
controlled field and requires each one to be either gated or named here with
the reason it is safe. A new surface that reads `raising_amount` fails the day
it is written, not the day someone notices it in production.

Two halves, because the reads live in two places:

    templates   line-level; a read must sit under a gate the view computed
                from the authority.
    Python      AST, keyed by (file, enclosing function). File-level would be
                too coarse -- accounts/views.py has a safe read (the owner's own
                dashboard) and a leak (the profile's founder_data_json) in
                different functions, and a file allowlist would have to wave
                both through or fail both.

A source scan rather than a render, deliberately: rendering proves the pages we
thought of; scanning proves there are none we did not.

Allowlist entries are not exemptions. Each states why a read is not a
disclosure -- internal computation that never returns a per-record value to a
user, the owner reading their own data, or a value already filtered upstream.
An entry that cannot state one of those is a leak with a label on it.
"""
import ast
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
TEMPLATES_DIR = ROOT / 'templates'

# The fields whose default visibility is below PUBLIC -- the ones a read can
# actually disclose. The descriptive fields default PUBLIC; a read of those is
# not a leak unless a founder raises the level, which the template gates cover.
FOUNDER_SENSITIVE = (
    'raising_amount', 'prior_amount_raised', 'current_revenue',
    'monthly_burn_rate', 'reason_for_capital', 'founder_name',
)

# Every controllable seller field -- including asking_price, which defaults
# PUBLIC. The founder list above scans only fields that default below PUBLIC;
# that is not good enough here, because the seller field most likely to be
# tightened is precisely the one that starts open. Leaving asking_price out
# would exempt the headline field of every listing from enforcement.
SELLER_SENSITIVE = ('asking_price', 'annual_revenue', 'ebitda', 'reason_for_sale')

SENSITIVE = FOUNDER_SENSITIVE + SELLER_SENSITIVE

TEMPLATE_READ = re.compile(r'\.(' + '|'.join(SENSITIVE) + r')\b')
TEMPLATE_GATES = ('visible_founder_fields', 'visible_seller_fields', 'visible_fields', 'raise_disclosed')
TEMPLATE_LOOKBACK = 12

TEMPLATE_ALLOWED = {
    'usersettings/edit_founder_profile.html':
        'the founder editing their own profile',
    'zelda_api/ic_memo.html':
        'values filtered to None by build_ic_memo_context(viewer=...) before render',
    # Orphaned: no view renders it and no template includes or extends it, so
    # its ungated financial fields reach no one. Enforced, not assumed -- see
    # test_orphaned_templates_stay_orphaned. Deleting it is the cleaner fix and
    # is left as a separate decision.
    'accounts/application_detail.html':
        'UNREACHABLE: referenced by no view, include or extends',
    'matchmaking/seller_dashboard.html':
        "the seller's own dashboard: their own asking price",
}

# Templates allowlisted only because nothing renders them. Each must stay
# unreferenced for its exemption to remain true.
ORPHANED_TEMPLATES = ('accounts/application_detail.html',)

PYTHON_ALLOWED = {
    # Internal computation: reads the value, never returns it per record.
    ('accounts/models.py', 'completion_percentage'):
        'profile completeness percentage; reports whether fields are filled, not their values',
    ('matchmaking/models.py', 'completion_percentage'):
        'profile completeness percentage; reports whether fields are filled, not their values',
    ('matchmaking/services/ai_engine.py', 'calculate_zelda_advantage'):
        'composite score; not invertible to any single input',
    ('matchmaking/signals.py', 'update_founder_vector'):
        'builds an embedding; the vector is never shown',
    ('zelda_api/intelligence_pipeline.py', '_build_structured_context'):
        "context for the founder's own analysis",
    ('zelda_api/entity_verification.py', '_describe'):
        'input to entity verification; not rendered to other users',
    # Owner reading their own profile.
    ('accounts/views.py', 'zelda_dashboard_view'):
        "the founder's own dashboard (request.user's profile)",
    ('pages/views.py', 'thank_you_view'):
        "greets the signed-in founder by their own name",
    # Already filtered upstream.
    ('accounts/views.py', '_zelda_advantage_payload'):
        'called only after profile() confirms all three figures are visible to the viewer',
    ('zelda_api/ic_memo.py', 'build_ic_memo_context'):
        'applies can_view_profile_field / PRIVATE stripping itself',
    ('zelda_api/views.py', '_match_reasons'):
        'each field read is guarded by can_view_profile_field for the viewing investor',
    # Matching. A hidden raise amount must not decide whether an investor can
    # discover a founder, so both read it only when it is visible to them.
    ('matchmaking/utils.py', 'passes_hard_filters'):
        'cache key carries the raise amount only when visible to the investor',
    ('matchmaking/utils.py', '_compute_hard_filters'):
        'reads the raise amount only when raise_visible is True for the investor',
    # Seller side.
    ('matchmaking/insights_engine.py', '_completion_percentage'):
        'profile completeness percentage; reports whether fields are filled, not their values',
    ('matchmaking/tasks.py', 'grade_buyer_prediction_snapshots'):
        'staff-only shadow prediction grading; never shown to users',
    ('matchmaking/match_components.py', 'deal_size_signal'):
        'reads the asking price only when _asking_price_visible for the buyer; hidden = unstated',
    ('matchmaking/views.py', 'export_acquisition_csv'):
        'each figure written only when in the listing\'s visible_fields for the requester',
    ('zelda_api/views.py', '_seller_to_result_dict'):
        'price gated by can_view_profile_field, has_cim by can_download_cim, for the viewer',
    # Unreachable today -- kept visible here rather than silently allowed, so
    # wiring either up forces a decision.
    ('matchmaking/models.py', 'to_foundry_envelope'):
        'UNREACHABLE: only ArticlePostSerializer calls to_foundry_envelope, on articles',
    ('matchmaking/signals.py', 'send_investor_match_email'):
        'UNREACHABLE: handle_connection_lifecycle is not registered, and Connection '
        'never takes status APPROVED',
}

# History: this list began failing on accounts/views.py::profile,
# zelda_api/views.py::_match_reasons and the two hard-filter functions. Each
# was closed rather than allowlisted; the entries above describe the gated
# versions, and the stale-entry test fails if any of them stops reading.

SKIP_DIRS = {'venv', 'node_modules', 'staticfiles', 'migrations', '.git', '__pycache__'}

# Module-level tables that hold controlled field NAMES as keys. An attribute
# scan cannot see a field used this way: Ask Zelda filtered on raising_amount
# and asking_price through `filter(**{f'{field}__lte': v})` with the field name
# drawn from a dict like these, and no `.raising_amount` read ever appeared --
# so a hidden amount was bisectable through a chat box while the attribute
# guard stayed green. Every such table must be named here with the reason its
# names cannot reach a requester-visible filter unguarded. A new one fails the
# guard the day it is written.
FIELD_NAME_TABLES = {
    ('matchmaking/models.py', 'NEW_PROFILE_FIELD_VISIBILITY'):
        'the founder policy itself: defines the fields, filters on none',
    ('matchmaking/models.py', 'SELLER_FIELD_VISIBILITY'):
        'the seller policy itself: defines the fields, filters on none',
    ('zelda_api/intelligence_pipeline.py', 'ASK_ZELDA_ALLOWED_FIELDS'):
        'consumed only by _apply_constraints_to_queryset, which narrows via '
        'restrict_queryset_for_field_filter before every filter',
    ('zelda_api/intelligence_pipeline.py', 'ASK_ZELDA_SELLER_ALLOWED_FIELDS'):
        'consumed only by _apply_constraints_to_queryset, which narrows via '
        'restrict_queryset_for_field_filter before every filter',
}


def _python_reads():
    """(relpath, function, field, line) for every Load of a sensitive attribute."""
    reads = []
    for path in ROOT.rglob('*.py'):
        if any(part in SKIP_DIRS for part in path.parts) or path.name.startswith('tests'):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
        except SyntaxError:
            continue
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and node.attr in SENSITIVE
                    and isinstance(node.ctx, ast.Load)):
                fn, cur = '<module>', node
                while cur in parents:
                    cur = parents[cur]
                    if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        fn = cur.name
                        break
                reads.append((rel, fn, node.attr, node.lineno))
    return reads


class ControlledFieldReadsGoThroughTheAuthority(SimpleTestCase):

    def test_every_template_read_is_gated(self):
        ungated = []
        for path in sorted(TEMPLATES_DIR.rglob('*.html')):
            rel = path.relative_to(TEMPLATES_DIR).as_posix()
            if rel in TEMPLATE_ALLOWED:
                continue
            lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
            for i, line in enumerate(lines):
                match = TEMPLATE_READ.search(line)
                if not match or re.search(r'\bform\.' + match.group(1) + r'\b', line):
                    continue
                window = '\n'.join(lines[max(0, i - TEMPLATE_LOOKBACK):i + 1])
                if not any(gate in window for gate in TEMPLATE_GATES):
                    ungated.append(f'{rel}:{i + 1}  .{match.group(1)}')
        self.assertEqual(ungated, [], _message('templates', ungated))

    def test_every_python_read_is_gated_or_explained(self):
        unexplained = sorted({
            f'{rel} :: {fn}  (.{field}, line {line})'
            for rel, fn, field, line in _python_reads()
            if (rel, fn) not in PYTHON_ALLOWED
        })
        self.assertEqual(unexplained, [], _message('Python', unexplained))

    def test_no_allowlist_entry_is_stale(self):
        """
        An entry for a function that no longer reads a controlled field is a
        standing exemption with nothing behind it; remove it so the list only
        ever describes real reads.
        """
        present = {(rel, fn) for rel, fn, _, _ in _python_reads()}
        stale = sorted(f'{rel} :: {fn}' for rel, fn in PYTHON_ALLOWED if (rel, fn) not in present)
        self.assertEqual(stale, [], 'allowlist entries matching no current read:\n  ' + '\n  '.join(stale))

    def test_orphaned_templates_stay_orphaned(self):
        """
        An UNREACHABLE exemption is only as good as the claim behind it. If any
        view, include or extends starts referencing one of these templates, its
        ungated fields become live and this fails -- so the exemption cannot
        silently outlive its reason.
        """
        for template in ORPHANED_TEMPLATES:
            name = template.rsplit('/', 1)[-1]
            referrers = [
                path.relative_to(ROOT).as_posix()
                for path in list(ROOT.rglob('*.py')) + list(TEMPLATES_DIR.rglob('*.html'))
                if not any(part in SKIP_DIRS for part in path.parts)
                and path.as_posix() != (TEMPLATES_DIR / template).as_posix()
                and not path.name.startswith('tests_visibility_source_guard')
                and name in path.read_text(encoding='utf-8', errors='ignore')
            ]
            self.assertEqual(referrers, [], f'{template} is referenced again, so its reads are live: {referrers}')

    def test_every_table_of_controlled_field_names_is_accounted_for(self):
        """
        The blind spot of the attribute scan, closed by looking for the names
        themselves: any module-level dict keyed by a controlled field.
        """
        found = set()
        for path in ROOT.rglob('*.py'):
            if any(part in SKIP_DIRS for part in path.parts) or path.name.startswith('tests'):
                continue
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
            except SyntaxError:
                continue
            for node in tree.body:
                if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
                    continue
                keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
                if keys & set(SENSITIVE):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            found.add((rel, target.id))
        unexplained = sorted(f'{rel} :: {name}' for rel, name in found - set(FIELD_NAME_TABLES))
        self.assertEqual(
            unexplained, [],
            'Tables keyed by controlled field names, not accounted for. If any '
            'feeds a filter, route it through restrict_queryset_for_field_filter '
            'and register it:\n  ' + '\n  '.join(unexplained),
        )
        stale = sorted(f'{rel} :: {name}' for rel, name in set(FIELD_NAME_TABLES) - found)
        self.assertEqual(stale, [], 'registered tables that no longer exist:\n  ' + '\n  '.join(stale))

    def test_ask_zelda_constraints_pass_the_boundary(self):
        """
        Pins the specific fix: the function every Ask Zelda filter runs through
        must call restrict_queryset_for_field_filter.
        """
        tree = ast.parse((ROOT / 'zelda_api' / 'intelligence_pipeline.py').read_text(encoding='utf-8'))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == '_apply_constraints_to_queryset')
        calls = {c.func.id for c in ast.walk(fn)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        self.assertIn('restrict_queryset_for_field_filter', calls)

    def test_the_scanners_see_what_they_guard(self):
        """
        Positive controls. A pattern or walker that matched nothing would pass
        both tests above against the entire project.
        """
        profile = (TEMPLATES_DIR / 'accounts' / 'profile.html').read_text(encoding='utf-8')
        self.assertTrue(TEMPLATE_READ.search(profile), 'template scanner matches nothing')
        self.assertTrue(
            any(rel == 'zelda_api/ic_memo.py' for rel, _, _, _ in _python_reads()),
            'Python scanner found no reads in a file known to contain them',
        )


def _message(where, items):
    return (
        f'Controlled profile fields read in {where} without the visibility '
        f'authority. Gate each one, or add it to the allowlist with the reason '
        f'it is not a disclosure:\n  ' + '\n  '.join(items)
    )
