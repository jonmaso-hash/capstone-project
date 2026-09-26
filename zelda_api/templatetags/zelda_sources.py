"""
Renders the shared evidence-source description into any surface that needs
it, so no template spells the sources out in its own words.

Five templates used to, and three of them drifted into asserting a source
that does not run without an API key it deliberately does not have. See
zelda_api/disclaimers.py.
"""
from django import template

from ..disclaimers import evidence_sources_sentence, verifying_source_names

register = template.Library()


@register.simple_tag
def zelda_evidence_sources():
    """The full sentence: what claims are checked against, and its limits."""
    return evidence_sources_sentence()


@register.simple_tag
def zelda_source_names():
    """Just the names, for surfaces that need them inline in their own prose."""
    names = verifying_source_names()
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"
