"""
What Filed's answer for a jurisdiction is allowed to establish. Measured.

The provider began with five hard-coded trusted sources: the five states that
happened to have been probed. A sweep of all 51 US jurisdictions on 2026-10-02
found thirteen genuine registrars, thirty-seven jurisdictions answering a state
query with the IRS Exempt Organizations file, and Iowa returning nothing --
although Filed's own March post listed Iowa as covered.

So the knowledge lives in a fixture, `data/filed_state_authority.json`, and
this module only reads it. Two reasons that matters:

  A FIXTURE SHOWS DRIFT. Registrar coverage is an empirical capability that
  changes independently of this code. Iowa proves it moves in both directions.
  With `observed_at` on every entry, the next sweep produces a diff rather than
  silently replacing today's behaviour with permanent product truth.

  A TUPLE INVITES EDITING. 'Georgia Secretary of State' reads exactly like an
  accepted entry, and any name-shaped rule would have accepted all
  thirty-seven substitutions. Acceptance has to come from having looked.

AUTHORITY AND COVERAGE ARE SEPARATE AXES, which the Delaware probe forced.
`Delaware DOS` is a real registrar AND returns 51 records for a query that
returns 3,420 in Florida, despite Delaware having comparable real-world
registrations. A Delaware hit is real evidence; a Delaware miss says almost
nothing. One boolean cannot carry that, and Delaware is where startups
incorporate.

CAPABILITY IS PER REGISTRAR. Officer records exist in FL and TX and in none of
the other eleven. So a caller asks before reading officers, and omits the
dimension where it is unsupported: absence from a registrar that never
publishes officers is not evidence about a company.
"""
import functools
import io
import json
import os

STATE_REGISTRY = 'state_registry'
FEDERAL_SUBSTITUTION = 'federal_substitution'
NO_DATA = 'no_data'
UNKNOWN_SOURCE = 'unknown_source'

CLASSIFICATIONS = frozenset({STATE_REGISTRY, FEDERAL_SUBSTITUTION, NO_DATA,
                             UNKNOWN_SOURCE})

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'data',
                            'filed_state_authority.json')


@functools.lru_cache(maxsize=1)
def _document():
    with io.open(FIXTURE_PATH, encoding='utf-8') as handle:
        doc = json.load(handle)
    entries = doc.get('jurisdictions') or {}
    if not entries:
        raise ValueError(
            'filed_state_authority.json has no jurisdictions. An empty fixture '
            'would make every source unrecognised and every finding '
            "couldnt_check, which reads like a provider outage rather than a "
            'missing file.')
    for state, entry in entries.items():
        classification = entry.get('classification')
        if classification not in CLASSIFICATIONS:
            raise ValueError(
                'filed_state_authority.json: %s has classification %r, which is '
                'not one of %s. An unrecognised classification must not be '
                'treated as either accepted or refused.'
                % (state, classification, sorted(CLASSIFICATIONS)))
    return doc


def jurisdictions():
    """Every characterised jurisdiction code."""
    return set(_document()['jurisdictions'])


def _entry(state):
    """
    The entry for a jurisdiction. Raises for anything uncharacterised.

    Deliberately not a `.get`: a jurisdiction nobody measured is an omission,
    not a default, and defaulting is how five states became the whole truth.
    """
    try:
        return _document()['jurisdictions'][state]
    except (KeyError, TypeError):
        raise KeyError(
            'No Filed authority measurement for jurisdiction %r. Add it to '
            'zelda_api/data/filed_state_authority.json by MEASURING it -- '
            '"all 50 states" means every state code returns something, not '
            'that it is registration data.' % (state,))


def classification_for(state):
    return _entry(state)['classification']


def authority_for(state):
    """The registrar that answered for this jurisdiction, or None."""
    return _entry(state).get('authority_source')


def observed_at(state):
    return _entry(state).get('observed_at')


def coverage_for(state):
    """
    How completely this registrar is carried, or None when not a registry.

    'unmeasured' rather than 'broad' by default: only Delaware has been
    measured, and reading silence as breadth would invent evidence for twelve
    registrars.
    """
    entry = _entry(state)
    if entry['classification'] != STATE_REGISTRY:
        return None
    return entry.get('coverage') or 'unmeasured'


def coverage_note(state):
    return _entry(state).get('coverage_note') or ''


@functools.lru_cache(maxsize=1)
def accepted_sources():
    """Every source string measured to be a genuine state registrar."""
    return {entry['authority_source']
            for entry in _document()['jurisdictions'].values()
            if entry['classification'] == STATE_REGISTRY and entry.get('authority_source')}


def is_state_registration_source(source):
    """
    Whether this source may ground a statement about state registration.

    Membership in the measured set, never a pattern. Thirty-seven jurisdictions
    return a federal file in response to a state query, and a rule based on
    what a registrar's name looks like would have accepted every one of them.
    """
    return bool(source) and source in accepted_sources()


def publishes_officers(state):
    """Whether this registrar was measured to publish officer records."""
    try:
        return bool(_entry(state).get('publishes_officers'))
    except KeyError:
        return False


def publishes_agent(state):
    """Whether this registrar was measured to publish a registered agent."""
    try:
        return bool(_entry(state).get('publishes_agent'))
    except KeyError:
        return False
