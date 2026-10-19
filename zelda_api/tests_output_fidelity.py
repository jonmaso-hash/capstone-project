"""
Memo 98 (ManyChat, document 3140; graded PARTIAL PASS): three output defects the guards did not catch.

    UB-604  risk_assessment 1: "If the cumulative figure is being presented as a monthly figure, the key
            traction claim is materially overstated."  Page 10 states 500M messages with NO explicit interval;
            nothing admitted makes it cumulative, and two bounded facts cannot show an overstatement.
    NP-603  supported_points: "Pitch Deck Hunt lists $23.1M as the total amount raised [S4]" (no total in the
            admitted item) and "it establishes the fundraising narrative the company has put forward" (only
            Pitch Deck Hunt narrates C1/S4).
    NP-604  "how long the company can operate on the capital narrated as raised [S4]" and "runway against the
            $23.1M (per Pitch Deck Hunt) narrated as raised [S4]": historical funding used as the cash/runway
            denominator, in a statement and in a question.

The fixtures are memo 98's grounded payload as sent and its raw reply (data/funding_fidelity/memo98*.json,
from the committed evidence 0dd8e91). Memo 98 itself is not edited; these tests replay its reply.
"""
import json
import os
import re

from django.test import SimpleTestCase, TestCase

from .claim_context import guard_time_wording
from .funding_fidelity import funding_facts, guard_funding_fidelity
from .grounded_context import INSUFFICIENT, SELF_REPORTED, GroundedItem, SourceRef
from .memo_lists import memo_text

DATA = os.path.join(os.path.dirname(__file__), 'data', 'funding_fidelity')
REF = re.compile(r'\[([A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)\]')


def refs(text):
    return [r.strip() for group in REF.findall(text or '') for r in group.split(',')]


def memo98():
    with open(os.path.join(DATA, 'memo98.json'), encoding='utf-8') as f:
        data = json.load(f)
    return json.loads(re.search(r'\{.*\}', data['model_reply_text'], re.S).group(0)), data['stored']


def memo98_payload():
    with open(os.path.join(DATA, 'memo98_payload.json'), encoding='utf-8') as f:
        return json.load(f)['payload']


def items_from(payload):
    def source(s):
        return SourceRef(document_id=s.get('document_id'), page_number=s.get('page'), chunk_index=s.get('chunk'),
                         profile_field=s.get('profile_field', ''))
    return [GroundedItem(ref=i['ref'], kind=i['kind'], category=i['category'], statement=i['statement'],
                         status=i['status'], sources=tuple(source(s) for s in i['sources']),
                         confidence=i.get('confidence'), reason=i.get('reason', ''), dated='as_of' in i,
                         narrator=i.get('narrator', ''), source_context=i.get('source_context', ''),
                         as_of=i.get('as_of', ''), dates_not_as_of=tuple(i.get('dates_not_as_of', ())))
            for i in payload['items']]


def notes_from(payload):
    return tuple((n['kind'], tuple(n['refs']), n['note']) for n in payload.get('consistency_notes', []))


def replay(raw, items, notes):
    """The pipeline's post-generation steps, in order (intelligence_pipeline._generate_memo)."""
    from .basis_fidelity import basis_facts, guard_basis_wording
    allowed = {i.ref: i.time_wording_allowed for i in items if i.dated}
    facts = funding_facts(items, 'ManyChat')
    bfacts = basis_facts(items, notes)
    out, changes = {}, {}
    for key, value in raw.items():
        text = memo_text(value) if isinstance(value, (str, list, tuple, dict)) else value
        text, removed = guard_time_wording(text, allowed)
        text, fid = guard_funding_fidelity(text, facts)
        text, basis = guard_basis_wording(text, bfacts)
        out[key] = text
        if removed or fid or basis:
            changes[key] = list(removed or []) + list(fid) + list(basis)
    return out, changes


RISK_BEFORE = 'If the cumulative figure is being presented as a monthly figure, the key traction claim is materially overstated.'
RISK_AFTER = ('How the figure stated without an explicit interval relates to the monthly figure needs clarification '
              'before either is relied on.')
TOTAL_BEFORE = 'Pitch Deck Hunt lists $23.1M as the total amount raised [S4].'
TOTAL_AFTER = 'Pitch Deck Hunt lists $23.1M as the amount raised [S4].'
NARRATIVE_BEFORE = 'it establishes the fundraising narrative the company has put forward'
NARRATIVE_AFTER = 'it establishes the fundraising narrative Pitch Deck Hunt has put forward'
OPERATE_BEFORE = 'how long the company can operate on the capital narrated as raised [S4].'
OPERATE_AFTER = ('how long the company can operate — from the dated cash and burn alone, since the capital narrated '
                 'as raised is historical funding, not cash on hand [S4].')
RUNWAY_BEFORE = 'how does that translate to runway against the $23.1M (per Pitch Deck Hunt) narrated as raised [S4]?'
RUNWAY_AFTER = ('how does that translate to runway — from the dated cash and burn alone, since the $23.1M (per Pitch '
                'Deck Hunt) narrated as raised is historical funding, not cash on hand [S4]?')
CHANGED = {'risk_assessment', 'supported_points', 'what_would_change_the_picture', 'questions_for_management'}


class Memo98ReplayTests(SimpleTestCase):
    """The actual memo-98 reply through the pipeline's guards, with the new rules."""

    def setUp(self):
        self.raw, self.stored = memo98()
        self.payload = memo98_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)
        self.out, self.changes = replay(self.raw, self.items, self.notes)

    def test_the_fixture_is_memo_98_as_stored(self):
        # Without the new rules the replay is exactly memo 98 as stored (the evidence's own replay).
        for key in CHANGED:
            self.assertIn(key, self.stored)
        self.assertIn(RISK_BEFORE, self.stored['risk_assessment'])
        self.assertIn(TOTAL_BEFORE, self.stored['supported_points'])
        self.assertIn(NARRATIVE_BEFORE, self.stored['supported_points'])
        self.assertIn(OPERATE_BEFORE, self.stored['what_would_change_the_picture'])
        self.assertIn(RUNWAY_BEFORE, self.stored['questions_for_management'])
        self.assertEqual(self.notes[0][1], ('C3', 'C2'))

    def test_ub604_the_unsupported_cumulative_overstatement_is_replaced(self):
        risk = self.out['risk_assessment']
        self.assertNotIn(RISK_BEFORE, risk)
        self.assertIn(RISK_AFTER, risk)
        # The correct preceding sentences of item 1 stay as the model wrote them.
        self.assertIn("states 500M messages without an explicit interval [C3, S2], while page 12 states 500M "
                      "messages/month [C2, S3].", risk)
        self.assertIn('These use different measurement bases and cannot be compared or reconciled without '
                      'clarification from management.', risk)

    def test_np603_narrative_and_total_stay_with_the_narrator(self):
        points = self.out['supported_points']
        self.assertIn(TOTAL_AFTER, points)
        self.assertIn(NARRATIVE_AFTER, points)
        self.assertNotIn('the company has put forward', points)
        # The company's own bot statement is untouched.
        self.assertIn('The company states 140,000+ bots had been deployed', points)

    def test_np604_funding_is_not_the_runway_denominator(self):
        self.assertIn(OPERATE_AFTER, self.out['what_would_change_the_picture'])
        self.assertIn(RUNWAY_AFTER, self.out['questions_for_management'])

    def test_every_other_field_is_exactly_as_stored(self):
        for key, value in self.out.items():
            if key in self.stored and key not in CHANGED:
                self.assertEqual(value, self.stored[key], key)

    def test_valid_questions_and_scenarios_are_kept(self):
        q = self.out['questions_for_management']
        self.assertIn('Is the 500M messages figure a cumulative total or a monthly run rate, and which page of the '
                      'deck reflects the correct measurement basis [C2, C3, S2, S3]?', q)
        self.assertIn('Is a new fundraising round currently planned or in progress', q)
        self.assertIn('rather than a cumulative total', self.out['upside_scenario'])
        self.assertIn('is a cumulative total rather than monthly', self.out['downside_scenario'])
        self.assertIn('cumulative vs. monthly [C2, C3]', self.out['information_readiness'])
        self.assertIn('the difference between a cumulative total and a monthly rate is material', self.out['open_concerns'])

    def test_citations_are_preserved_in_order(self):
        for key, value in self.out.items():
            if isinstance(value, str) and key in self.stored:
                self.assertEqual(refs(value), refs(self.stored[key]), key)

    def test_a_second_pass_changes_nothing(self):
        again, changes = replay(self.out, self.items, self.notes)
        self.assertEqual(again, self.out)
        self.assertEqual(changes, {})

    def test_reversed_item_order_gives_the_same_output(self):
        reversed_out, _ = replay(self.raw, list(reversed(self.items)), self.notes)
        self.assertEqual(reversed_out, self.out)

    def test_only_the_expected_rules_fired(self):
        self.assertEqual(set(self.changes), CHANGED | {'open_concerns'})          # open_concerns: the existing attribution
        self.assertIn('basis_overstatement', self.changes['risk_assessment'])
        self.assertIn('narrator_narrative', self.changes['supported_points'])
        self.assertIn('unsupported_total', self.changes['supported_points'])
        self.assertIn('funding_not_runway', self.changes['what_would_change_the_picture'])
        self.assertIn('funding_not_runway', self.changes['questions_for_management'])


# --- the basis guard on its own ----------------------------------------------------------------

def _usage(ref, statement, page):
    return GroundedItem(ref=ref, kind='claim', category='usage', statement=statement, status=INSUFFICIENT,
                        sources=(SourceRef(document_id=1, page_number=page),), dated=True, as_of='not stated')


NOTE = ('measurement_basis', ('C3', 'C2'),
        'Page 10 states 500M messages without an explicit interval; page 12 states 500M messages/month. '
        'These use different measurement bases and need clarification before comparison.')


class BasisGuardTests(SimpleTestCase):

    def guard(self, text, cumulative=False, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = [_usage('C2', '500M messages/month', 12),
                 _usage('C3', '500M messages to date' if cumulative else '500M messages', 10)]
        return guard_basis_wording(text, basis_facts(items, notes))

    def test_the_definite_cumulative_referent_is_replaced_when_nothing_is_cumulative(self):
        text, changes = self.guard('The cumulative figure [C3] sits beside a monthly rate [C2].')
        self.assertEqual(text, 'The figure stated without an explicit interval [C3] sits beside a monthly rate [C2].')
        self.assertEqual(changes, ['basis_cumulative_referent'])

    def test_an_admitted_cumulative_fact_keeps_its_referent(self):
        text = 'The cumulative figure [C3] sits beside a monthly rate [C2].'
        self.assertEqual(self.guard(text, cumulative=True), (text, []))

    def test_an_overstatement_judgment_is_replaced_and_its_refs_kept(self):
        text, changes = self.guard('The monthly figure [C2] overstates the page-10 count [C3].')
        self.assertEqual(text, RISK_AFTER[:-1] + ' [C2] [C3].')
        self.assertEqual(changes, ['basis_overstatement'])

    def test_an_explicit_cumulative_fact_does_not_license_an_overstatement(self):
        # Worded from the admitted bases: here page 10's figure really is cumulative ("to date").
        text, changes = self.guard('If the cumulative messages total is shown as monthly, the claim is inflated.',
                                   cumulative=True)
        self.assertEqual(text, 'How the cumulative figure relates to the monthly figure needs clarification before '
                               'either is relied on.')
        self.assertEqual(changes, ['basis_overstatement'])

    def test_questions_scenarios_and_unrelated_metrics_are_kept(self):
        for text in ('Is the 500M messages figure a cumulative total or a monthly run rate [C2, C3]?',
                     'If the 500M messages figure is a cumulative total rather than monthly [C3 vs. C2], monthly '
                     'engagement would be lower.',
                     'The difference between a cumulative total and a monthly rate is material.',
                     'Revenue in the deck may be overstated.',
                     'Has the monthly figure been overstated?'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_no_note_no_rule(self):
        text = 'If the cumulative messages figure is presented as monthly, the claim is materially overstated.'
        self.assertEqual(self.guard(text, notes=()), (text, []))

    def test_idempotent(self):
        once, changes = self.guard('If the cumulative messages figure is presented as monthly, the claim is materially '
                                   'overstated.')
        self.assertEqual(changes, ['basis_overstatement'])
        self.assertEqual(self.guard(once), (once, []))

    def test_a_list_marker_and_numbering_are_kept(self):
        text, _ = self.guard('1. If the cumulative messages figure is presented as monthly, the claim is overstated.')
        self.assertEqual(text, '1. ' + RISK_AFTER)


# --- the funding rules on their own ------------------------------------------------------------

def _funding(ref, statement, narrator='Pitch Deck Hunt', kind='claim', as_of='not stated'):
    category = 'funding_raised' if kind == 'claim' else 'Funding'
    status = INSUFFICIENT if kind == 'claim' else SELF_REPORTED
    return GroundedItem(ref=ref, kind=kind, category=category, statement=statement, status=status,
                        sources=(SourceRef(document_id=1, page_number=2),), dated=True, narrator=narrator, as_of=as_of)


class FundingSourceAndRunwayTests(SimpleTestCase):

    def guard(self, text, items):
        return guard_funding_fidelity(text, funding_facts(items, 'ManyChat'))

    def narrated(self, statement='$23.1M raised'):
        return [_funding('C1', statement), _funding('S4', statement, kind='statement'), _usage('C3', '500M messages', 10)]

    def test_the_narrative_stays_with_the_narrator(self):
        text, changes = self.guard('It establishes the fundraising narrative the company has put forward [C1].',
                                   self.narrated())
        self.assertEqual(text, 'It establishes the fundraising narrative Pitch Deck Hunt has put forward [C1].')
        self.assertIn('narrator_narrative', changes)

    def test_company_owned_funding_and_mixed_refs_are_kept(self):
        own = [_funding('S9', '$2M raised', narrator='')]
        text = 'It reflects the fundraising narrative the company has put forward [S9].'
        self.assertEqual(self.guard(text, own)[0], text)
        mixed = 'The company states the traction and fundraising narrative it put forward [C1, C3].'
        self.assertEqual(self.guard(mixed, self.narrated())[0], mixed)

    def test_an_unsupported_total_is_dropped_and_a_stated_one_kept(self):
        text, changes = self.guard('Pitch Deck Hunt lists $23.1M as the total amount raised [S4].', self.narrated())
        self.assertEqual(text, 'Pitch Deck Hunt lists $23.1M as the amount raised [S4].')
        self.assertIn('unsupported_total', changes)
        stated = 'Pitch Deck Hunt lists $23.1M as the total amount raised to date [S4].'
        self.assertNotIn('unsupported_total', self.guard(stated, self.narrated('$23.1M raised to date'))[1])

    def test_funding_is_not_a_runway_denominator_even_with_dated_cash(self):
        dated = self.narrated() + [GroundedItem(
            ref='S7', kind='statement', category='Financial', statement='Cash balance of $2M', status=SELF_REPORTED,
            sources=(SourceRef(document_id=1, page_number=8),), dated=True, as_of='2026-06-30')]
        text, changes = self.guard('How long can the company operate on the $23.1M raised [S4]?', dated)
        # The existing attribution rule names the narrator of the uncredited amount first.
        self.assertEqual(text, 'How long can the company operate — from the dated cash and burn alone, since the '
                               '$23.1M raised (per Pitch Deck Hunt) is historical funding, not cash on hand [S4]?')
        self.assertIn('funding_not_runway', changes)

    def test_valid_cash_and_funding_questions_are_kept(self):
        for text in ('What is the current monthly burn and dated cash balance, and what runway do they support?',
                     'Did the $23.1M (per Pitch Deck Hunt) raise occur, when, and how were confirmed proceeds used [S4]?',
                     'What runway does the $2M cash balance [S7] support at the stated burn?',
                     'How long can the company operate on its $2M cash balance [S7], separate from the $23.1M '
                     '(per Pitch Deck Hunt) raised [S4]?'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text, self.narrated())[0], text)

    def test_idempotent(self):
        once, _ = self.guard('How does that translate to runway against the $23.1M narrated as raised [S4]?',
                             self.narrated())
        self.assertEqual(self.guard(once, self.narrated()), (once, []))


class PipelineAppliesTheRulesTests(TestCase):
    """The memo writer itself (intelligence_pipeline._generate_memo) stores the corrected memo 98 reply."""

    def test_the_stored_memo_carries_the_corrections(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo98_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo98_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo98()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertIn(RISK_AFTER, memo.risk_assessment)
        self.assertNotIn(RISK_BEFORE, memo.risk_assessment)
        self.assertIn(TOTAL_AFTER, memo.supported_points)
        self.assertIn(NARRATIVE_AFTER, memo.supported_points)
        self.assertIn(OPERATE_AFTER, memo.what_would_change_the_picture)
        self.assertIn(RUNWAY_AFTER, memo.questions_for_management)
        self.assertEqual(memo.upside_scenario, stored['upside_scenario'])
        self.assertEqual(memo.zelda_advantage, stored['zelda_advantage'])


# --- review of 2fb8530: containment ------------------------------------------------------------

def _revenue(ref='C8'):
    return GroundedItem(ref=ref, kind='claim', category='revenue', statement='$10M revenue', status=INSUFFICIENT,
                        sources=(SourceRef(document_id=1, page_number=7),), dated=True, as_of='not stated')


NOTE_BOTS = ('measurement_basis', ('C5', 'C6'),
             'Page 5 states 2M bots without an explicit interval; page 6 states 2M bots/day. '
             'These use different measurement bases and need clarification before comparison.')
NOTE_CUMULATIVE = ('measurement_basis', ('C7', 'C9'),
                   'Page 7 states 3M messages as a cumulative total; page 9 states 3M messages/week. '
                   'These use different measurement bases and need clarification before comparison.')
DAILY_CLARIFICATION = ('How the figure stated without an explicit interval relates to the daily figure needs '
                       'clarification before either is relied on')


def _pairs_items():
    return [_usage('C2', '500M messages/month', 12), _usage('C3', '500M messages', 10),
            _usage('C5', '2M bots', 5), _usage('C6', '2M bots/day', 6),
            _usage('C7', '3M messages to date', 7), _usage('C9', '3M messages/week', 9), _revenue()]


class BasisContainmentTests(SimpleTestCase):
    """P2-1 / P2-2: a basis note acts only on its own pair, with that pair's wording and permission."""

    def guard(self, text, items=None, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = items if items is not None else [_usage('C2', '500M messages/month', 12),
                                                 _usage('C3', '500M messages', 10), _revenue()]
        return guard_basis_wording(text, basis_facts(items, notes))

    # P2-1: an unrelated metric is never rewritten, and its citation never moves onto a usage clarification
    def test_unrelated_monthly_revenue_judgment_is_kept(self):
        for text in ('Monthly revenue is overstated [C8].', 'Monthly revenue may be overstated.',
                     'The monthly revenue figure [C8] looks inflated.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_unrelated_cumulative_referent_is_kept(self):
        for text in ('The cumulative figure for revenue is $10M [C8].', 'The cumulative total of revenue is unknown.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_mixed_sentence_keeps_its_unrelated_clause(self):
        text = 'The monthly message figure [C2] is overstated, and revenue is overstated too [C8].'
        out, _ = self.guard(text)
        self.assertIn('revenue is overstated too [C8]', out)
        self.assertFalse(re.search(r'relied on[^.]*\[C8\]', out))

    def test_the_memo_98_passage_still_resolves_by_its_paragraph(self):
        text = ("1. Measurement ambiguity: page 10 states 500M messages without an explicit interval [C3, S2], while "
                "page 12 states 500M messages/month [C2, S3]. These use different measurement bases. If the "
                "cumulative figure is being presented as a monthly figure, the key traction claim is materially "
                "overstated.\n2. Monthly revenue is overstated [C8].")
        items = [_usage('C2', '500M messages/month', 12), _usage('C3', '500M messages', 10), _revenue(),
                 GroundedItem(ref='S2', kind='statement', category='Traction', statement='500M messages',
                              status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=10),)),
                 GroundedItem(ref='S3', kind='statement', category='Traction', statement='500M messages/month',
                              status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=12),))]
        out, changes = self.guard(text, items=items)
        self.assertIn(RISK_AFTER, out)
        self.assertTrue(out.endswith('\n2. Monthly revenue is overstated [C8].'), out)
        self.assertEqual(changes, ['basis_overstatement'])

    # P2-2: per-pair wording, citations and cumulative permission
    def test_a_second_pair_gets_its_own_basis_wording(self):
        text = 'The daily bot figure [C6] is overstated compared with the bare bot count [C5].'
        out, changes = self.guard(text, items=_pairs_items(), notes=(NOTE, NOTE_BOTS, NOTE_CUMULATIVE))
        self.assertEqual(out, DAILY_CLARIFICATION + ' [C6] [C5].')
        self.assertEqual(changes, ['basis_overstatement'])

    def test_a_cumulative_fact_licenses_only_its_own_pair(self):
        notes = (NOTE, NOTE_BOTS, NOTE_CUMULATIVE)
        text = 'The cumulative figure [C3] sits beside a monthly rate [C2].'
        self.assertEqual(self.guard(text, items=_pairs_items(), notes=notes)[0],
                         'The figure stated without an explicit interval [C3] sits beside a monthly rate [C2].')
        own = 'The cumulative figure [C7] sits beside a weekly rate [C9].'
        self.assertEqual(self.guard(own, items=_pairs_items(), notes=notes), (own, []))

    def test_refs_from_two_pairs_or_an_ambiguous_uncited_sentence_are_left_alone(self):
        notes = (NOTE, NOTE_BOTS)
        for text in ('The monthly messages [C2] and daily bots [C6] look overstated.',
                     'If the cumulative figure is presented as monthly, the claim is materially overstated.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text, items=_pairs_items(), notes=notes), (text, []))

    def test_note_and_item_order_do_not_change_a_cited_sentence(self):
        text = 'The daily bot figure [C6] is overstated compared with the bare bot count [C5].'
        forward = self.guard(text, items=_pairs_items(), notes=(NOTE, NOTE_BOTS, NOTE_CUMULATIVE))
        backward = self.guard(text, items=list(reversed(_pairs_items())), notes=(NOTE_CUMULATIVE, NOTE_BOTS, NOTE))
        self.assertEqual(forward, backward)


class FundingTotalPerItemTests(SimpleTestCase):
    """P2-3: one source's stated total does not license another's."""

    def items(self, reverse=False):
        items = [_funding('C1', '$23.1M raised'), _funding('C5', '$10M raised in total', narrator='Other Source'),
                 _usage('C3', '500M messages', 10)]
        return list(reversed(items)) if reverse else items

    def guard(self, text, reverse=False):
        return guard_funding_fidelity(text, funding_facts(self.items(reverse), 'ManyChat'))

    def test_the_unsupported_total_is_dropped_beside_another_sources_total(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                text, changes = self.guard('Pitch Deck Hunt lists $23.1M as the total amount raised [C1].', reverse)
                self.assertEqual(text, 'Pitch Deck Hunt lists $23.1M as the amount raised [C1].')
                self.assertIn('unsupported_total', changes)

    def test_the_stated_total_is_kept(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                text = 'Other Source lists $10M as the total amount raised [C5].'
                self.assertNotIn('unsupported_total', self.guard(text, reverse)[1])
                self.assertIn('as the total amount raised [C5]', self.guard(text, reverse)[0])

    def test_separate_clauses_each_keep_their_own_support(self):
        text = ('Pitch Deck Hunt lists $23.1M as the total amount raised [C1], while Other Source lists $10M as the '
                'total amount raised [C5].')
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                out, _ = self.guard(text, reverse)
                self.assertIn('$23.1M as the amount raised [C1]', out)
                self.assertIn('$10M as the total amount raised [C5]', out)

    def test_an_uncited_figure_resolves_by_its_amount(self):
        out, _ = self.guard('Pitch Deck Hunt lists $23.1M as the total amount raised.')
        self.assertIn('$23.1M as the amount raised', out)


class PipelineContainmentTests(TestCase):
    """The memo writer with an active usage note: unrelated metrics and another pair keep their meaning."""

    def test_unrelated_and_second_pair_sentences_through_the_writer(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('containment_writer', password='x')
        doc = DocumentSource.objects.create(filename='c.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(_pairs_items()),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=(NOTE, NOTE_BOTS, NOTE_CUMULATIVE))
        raw = {'executive_summary': 'Monthly revenue is overstated [C8]. The cumulative figure for revenue is $10M [C8].',
               'risk_assessment': 'The daily bot figure [C6] is overstated compared with the bare bot count [C5].',
               'open_concerns': 'The cumulative figure [C3] sits beside a monthly rate [C2]. The cumulative figure [C7] '
                                'sits beside a weekly rate [C9].'}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.executive_summary, raw['executive_summary'])
        self.assertEqual(memo.risk_assessment, DAILY_CLARIFICATION + ' [C6] [C5].')
        self.assertEqual(memo.open_concerns, 'The figure stated without an explicit interval [C3] sits beside a monthly '
                                             'rate [C2]. The cumulative figure [C7] sits beside a weekly rate [C9].')


class BasisResolutionTests(SimpleTestCase):
    """How a sentence is tied to one pair: all its citations, its paragraph, never across list items."""

    def items(self):
        return _pairs_items() + [
            GroundedItem(ref='S2', kind='statement', category='Traction', statement='500M messages',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=10),)),
            GroundedItem(ref='S3', kind='statement', category='Traction', statement='500M messages/month',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=12),))]

    def guard(self, text):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(self.items(), (NOTE, NOTE_BOTS)))

    def test_a_pair_ref_beside_an_unrelated_ref_is_left_alone(self):
        text = 'The monthly figure [C2] and the other figure [C8] look overstated.'
        self.assertEqual(self.guard(text), (text, []))

    def test_with_two_pairs_the_paragraph_names_the_pair(self):
        text = ('1. Page 10 states 500M messages without an explicit interval [C3, S2], while page 12 states 500M '
                'messages/month [C2, S3]. If the cumulative figure is being presented as a monthly figure, the key '
                'traction claim is materially overstated.')
        out, changes = self.guard(text)
        self.assertTrue(out.endswith(RISK_AFTER), out)
        self.assertEqual(changes, ['basis_overstatement'])

    def test_a_new_list_item_does_not_inherit_the_pair(self):
        text = ('1. Page 10 states 500M messages without an explicit interval [C3, S2], while page 12 states 500M '
                'messages/month [C2, S3].\n2. If the cumulative figure is presented as monthly, the claim is '
                'materially overstated.')
        self.assertEqual(self.guard(text), (text, []))

    def test_a_resolved_sentence_not_about_the_bases_keeps_its_judgment(self):
        # One pair: an uncited sentence resolves to it, but says nothing about its bases.
        from .basis_fidelity import basis_facts, guard_basis_wording
        facts = basis_facts([_usage('C2', '500M messages/month', 12), _usage('C3', '500M messages', 10)], (NOTE,))
        text = 'The key traction claim may be overstated.'
        self.assertEqual(guard_basis_wording(text, facts), (text, []))


# --- review of 3e0fa33: a positive association, never a fallback ------------------------------------

STALE_ANTECEDENT = ('The message figures use different bases [C3, C2]. Revenue is reported as $10M. '
                    'The cumulative figure is overstated.')
MEMO_98_CONTIGUOUS = ("1. Measurement ambiguity on the core traction metric: the deck's page 10 ('Traction by Apr-16') "
                      "states 500M messages without an explicit interval [C3, S2], while page 12 states 500M "
                      "messages/month [C2, S3]. These use different measurement bases and cannot be compared or "
                      "reconciled without clarification from management. If the cumulative figure is being presented "
                      "as a monthly figure, the key traction claim is materially overstated.")


def _statement_aliases():
    return [GroundedItem(ref='S2', kind='statement', category='Traction', statement='500M messages',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=10),)),
            GroundedItem(ref='S3', kind='statement', category='Traction', statement='500M messages/month',
                         status=SELF_REPORTED, sources=(SourceRef(document_id=1, page_number=12),))]


class BasisAssociationTests(SimpleTestCase):
    """A sentence is acted on only with a defensible tie to the pair: its citations, its noun, or a contiguous
    discussion of that pair. No sole-pair fallback, and no antecedent across a different metric."""

    def guard(self, text, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_pairs_items() + _statement_aliases(), notes))

    # 1. Metrics no list names: the sole note is not every sentence's subject
    def test_a_metric_outside_any_list_is_kept_with_a_sole_note(self):
        for text in ('Monthly operating expenses are overstated.', 'Monthly churn is overstated.',
                     'The monthly retention figure looks inflated.', 'Weekly support tickets are overstated.',
                     'The cumulative figure is overstated.',
                     'If the cumulative figure is presented as monthly, the claim is materially overstated.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    # 2. A different metric between the pair and a definite referent ends the association
    def test_a_stale_antecedent_is_not_inherited_across_another_metric(self):
        self.assertEqual(self.guard(STALE_ANTECEDENT, notes=(NOTE, NOTE_BOTS)), (STALE_ANTECEDENT, []))

    def test_the_stale_antecedent_control(self):
        text = 'The cumulative figure is overstated.'
        self.assertEqual(self.guard(text, notes=(NOTE, NOTE_BOTS)), (text, []))

    def test_any_intervening_non_bridge_sentence_ends_the_association(self):
        for middle in ('Monthly operating expenses are overstated.', 'Churn is 3% [C8].',
                       'Customers renew annually.', 'Users grew 40% last year.'):
            text = f'The message figures use different bases [C3, C2]. {middle} The cumulative figure is overstated.'
            with self.subTest(middle=middle):
                out, _ = self.guard(text, notes=(NOTE, NOTE_BOTS))
                self.assertTrue(out.endswith(' The cumulative figure is overstated.'), out)

    def test_an_inherited_sentence_needs_a_figure_referent(self):
        text = 'The message figures use different bases [C3, C2]. Monthly operating expenses are overstated.'
        self.assertEqual(self.guard(text, notes=(NOTE, NOTE_BOTS)), (text, []))

    # Positive controls: contiguous discussion, citations, noun, statement aliases, explicit cumulative evidence
    def test_the_memo_98_contiguous_passage_is_still_corrected(self):
        for notes in ((NOTE,), (NOTE, NOTE_BOTS), (NOTE_BOTS, NOTE_CUMULATIVE, NOTE)):
            with self.subTest(notes=len(notes)):
                out, changes = self.guard(MEMO_98_CONTIGUOUS, notes=notes)
                self.assertTrue(out.endswith(' ' + RISK_AFTER), out)
                self.assertIn('[C3, S2]', out)
                self.assertEqual(changes, ['basis_overstatement'])

    def test_a_directly_following_referent_is_still_corrected(self):
        out, changes = self.guard('The message figures use different bases [C3, C2]. The cumulative figure is '
                                  'overstated.', notes=(NOTE, NOTE_BOTS))
        self.assertEqual(out, 'The message figures use different bases [C3, C2]. ' + RISK_AFTER)
        self.assertEqual(changes, ['basis_overstatement'])

    def test_cited_and_named_sentences_still_resolve(self):
        cited = 'If the cumulative figure [C3] is presented as monthly [C2], the claim is materially overstated.'
        self.assertEqual(self.guard(cited)[0], RISK_AFTER[:-1] + ' [C3] [C2].')
        named = 'If the cumulative messages figure is presented as monthly, the claim is materially overstated.'
        self.assertEqual(self.guard(named), (RISK_AFTER, ['basis_overstatement']))
        alias = 'The cumulative figure [S2] sits beside a monthly rate [S3].'
        self.assertEqual(self.guard(alias)[0], 'The figure stated without an explicit interval [S2] sits beside a '
                                               'monthly rate [S3].')

    def test_explicit_cumulative_evidence_and_questions_are_kept(self):
        own = 'The message figures use different bases [C7, C9]. The cumulative figure is overstated.'
        self.assertEqual(self.guard(own, notes=(NOTE_CUMULATIVE,))[0],
                         'The message figures use different bases [C7, C9]. How the cumulative figure relates to the '
                         'weekly figure needs clarification before either is relied on.')
        # A question is never turned into the judgment clarification (its referent may still be corrected).
        out, changes = self.guard('The message figures use different bases [C3, C2]. Is the cumulative figure '
                                  'overstated?')
        self.assertNotIn('basis_overstatement', changes)
        self.assertTrue(out.endswith(' overstated?'), out)


class PipelineAssociationTests(TestCase):
    """The memo writer: the two review counterexamples stay as written; memo 98's passage is still corrected."""

    def test_the_writer_keeps_unrelated_prose_and_corrects_the_contiguous_passage(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('association_writer', password='x')
        doc = DocumentSource.objects.create(filename='a.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test',
                                  items=tuple(_pairs_items() + _statement_aliases()), gaps=(), verification='complete',
                                  analysis_confidence=0.5, consistency_notes=(NOTE, NOTE_BOTS))
        raw = {'executive_summary': 'Monthly operating expenses are overstated.',
               'open_concerns': STALE_ANTECEDENT,
               'risk_assessment': MEMO_98_CONTIGUOUS}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.executive_summary, raw['executive_summary'])
        self.assertEqual(memo.open_concerns, STALE_ANTECEDENT)
        self.assertTrue(memo.risk_assessment.endswith(' ' + RISK_AFTER), memo.risk_assessment)


class BasisAssociationEdgeTests(SimpleTestCase):
    """Edges of the association found by the review-of-3e0fa33 mutation run (O3, C1, C6, A5 survived)."""

    def guard(self, text, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_pairs_items() + _statement_aliases(), notes))

    def test_a_named_sentence_not_about_the_bases_keeps_its_judgment(self):
        text = 'The messages count in the press release may be overstated.'
        self.assertEqual(self.guard(text), (text, []))

    def test_a_tied_sentence_that_also_names_another_metric_is_kept(self):
        for text in ('Monthly messages and monthly revenue are both overstated.',
                     'The monthly figure [C2] overstates revenue.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_new_paragraph_or_bullet_does_not_inherit(self):
        for sep in ('\n\n', '\n', '\n- '):
            text = (f'The message figures use different bases [C3, C2].{sep}The cumulative figure is overstated.')
            with self.subTest(sep=sep):
                self.assertEqual(self.guard(text, notes=(NOTE, NOTE_BOTS)), (text, []))

    def test_an_anaphoric_sentence_stating_a_new_figure_ends_the_association(self):
        text = 'The message figures use different bases [C3, C2]. They also report 40% growth. The cumulative figure is overstated.'
        self.assertEqual(self.guard(text, notes=(NOTE, NOTE_BOTS)), (text, []))


# --- review of c297ec3: a bridge is a complete, known measurement-basis sentence --------------------

NON_BRIDGES = ('This revenue figure is unaudited.', 'These operating expenses are unaudited.',
               'These use different measurement bases for expenses.')


def _with_middle(middle):
    return f'The message figures use different bases [C3, C2]. {middle} The cumulative figure is overstated.'


class BasisBridgeTests(SimpleTestCase):
    """An anaphoric opener is not a bridge: only the whole known basis sentence continues the pair."""

    def guard(self, text, notes=(NOTE, NOTE_BOTS)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_pairs_items() + _statement_aliases(), notes))

    def test_an_anaphoric_sentence_naming_another_metric_ends_the_association(self):
        for middle in NON_BRIDGES:
            text = _with_middle(middle)
            with self.subTest(middle=middle):
                self.assertEqual(self.guard(text), (text, []))

    def test_the_known_bridges_continue_the_pair(self):
        for middle in ('These use different measurement bases.',
                       'These use different measurement bases and need clarification before comparison.',
                       'These use different measurement bases and cannot be compared or reconciled without '
                       'clarification from management.'):
            with self.subTest(middle=middle):
                out, changes = self.guard(_with_middle(middle))
                self.assertEqual(out, f'The message figures use different bases [C3, C2]. {middle} {RISK_AFTER}')
                self.assertEqual(changes, ['basis_overstatement'])

    def test_direct_cited_and_named_paths_are_unaffected(self):
        direct = 'The message figures use different bases [C3, C2]. The cumulative figure is overstated.'
        self.assertEqual(self.guard(direct)[0], 'The message figures use different bases [C3, C2]. ' + RISK_AFTER)
        cited = 'If the cumulative figure [C3] is presented as monthly [C2], the claim is materially overstated.'
        self.assertEqual(self.guard(cited)[0], RISK_AFTER[:-1] + ' [C3] [C2].')
        named = 'If the cumulative messages figure is presented as monthly, the claim is materially overstated.'
        self.assertEqual(self.guard(named), (RISK_AFTER, ['basis_overstatement']))


class PipelineBridgeTests(TestCase):
    """The memo writer: a non-bridge between the pair and the referent leaves the referent as written."""

    def test_the_writer_keeps_the_referent_after_a_non_bridge(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('bridge_writer', password='x')
        doc = DocumentSource.objects.create(filename='b.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test',
                                  items=tuple(_pairs_items() + _statement_aliases()), gaps=(), verification='complete',
                                  analysis_confidence=0.5, consistency_notes=(NOTE, NOTE_BOTS))
        raw = {'executive_summary': _with_middle(NON_BRIDGES[0]),
               'open_concerns': _with_middle(NON_BRIDGES[1]),
               'upside_scenario': _with_middle(NON_BRIDGES[2]),
               'risk_assessment': MEMO_98_CONTIGUOUS}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.executive_summary, raw['executive_summary'])
        self.assertEqual(memo.open_concerns, raw['open_concerns'])
        self.assertEqual(memo.upside_scenario, raw['upside_scenario'])
        self.assertTrue(memo.risk_assessment.endswith(' ' + RISK_AFTER), memo.risk_assessment)


# --- memo 99 (document 3141; graded PARTIAL PASS): OF-704 label, OF-705 source location --------------------
#
#     OF-704  open_concerns: "Measurement-basis contradiction in the headline usage metric: ... [C2, C3]". The pair
#             supports an ambiguity to clarify, not a contradiction.
#     OF-705  supported_points: "either 500M total or 500M/month ... on the same traction slide [S2, S3]" and
#             business_model_analysis: "... on a slide headed 'Traction by Apr-16' [S1, S2, S3]". S3 is page 12,
#             with no slide context; page 10's interval is unspecified, not a total.
#
# The fixtures are memo 99's payload as sent and its raw reply (data/funding_fidelity/memo99*.json, from the
# committed evidence d821cca). Memo 99 itself is not edited; these tests replay its reply.

def memo99():
    with open(os.path.join(DATA, 'memo99.json'), encoding='utf-8') as f:
        data = json.load(f)
    return json.loads(re.search(r'\{.*\}', data['model_reply_text'], re.S).group(0)), data['stored']


def memo99_payload():
    with open(os.path.join(DATA, 'memo99_payload.json'), encoding='utf-8') as f:
        return json.load(f)['payload']


OPEN_BEFORE = ("- Measurement-basis contradiction in the headline usage metric: the deck states '500M messages' without "
               "an interval on page 10 and '500M messages/month' on page 12 [C2, C3].")
OPEN_AFTER = OPEN_BEFORE.replace('Measurement-basis contradiction', 'Measurement-basis ambiguity')
POINT_BEFORE = ("- The company states a messages figure of either 500M total or 500M/month (measurement basis unresolved; "
                "see open concerns) on the same traction slide [S2, S3], suggesting material message volume on the "
                "platform at that time.")
# Review of d30a022: each fact under its own metric, basis, page and context; the relation stays a clarification.
CLARIFICATION_99 = ("(how the figure stated without an explicit interval relates to the monthly figure needs clarification "
                    "before either is relied on)")
POINT_AFTER = ("- The company states 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', "
               "and separately 500M messages/month [S3] on page 12 " + CLARIFICATION_99 + ", suggesting material message "
               "volume on the platform at that time.")
MODEL_BEFORE = ("the company states 140,000+ bots and 500M messages (measurement basis questioned; see open concerns) on a "
                "slide headed 'Traction by Apr-16' [S1, S2, S3] — which confirm")
MODEL_AFTER = ("the company states 140 000+ bots [S1] and 500M messages with no explicit interval [S2] on page 10, under "
               "'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 " + CLARIFICATION_99 +
               " — which confirm")
CHANGED_99 = {'open_concerns', 'supported_points', 'business_model_analysis'}
# The merged funding guard's accepted live edits on memo 99 (evidence 09e), unchanged by this correction.
FUNDING_99 = {'risk_assessment', 'information_readiness', 'what_would_change_the_picture', 'downside_scenario',
              'questions_for_management'}
RUN = re.compile(r"^(?P<facts>.+) on page (?P<page>\d+)(?:, under '(?P<ctx>[^']+)')?$")
FACT = re.compile(r"^(?P<fact>.+) \[(?P<ref>[A-Z]\d+)\]$")


def placed_facts(text):
    """(fact, ref, page, context) for every fact the location repair emitted, in order."""
    out = []
    for body in re.findall(r"states (.+?) \(how the figure stated", text):
        for run in body.split(', and separately '):
            m = RUN.match(run)
            assert m, run
            for fact in m.group('facts').split(' and '):
                f = FACT.match(fact)
                assert f, fact
                out.append((f.group('fact'), f.group('ref'), int(m.group('page')), m.group('ctx')))
    return out


def expected_facts(payload):
    """Each ref's own statement, page and context; the note's no-interval side (and statements repeating it on its
    page) carry "with no explicit interval"."""
    items = {i['ref']: i for i in payload['items']}
    note = payload['consistency_notes'][0]['refs']
    bare = next(items[r] for r in note if '/' not in items[r]['statement'])
    out = {}
    for ref, i in items.items():
        fact = i['statement']
        if fact == bare['statement'] and i['sources'][0].get('page') == bare['sources'][0].get('page'):
            fact += ' with no explicit interval'
        out[ref] = (fact, i['sources'][0].get('page'), i.get('source_context'))
    return out


class Memo99ReplayTests(SimpleTestCase):
    """The actual memo-99 reply through the pipeline's guards: only the two graded shapes change."""

    def setUp(self):
        self.raw, self.stored = memo99()
        self.payload = memo99_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)
        self.out, self.changes = replay(self.raw, self.items, self.notes)

    def test_the_fixture_is_memo_99_as_stored(self):
        self.assertIn(OPEN_BEFORE, self.stored['open_concerns'])
        self.assertIn(POINT_BEFORE, self.stored['supported_points'])
        self.assertIn(MODEL_BEFORE, self.stored['business_model_analysis'])
        self.assertEqual(self.notes[0][1], ('C3', 'C2'))
        sources = {i['ref']: (i['sources'][0].get('page'), i.get('source_context')) for i in self.payload['items']}
        self.assertEqual(sources['S2'], (10, 'Traction by Apr-16'))
        self.assertEqual(sources['S3'], (12, None))

    def test_of704_the_basis_pair_is_an_ambiguity_not_a_contradiction(self):
        concerns = self.out['open_concerns']
        self.assertTrue(concerns.startswith(OPEN_AFTER), concerns)
        self.assertNotIn('contradiction', concerns.split('\n')[0])
        # The model's own qualification and the clarification request stay.
        self.assertIn('These are not necessarily the same figure; until management clarifies whether 500M is a '
                      'cumulative total or a monthly rate', concerns)
        # Its other bullets are as stored, including the funding one ("establish or contradict it").
        self.assertEqual(concerns.split('\n')[1:], self.stored['open_concerns'].split('\n')[1:])

    def test_of705_each_fact_keeps_its_own_page_and_context(self):
        self.assertIn(POINT_AFTER, self.out['supported_points'])
        self.assertIn(MODEL_AFTER, self.out['business_model_analysis'])
        for key in ('supported_points', 'business_model_analysis'):
            self.assertNotIn('same traction slide', self.out[key])
            self.assertNotIn('500M total', self.out[key])

    def test_every_placed_citation_supports_its_page_and_context(self):
        # Review of d30a022: metric, basis, page, context and ref together, for every emitted fact.
        expected = expected_facts(self.payload)
        seen = {}
        for key in ('supported_points', 'business_model_analysis'):
            seen[key] = placed_facts(self.out[key])
            for fact, ref, page, context in seen[key]:
                self.assertEqual((fact, page, context), expected[ref], (key, ref))
        self.assertEqual([r for _, r, _, _ in seen['supported_points']], ['S2', 'S3'])
        self.assertEqual([r for _, r, _, _ in seen['business_model_analysis']], ['S1', 'S2', 'S3'])
        # No bots fact and no dated heading under page 12; no cumulative reading invented.
        for key, facts in seen.items():
            for fact, ref, page, context in facts:
                if page == 12:
                    self.assertIsNone(context, key)
                    self.assertNotIn('bots', fact, key)
            self.assertNotIn('cumulative', self.out[key].split(' (how the figure')[0].split('states ', 1)[1], key)

    def test_every_other_field_is_exactly_as_stored(self):
        for key, value in self.out.items():
            if key in self.stored and key not in CHANGED_99:
                self.assertEqual(value, self.stored[key], key)

    def test_citations_are_preserved_in_order(self):
        for key, value in self.out.items():
            if isinstance(value, str) and key in self.stored:
                self.assertEqual(refs(value), refs(self.stored[key]), key)

    def test_correct_shared_context_and_questions_are_kept(self):
        self.assertIn("appearing in a slide headed 'Traction by Apr-16' [S1, S2]", self.out['executive_summary'])
        self.assertIn("on a slide headed 'Traction by Apr-16' [S1, S2]", self.out['base_scenario'])
        self.assertIn("(slide headed 'Traction by Apr-16') [S1, S2]", self.out['information_readiness'])
        self.assertIn("Is the '500M messages' figure on the traction slide a cumulative total or a monthly rate?",
                      self.out['questions_for_management'])
        self.assertIn('(total vs. per month) [C2, C3]', self.out['information_readiness'])
        self.assertIn('internal inconsistency', self.out['zelda_advantage'])           # P3, outside this scope
        self.assertIn("page 10 (slide headed 'Traction by Apr-16') [C3, S2] and '500M messages/month' on page 12 "
                      "[C2, S3]", self.out['risk_assessment'])

    def test_a_second_pass_changes_nothing(self):
        again, changes = replay(self.out, self.items, self.notes)
        self.assertEqual(again, self.out)
        self.assertEqual(changes, {})

    def test_reversed_item_order_gives_the_same_output(self):
        reversed_out, _ = replay(self.raw, list(reversed(self.items)), self.notes)
        self.assertEqual(reversed_out, self.out)

    def test_only_the_expected_rules_fired(self):
        self.assertEqual(set(self.changes), CHANGED_99 | FUNDING_99)
        self.assertEqual(self.changes['open_concerns'], ['basis_contradiction_label'])
        self.assertEqual(self.changes['supported_points'], ['basis_source_location'])
        self.assertEqual(self.changes['business_model_analysis'], ['basis_source_location'])
        for key in FUNDING_99:
            self.assertFalse([c for c in self.changes[key] if c.startswith('basis_')], key)


class Memo99StoredSectionsTests(SimpleTestCase):
    """The stored memo-99 text (after the merged guards) through the basis guard: the same three repairs."""

    def test_the_stored_sections_get_the_same_repairs(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        payload = memo99_payload()
        facts = basis_facts(items_from(payload), notes_from(payload))
        _, stored = memo99()
        out = {key: guard_basis_wording(value, facts)[0] for key, value in stored.items()}
        self.assertTrue(out['open_concerns'].startswith(OPEN_AFTER))
        self.assertIn(POINT_AFTER, out['supported_points'])
        self.assertIn(MODEL_AFTER, out['business_model_analysis'])
        self.assertEqual({k for k in stored if out[k] != stored[k]}, CHANGED_99)


def _statement(ref, statement, page, context=''):
    return GroundedItem(ref=ref, kind='statement', category='Traction', statement=statement, status=SELF_REPORTED,
                        sources=(SourceRef(document_id=1, page_number=page),), source_context=context)


def _context_items(status=INSUFFICIENT):
    return [GroundedItem(ref='C2', kind='claim', category='usage', statement='500M messages/month', status=status,
                         sources=(SourceRef(document_id=1, page_number=12),), dated=True, as_of='not stated'),
            GroundedItem(ref='C3', kind='claim', category='usage', statement='500M messages', status=INSUFFICIENT,
                         sources=(SourceRef(document_id=1, page_number=10),), dated=True, as_of='not stated',
                         source_context='Traction by Apr-16'),
            _statement('S1', '140 000+ bots', 10, 'Traction by Apr-16'),
            _statement('S2', '500M messages', 10, 'Traction by Apr-16'),
            _statement('S3', '500M messages/month', 12),
            _statement('S5', '2M downloads', 4), _statement('S6', '1M downloads', 5),
            _revenue()]


class BasisLabelTests(SimpleTestCase):
    """OF-704: a basis pair supports an ambiguity to clarify; other contradictions and negations are kept."""

    def guard(self, text, status=INSUFFICIENT):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(status), (NOTE,)))

    def test_the_pair_label_becomes_an_ambiguity(self):
        cases = {
            'There is a contradiction between page 10 and page 12 [C3, C2].':
                'There is an ambiguity between page 10 and page 12 [C3, C2].',
            'The two message figures are contradictory [C3, C2].': 'The two message figures are ambiguous [C3, C2].',
            'Contradictions in the messages metric need management review [S2, S3].':
                'Ambiguities in the messages metric need management review [S2, S3].',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (expected, ['basis_contradiction_label']))

    def test_negations_questions_and_other_words_are_kept(self):
        for text in ('There is no contradiction between page 10 and page 12 [C3, C2].',
                     'The message figures are not contradictory [C3, C2].',
                     'Rather than a contradiction, the messages metric needs clarification [C3, C2].',
                     'Is this a contradiction between the message figures [C3, C2]?',
                     'This inconsistency between the message figures needs clarification [C3, C2].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_unrelated_and_external_contradictions_are_kept(self):
        for text in ('Revenue shows a contradiction [C8].', 'The download counts are a contradiction [S5, S6].',
                     'A contradiction between revenue and messages [C8, C2] needs review.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        # A pair item Truth Delta actually found contradicted keeps the word.
        external = 'There is a contradiction between page 10 and page 12 [C3, C2].'
        from .grounded_context import CONTRADICTED
        self.assertEqual(self.guard(external, status=CONTRADICTED), (external, []))


class BasisSourceLocationTests(SimpleTestCase):
    """OF-705: a shared-slide phrase over refs from different pages or contexts places each under its own source."""

    def guard(self, text, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(), notes))

    def test_a_cross_page_group_is_placed_by_its_own_sources(self):
        cases = {
            'The figures appear on the same slide [S2, S3].':
                "The deck states 500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and "
                "separately 500M messages/month [S3] on page 12 " + CLARIFICATION_99 + ".",
            "Bots and messages are on a slide headed 'Traction by Apr-16' [S1, S2, S3].":
                "The deck states 140 000+ bots [S1] and 500M messages with no explicit interval [S2] on page 10, under "
                "'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 " + CLARIFICATION_99 + ".",
            "Both message figures appear in the slide headed 'Traction by Apr-16' [S3, S2].":
                "The deck states 500M messages/month [S3] on page 12, and separately 500M messages with no explicit "
                "interval [S2] on page 10, under 'Traction by Apr-16' " + CLARIFICATION_99 + ".",
            "The company states 140,000+ bots and 500M messages on the same slide [S1, S3].":
                "The company states 140 000+ bots [S1] on page 10, under 'Traction by Apr-16', and separately 500M "
                "messages/month [S3] on page 12.",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (expected, ['basis_source_location']))

    def test_correctly_shared_or_separately_placed_figures_are_kept(self):
        for text in ("The company states 140,000+ bots and 500M messages on a slide headed 'Traction by Apr-16' [S1, S2].",
                     'Page 10 states 500M messages [C3, S2], while page 12 states 500M messages/month [C2, S3].',
                     'The figures appear on the same slide [S2].',
                     'Is the 500M messages figure on the same slide as the monthly figure [S2, S3]?',
                     'The download counts appear on the same slide [S5, S6].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_without_a_basis_note_nothing_is_placed(self):
        text = 'The figures appear on the same slide [S2, S3].'
        self.assertEqual(self.guard(text, notes=()), (text, []))


class BasisUnspecifiedTotalTests(SimpleTestCase):
    """OF-705: the pair's unspecified-interval figure is not a stated total; a stated cumulative fact keeps it."""

    def guard(self, text, items=None, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items or _context_items(), notes))

    def test_the_unspecified_figure_is_not_called_a_total(self):
        self.assertEqual(self.guard('The deck gives either 500M total or 500M/month [S2, S3].'),
                         ('The deck gives either 500M with no stated interval or 500M/month [S2, S3].',
                          ['basis_unspecified_total']))

    def test_conditional_totals_and_a_stated_cumulative_fact_are_kept(self):
        for text in ('If 500M is a cumulative total rather than a monthly rate [C3, C2], usage is lower.',
                     'Measurement basis of the 500M messages figure (total vs. per month) [C2, C3].',
                     'Revenue was 500M total [C8].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        items = [_usage('C9', '3M messages/week', 9), _usage('C7', '3M messages to date', 7)]
        own = 'The deck gives 3M total or 3M/week [C7, C9].'
        self.assertEqual(self.guard(own, items=items, notes=(NOTE_CUMULATIVE,)), (own, []))


class PipelineMemo99Tests(TestCase):
    """The memo writer itself (intelligence_pipeline._generate_memo) stores the repaired memo-99 reply."""

    def test_the_stored_memo_carries_the_repairs(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo99_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo99_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo99()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertTrue(memo.open_concerns.startswith(OPEN_AFTER), memo.open_concerns)
        self.assertIn(POINT_AFTER, memo.supported_points)
        self.assertIn(MODEL_AFTER, memo.business_model_analysis)
        for key in ('executive_summary', 'risk_assessment', 'what_would_change_the_picture', 'zelda_advantage',
                    'questions_for_management', 'downside_scenario'):
            self.assertEqual(getattr(memo, key), stored[key], key)


class Of705MutationControlTests(SimpleTestCase):
    """Controls added after the first mutation run (T2 and P5 survived: the earlier controls never reached the rule)."""

    def guard(self, text, items, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items, notes))

    def test_a_pair_with_a_stated_cumulative_side_keeps_its_total(self):
        # One side states a cumulative fact ("to date"), the other the same figure with no interval: "3M total"
        # may be the stated cumulative figure, so it is kept.
        items = [_usage('C7', '3M messages to date', 7), _usage('C10', '3M messages', 8)]
        text = 'The deck gives 3M total [C7, C10].'
        self.assertEqual(self.guard(text, items, notes=(('measurement_basis', ('C10', 'C7'), 'note'),)), (text, []))

    def test_a_shared_place_question_is_kept(self):
        text = 'Are both message figures shown on the same slide [S2, S3]?'
        self.assertEqual(self.guard(text, _context_items()), (text, []))


# --- review of d30a022: the reviewer's probes ------------------------------------------------------------

class ReviewD30a022ProbeTests(SimpleTestCase):
    """Observed outputs at 979bf49 that the review required to stay as written, or to keep citation order."""

    def guard(self, text):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(), (NOTE,)))

    def test_denials_and_insufficient_evidence_are_kept(self):
        for text in ('The messages cannot establish a contradiction [C3, C2].',
                     'The message figures provide insufficient evidence to establish a contradiction [C3, C2].',
                     'Nothing here shows a contradiction between the message figures [C3, C2].',
                     'The deck is unable to show a contradiction [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_conditional_scenarios_are_kept_by_the_new_rules(self):
        for text in ('If the message figures are contradictory [C3, C2], management should explain the difference.',
                     'If 500M total is the correct interpretation [S2, S3], management should explain the reporting window.',
                     'If the figures appear on the same slide [S2, S3], management should say which is current.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_an_affirmative_label_after_a_condition_clause_ends_is_still_repaired(self):
        # The condition covers its own clause; memo 99's affirmative heading form is still repaired elsewhere.
        self.assertEqual(self.guard('There is a contradiction between page 10 and page 12 [C3, C2].')[1],
                         ['basis_contradiction_label'])

    def test_the_accepted_memo_98_conditional_overstatement_is_still_corrected(self):
        out, changes = self.guard('If the cumulative figure [C3] is presented as monthly [C2], the claim is materially '
                                  'overstated.')
        self.assertEqual(out, RISK_AFTER[:-1] + ' [C3] [C2].')
        self.assertEqual(changes, ['basis_overstatement'])

    def test_interleaved_locations_keep_the_flattened_citation_order(self):
        text = 'The figures appear on the same slide [S1, S3, S2].'
        out, changes = self.guard(text)
        self.assertEqual(refs(out), ['S1', 'S3', 'S2'])
        self.assertEqual(out, "The deck states 140 000+ bots [S1] on page 10, under 'Traction by Apr-16', and separately "
                              "500M messages/month [S3] on page 12, and separately 500M messages with no explicit interval "
                              "[S2] on page 10, under 'Traction by Apr-16' " + CLARIFICATION_99 + ".")
        self.assertEqual(changes, ['basis_source_location'])
        self.assertEqual(self.guard(out), (out, []))

    def test_an_unasserted_infinitive_is_kept(self):
        # No denial word in the window: only "to establish" marks the contradiction as not asserted.
        text = 'Further evidence would be needed to establish a contradiction [C3, C2].'
        self.assertEqual(self.guard(text), (text, []))


# --- review of b54d82b: the location repair stays inside its own clause and narrator -----------------------

PLACED_23 = ("500M messages with no explicit interval [S2] on page 10, under 'Traction by Apr-16', and separately 500M "
             "messages/month [S3] on page 12 " + CLARIFICATION_99)
FUNDING_PROBE = 'Pitch Deck Hunt reports $23.1M raised [S4], while the usage figures appear on the same slide [S2, S3].'
FUNDING_PROBE_AFTER = 'Pitch Deck Hunt reports $23.1M raised [S4], while the deck states ' + PLACED_23 + '.'


class ReviewB54d82bProbeTests(SimpleTestCase):
    """Observed at 91a9071: the location rewrite swallowed a comma-linked clause (and its narrator and citation)
    and rewrote the object of a negation. It now acts only on a clause it can bound, with a known subject."""

    def setUp(self):
        self.payload = memo99_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text, items=None):
        """The complete normalisation -> time -> funding -> basis sequence, on the memo-99 normalised payload."""
        out, changes = replay({'section': text}, items or self.items, self.notes)
        return out['section'], changes.get('section', [])

    def guard(self, text):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(), (NOTE,)))

    def assert_facts_placed(self, out):
        expected = expected_facts(self.payload)
        facts = placed_facts(out)
        self.assertTrue(facts, out)
        for fact, ref, page, context in facts:
            self.assertEqual((fact, page, context), expected[ref], ref)

    def test_the_funding_clause_and_its_narrator_are_kept(self):
        out, changes = self.full(FUNDING_PROBE)
        self.assertEqual(out, FUNDING_PROBE_AFTER)
        self.assertEqual(changes, ['basis_source_location'])
        self.assertTrue(out.startswith('Pitch Deck Hunt reports $23.1M raised [S4], while '), out)
        self.assertEqual(refs(out), ['S4', 'S2', 'S3'])
        self.assertNotIn('Pitch Deck Hunt reports 500M', out)
        self.assert_facts_placed(out)

    def test_the_revenue_clause_and_its_citation_are_kept(self):
        cases = {
            'The company reports revenue of $10M [C8], while the message figures appear on the same slide [S2, S3].':
                'The company reports revenue of $10M [C8], while the deck states ' + PLACED_23 + '.',
            'Revenue is $10M [C8], and the message figures appear on the same slide [S2, S3].':
                'Revenue is $10M [C8], and the deck states ' + PLACED_23 + '.',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                out, changes = self.guard(text)
                self.assertEqual((out, changes), (expected, ['basis_source_location']))
                self.assertEqual(refs(out), ['C8', 'S2', 'S3'])

    def test_a_negated_common_slide_statement_is_kept(self):
        for text in ('The company does not state that the figures appear on the same slide [S2, S3].',
                     'The company states that the figures do not appear on the same slide [S2, S3].',
                     'The figures do not appear on the same slide [S2, S3].',
                     'The deck never places the figures on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
                self.assertEqual(self.full(text), (text, []))

    def test_different_narrators_on_either_side_of_a_comma(self):
        before = 'Pitch Deck Hunt reports $23.1M raised [S4], while the company states the message figures on the same slide [S2, S3].'
        after = 'The company states the message figures on the same slide [S2, S3], while Pitch Deck Hunt reports $23.1M raised [S4].'
        cases = {
            before: 'Pitch Deck Hunt reports $23.1M raised [S4], while the company states ' + PLACED_23 + '.',
            after: 'The company states ' + PLACED_23 + ', while Pitch Deck Hunt reports $23.1M raised [S4].',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                out, changes = self.full(text)
                self.assertEqual((out, changes), (expected, ['basis_source_location']))
                self.assertEqual(sorted(refs(out)), sorted(refs(text)))
                self.assert_facts_placed(out)
        # A narrator that does not report these figures is never made their narrator: the location rule keeps
        # the clause (only the merged narrator-provenance guard's own correction applies in the full sequence).
        from .basis_fidelity import basis_facts, guard_basis_wording
        other = 'Pitch Deck Hunt states the message figures on the same slide [S2, S3].'
        self.assertEqual(guard_basis_wording(other, basis_facts(self.items, self.notes)), (other, []))
        out, changes = self.full(other)
        self.assertFalse([c for c in changes if c.startswith('basis_')], changes)
        self.assertTrue(out.startswith('Pitch Deck Hunt states the message figures on the same slide [S2, S3]'), out)

    def test_an_unresolved_boundary_or_subject_keeps_the_sentence(self):
        for text in ('Revenue is $10M, the message figures appear on the same slide [S2, S3].',
                     'Revenue is $10M while the message figures appear on the same slide [S2, S3].',
                     'Revenue and the message figures appear on the same slide [S2, S3].',
                     'The company states revenue and the message figures on the same slide [S2, S3].',
                     'The company states the message figures (see revenue [C8]) on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_narrated_figure_is_never_restated_under_another_subject(self):
        from dataclasses import replace
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = [replace(i, narrator='Pitch Deck Hunt') if i.ref == 'S3' else i for i in _context_items()]
        for text in ('The company states the message figures on the same slide [S2, S3].',
                     'The figures appear on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(guard_basis_wording(text, basis_facts(items, (NOTE,))), (text, []))

    def test_a_clause_without_a_known_predicate_is_kept(self):
        text = 'Message figures on the same slide [S2, S3] need clarification.'
        self.assertEqual(self.guard(text), (text, []))

    def test_a_question_or_condition_with_a_placeable_clause_is_kept(self):
        # Mutation controls (P5/P6 survived the first run at e9d6763): each clause below passes the clause,
        # subject and word checks, so only the question and condition guards keep the sentence.
        for text in ('Are the figures on the same slide [S2, S3]?',
                     'If management confirms the interval, and the figures appear on the same slide [S2, S3], the '
                     'deck should say so.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_numbers_and_parentheticals_do_not_end_the_clause(self):
        text = 'The company states the message figures (500M, 500M/month) on the same slide [S2, S3].'
        self.assertEqual(self.guard(text), ('The company states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_a_parenthetical_fact_or_qualification_keeps_the_sentence(self):
        # Review of 191e627: an aside the restatement would discard is another fact or a qualification.
        text = 'The company states the message figures (revenue is $10M) on the same slide [S2, S3].'
        with self.subTest(sequence='full', text=text):
            self.assertEqual(self.full(text), (text, []))
        for text in ('The company states the message figures (revenue is $10M) on the same slide [S2, S3].',
                     'The company states the message figures (unaudited) on the same slide [S2, S3].',
                     'The figures (not independently verified) appear on the same slide [S2, S3].',
                     # The basis aside is superseded only when the pair's clarification is restated (both sides).
                     'The company states 140,000+ bots and 500M messages (measurement basis questioned) on the same '
                     'slide [S1, S3].',
                     'The company states the message figures ((nested) 500M) on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_an_additional_figure_keeps_the_sentence(self):
        # Review of ed29f3b: a figure the cited statements do not hold is another fact the restatement would
        # discard, in parentheses (nested too) or not, and so is a cited figure given another interval or currency.
        text = 'The company states the message figures (250M messages/month) on the same slide [S2, S3].'
        with self.subTest(sequence='full', text=text):
            self.assertEqual(self.full(text), (text, []))
        nested = 'The company states the message figures ((250M messages/month)) on the same slide [S2, S3].'
        with self.subTest(sequence='full', text=nested):
            self.assertEqual(self.full(nested), (nested, []))
        for text in ('The company states the message figures (250M messages/month) on the same slide [S2, S3].',
                     'The company states the message figures ((250M messages/month)) on the same slide [S2, S3].',
                     'The company states the message figures (500M (250M messages/month)) on the same slide [S2, S3].',
                     'The company states 250M messages/month on the same slide [S2, S3].',
                     'The figures (250M and 500M) appear on the same slide [S2, S3].',
                     'The company states 500M/day on the same slide [S2, S3].',
                     'The company states the message figures ($500M) on the same slide [S2, S3].',
                     'The company states the message figures ($ 500M) on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_an_unknown_number_arithmetic_or_nested_aside_keeps_the_sentence(self):
        # Second review of ed29f3b: an unknown number, a sum or comparison of held figures, a sign and any nested
        # or unclosed parenthesis are not classified, so the restatement would discard them.
        for text in ('The company states the message figures (600M messages) on the same slide [S2, S3].',
                     'The company states the message figures (500M, 600M/month) on the same slide [S2, S3].',
                     'The company states the message figures (500M (600M)) on the same slide [S2, S3].',
                     'The company states the message figures (500M + 500M) on the same slide [S2, S3].'):
            with self.subTest(sequence='full', text=text):
                self.assertEqual(self.full(text), (text, []))
        for text in ('The company states the message figures (600M messages) on the same slide [S2, S3].',
                     'The company states the message figures (500M, 600M/month) on the same slide [S2, S3].',
                     'The company states the message figures (500M (600M)) on the same slide [S2, S3].',
                     'The company states the message figures (500M + 500M) on the same slide [S2, S3].',
                     'The company states the message figures (500M+500M) on the same slide [S2, S3].',
                     'The company states the message figures (500M = 500M/month) on the same slide [S2, S3].',
                     'The company states the message figures (500M-500M/month) on the same slide [S2, S3].',
                     'The company states the message figures (~500M) on the same slide [S2, S3].',
                     'The company states the message figures (500M, 5%) on the same slide [S2, S3].',
                     'The company states the message figures (500M (500M/month)) on the same slide [S2, S3].',
                     'The company states (the message figures on the same slide [S2, S3]).',
                     'The company states the message figures (500M)) on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_further_unknown_figure_keeps_the_sentence(self):
        # Third review of ed29f3b: an aside's every figure must be one the cited statements hold, the last too, so
        # one more figure after held ones ("500M, 500M/month, 700M") is another fact the restatement would discard.
        for text in ('The company states the message figures (700M messages) on the same slide [S2, S3].',
                     'The company states the message figures (500M, 500M/month, 700M) on the same slide [S2, S3].'):
            with self.subTest(sequence='full', text=text):
                self.assertEqual(self.full(text), (text, []))
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        # Control: the held figures alone are still restated.
        text = 'The company states the message figures (500M, 500M/month) on the same slide [S2, S3].'
        self.assertEqual(self.guard(text), ('The company states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_a_figure_qualification_or_denominator_no_statement_gives_keeps_the_sentence(self):
        # Review of 2465791: a figure is matched whole. Its "+" and its "/interval" must be ones a cited statement
        # states, or the restatement would discard the qualification or the denominator.
        for text in ('The company states the message figures (500M+) on the same slide [S2, S3].',
                     'The company states the message figures (500M+/month) on the same slide [S2, S3].',
                     'The company states the message figures (500M/messages) on the same slide [S2, S3].'):
            with self.subTest(sequence='full', text=text):
                self.assertEqual(self.full(text), (text, []))
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        # Controls: a figure may state what its statement states ("140,000+", "500M/month", from "500M messages/
        # month") or leave it out ("140,000"); the restatement gives the statement's own wording back.
        restated = ("The company states 140 000+ bots [S1] on page 10, under 'Traction by Apr-16', and separately 500M "
                    "messages/month [S3] on page 12.")
        for text in ('The company states 140,000+ bots and 500M messages on the same slide [S1, S3].',
                     'The company states 140,000 bots and 500M/month on the same slide [S1, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (restated, ['basis_source_location']))
        text = 'The company states the message figures (500M, 500M/month) on the same slide [S2, S3].'
        self.assertEqual(self.guard(text), ('The company states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_a_figure_token_that_is_not_one_whole_figure_keeps_the_sentence(self):
        # Review of a4f55e5 (P29): a figure token with more after its form ("/day" after "500M/month", "s" after
        # "500m") is not one whole figure, so its leading form must not be read as a stated figure.
        for text in ('The company states the message figures (500M/month/day) on the same slide [S2, S3].',
                     'The company states the message figures (500ms) on the same slide [S2, S3].'):
            with self.subTest(sequence='full', text=text):
                self.assertEqual(self.full(text), (text, []))
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        # Control: the whole stated forms are still restated.
        text = 'The company states the message figures (500M, 500M/month) on the same slide [S2, S3].'
        self.assertEqual(self.guard(text), ('The company states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_a_list_marker_is_not_arithmetic(self):
        # Control: a bullet's marker is the line's lead, not a sign inside the clause.
        for lead in ('- ', '• '):
            with self.subTest(lead=lead):
                self.assertEqual(self.guard(lead + 'The figures appear on the same slide [S2, S3].'),
                                 (lead + 'The deck states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_a_citation_inside_the_clause_keeps_the_sentence(self):
        # Mutation control (P12 survived at 1bb993b): every word here is a placing word, so only the citation
        # check keeps [C3], which the restatement would otherwise drop.
        for text in ('The company states the message figures (500M [C3]) on the same slide [S2, S3].',
                     'The company states the message figures [S2] on the same slide [S2, S3].'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_basis_aside_is_superseded_by_the_restated_clarification(self):
        # Memo 99's own asides ("measurement basis unresolved; see open concerns") are replaced by the pair's
        # clarification, which says the same thing; the memo-99 replay tests hold the exact text.
        text = ('The company states a messages figure of either 500M total or 500M/month (measurement basis '
                'unresolved; see open concerns) on the same traction slide [S2, S3].')
        self.assertEqual(self.full(text), ('The company states ' + PLACED_23 + '.', ['basis_source_location']))

    def test_the_repairs_are_stable_and_idempotent(self):
        for text in (FUNDING_PROBE,
                     'Pitch Deck Hunt reports $23.1M raised [S4], while the company states the message figures on '
                     'the same slide [S2, S3].'):
            with self.subTest(text=text):
                out, _ = self.full(text)
                self.assertEqual(self.full(out), (out, []))
                self.assertEqual(self.full(text, items=list(reversed(self.items)))[0], out)


class PipelineReviewB54d82bTests(TestCase):
    """The memo writer stores the bounded repair: the funding clause, its narrator and S4 survive."""

    def test_the_writer_keeps_the_funding_clause(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo99_clause', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo99_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo99()
        raw = dict(raw, executive_summary=FUNDING_PROBE)
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=raw):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.executive_summary, FUNDING_PROBE_AFTER)
        self.assertIn(POINT_AFTER, memo.supported_points)
        self.assertIn(MODEL_AFTER, memo.business_model_analysis)


# --- memo 100 (ManyChat, document 3142; graded at f17db5c): OF-805, OF-806, OF-807 ------------------------------
#
#     OF-805  business_model_analysis: "500M messages [S2, S3] as traction metrics (in a slide context headed
#             'Traction by Apr-16')". S3 is page 12's monthly rate, with no slide context.
#     OF-806  open_concerns 1: "one or both figures may misrepresent the scale of actual activity": a judgment
#             from measurement ambiguity alone.
#     OF-807  upside_scenario: "These conditions are stated by the company [S1, S2, S3]": the conditions (active,
#             paying customers, recurring revenue) are the analysis's, not the deck's.
#
# The fixtures are memo 100's payload as sent and its raw reply (data/funding_fidelity/memo100*.json, from the
# committed evidence d8b224c). Memo 100 itself is not edited; these tests replay its reply.

def memo100():
    with open(os.path.join(DATA, 'memo100.json'), encoding='utf-8') as f:
        data = json.load(f)
    return json.loads(re.search(r'\{.*\}', data['model_reply_text'], re.S).group(0)), data['stored']


def memo100_payload():
    with open(os.path.join(DATA, 'memo100_payload.json'), encoding='utf-8') as f:
        return json.load(f)['payload']


CLARIFY = ('how the figure stated without an explicit interval relates to the monthly figure needs clarification '
           'before either is relied on')
BMA_100_BEFORE = ("The evidence establishes only that the company states 140,000+ bots [S1] and 500M messages [S2, S3] "
                  "as traction metrics (in a slide context headed 'Traction by Apr-16'), and that it operates in software "
                  "[P2] (current profile, undated) at Series A stage [P1].")
BMA_100_AFTER = ("The evidence establishes only that the company states 140,000+ bots [S1] and 500M messages [S2] "
                 "as traction metrics (in a slide context headed 'Traction by Apr-16'), and separately 500M "
                 "messages/month [S3] on page 12 (" + CLARIFY + "), and that it operates in software [P2] (current "
                 "profile, undated) at Series A stage [P1].")
OPEN_100_BEFORE = ('These cannot be compared without clarification; one or both figures may misrepresent the scale of '
                   'actual activity.')
OPEN_100_AFTER = 'These cannot be compared without clarification; ' + CLARIFY + '.'
UPSIDE_100_BEFORE = ("These conditions are stated by the company [S1, S2, S3] but have not been independently verified "
                     "[C2, C3, C4], so the upside reading rests entirely on the company's own assertions.")
UPSIDE_100_AFTER = ("The figures are stated by the company [S1, S2, S3] but have not been independently verified "
                    "[C2, C3, C4]; the conditions placed on them (active, paying customers, recurring revenue) are "
                    "hypotheses the evidence does not state, and would need evidence.")
CHANGED_100 = {'business_model_analysis', 'open_concerns', 'upside_scenario'}
# The merged guards' accepted live edits on memo 100 (evidence 09e), unchanged by this correction.
LIVE_100 = {'business_model_analysis': ['profile_undated'], 'risk_assessment': ['basis_overstatement'],
            'open_concerns': ['basis_contradiction_label'], 'what_would_change_the_picture': ['attribution:Pitch Deck Hunt']}


class Memo100ReplayTests(SimpleTestCase):
    """The actual memo-100 reply through the pipeline's guards: the graded shapes change, nothing else."""

    def setUp(self):
        self.raw, self.stored = memo100()
        self.payload = memo100_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)
        self.out, self.changes = replay(self.raw, self.items, self.notes)

    def test_the_fixture_is_memo_100_as_stored(self):
        self.assertIn(BMA_100_BEFORE, self.stored['business_model_analysis'])
        self.assertIn(OPEN_100_BEFORE, self.stored['open_concerns'])
        self.assertIn(UPSIDE_100_BEFORE, self.stored['upside_scenario'])
        self.assertEqual(self.notes[0][1], ('C3', 'C2'))
        sources = {i['ref']: (i['sources'][0].get('page'), i.get('source_context')) for i in self.payload['items']}
        self.assertEqual(sources['S2'], (10, 'Traction by Apr-16'))
        self.assertEqual(sources['S3'], (12, None))
        self.assertEqual(sources['S1'], (10, 'Traction by Apr-16'))

    def test_the_live_corrections_are_reproduced(self):
        # The merged guard's live edits on memo 100 still happen, exactly as stored.
        self.assertEqual(self.out['risk_assessment'], self.stored['risk_assessment'])
        self.assertTrue(self.out['open_concerns'].startswith('• Ambiguous message-volume measurement bases:'))
        self.assertEqual(self.out['what_would_change_the_picture'], self.stored['what_would_change_the_picture'])

    def test_of805_each_message_figure_keeps_its_own_page_and_context(self):
        expected = self.stored['business_model_analysis'].replace(BMA_100_BEFORE, BMA_100_AFTER)
        self.assertEqual(self.out['business_model_analysis'], expected)
        before_aside = self.out['business_model_analysis'].split("(in a slide context headed 'Traction by Apr-16')")[0]
        self.assertNotIn('S3', before_aside)                   # page 12 is not under the page-10 context
        self.assertIn('140,000+ bots [S1]', before_aside)      # the bot count stays where the model put it

    def test_of806_the_judgment_becomes_the_pair_clarification(self):
        first, *rest = self.out['open_concerns'].split('\n')
        self.assertTrue(first.endswith(OPEN_100_AFTER), first)
        self.assertNotIn('misrepresent', self.out['open_concerns'])
        # The item's facts and the other bullets are as stored.
        self.assertIn("The deck states '500M messages' (slide context: 'Traction by Apr-16') [C3/S2] and '500M "
                      "messages/month' on a separate page [C2/S3].", first)
        self.assertEqual(rest, self.stored['open_concerns'].split('\n')[1:])

    def test_of807_the_conditions_stay_hypotheses(self):
        expected = self.stored['upside_scenario'].replace(UPSIDE_100_BEFORE, UPSIDE_100_AFTER)
        self.assertEqual(self.out['upside_scenario'], expected)
        self.assertNotIn('conditions are stated by the company', self.out['upside_scenario'])
        # The conditional itself is kept: the conditions remain explicit "if"s.
        self.assertIn('and if the 140,000+ bots [S1] reflect active, paying customers generating recurring revenue',
                      self.out['upside_scenario'])

    def test_every_other_field_is_exactly_as_stored(self):
        for key, value in self.out.items():
            if key in self.stored and key not in CHANGED_100:
                self.assertEqual(value, self.stored[key], key)

    def test_citations_are_preserved_in_order(self):
        for key, value in self.out.items():
            if isinstance(value, str) and key in self.stored:
                self.assertEqual(refs(value), refs(self.stored[key]), key)

    def test_a_second_pass_changes_nothing(self):
        again, changes = replay(self.out, self.items, self.notes)
        self.assertEqual(again, self.out)
        self.assertEqual(changes, {})

    def test_reversed_item_order_gives_the_same_output(self):
        reversed_out, reversed_changes = replay(self.raw, list(reversed(self.items)), self.notes)
        self.assertEqual(reversed_out, self.out)
        self.assertEqual(reversed_changes, self.changes)

    def test_only_the_expected_rules_fired(self):
        self.assertEqual(self.changes, {
            'business_model_analysis': ['profile_undated', 'basis_source_context'],
            'risk_assessment': ['basis_overstatement'],
            'open_concerns': ['basis_contradiction_label', 'basis_referent_judgment'],
            'what_would_change_the_picture': ['attribution:Pitch Deck Hunt'],
            'upside_scenario': ['basis_condition_attribution'],
        })


class Memo100StoredSectionsTests(SimpleTestCase):
    """The stored memo-100 text (after the merged guards) through the basis guard: the same three repairs."""

    def test_the_stored_sections_get_the_same_repairs(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        payload = memo100_payload()
        facts = basis_facts(items_from(payload), notes_from(payload))
        _, stored = memo100()
        out = {key: guard_basis_wording(value, facts)[0] for key, value in stored.items()}
        self.assertIn(BMA_100_AFTER, out['business_model_analysis'])
        self.assertIn(OPEN_100_AFTER, out['open_concerns'])
        self.assertIn(UPSIDE_100_AFTER, out['upside_scenario'])
        self.assertEqual({k for k in stored if out[k] != stored[k]}, CHANGED_100)


class PipelineMemo100Tests(TestCase):
    """The memo writer itself (intelligence_pipeline._generate_memo) stores the repaired memo-100 reply."""

    def test_the_stored_memo_carries_the_repairs(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo100_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo100_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo100()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertIn(BMA_100_AFTER, memo.business_model_analysis)
        self.assertIn(OPEN_100_AFTER, memo.open_concerns)
        self.assertIn(UPSIDE_100_AFTER, memo.upside_scenario)
        for key in ('executive_summary', 'risk_assessment', 'what_would_change_the_picture', 'zelda_advantage',
                    'questions_for_management', 'downside_scenario', 'base_scenario', 'financial_analysis'):
            self.assertEqual(getattr(memo, key), stored[key], key)


class Of805SourceContextTests(SimpleTestCase):
    """OF-805: a figure citing both sides of a basis pair before a trailing context aside keeps each side's own
    page and context. Anything not known to be that shape is kept as written."""

    def setUp(self):
        self.payload = memo100_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text, items=None):
        out, changes = replay({'section': text}, items or self.items, self.notes)
        return out['section'], changes.get('section', [])

    def guard(self, text, items=None, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items or _context_items(), notes))

    def test_the_merged_figure_is_split_by_source(self):
        text = ("The company states 140,000+ bots [S1] and 500M messages [S2, S3] as traction metrics (in a slide "
                "context headed 'Traction by Apr-16').")
        after = ("The company states 140,000+ bots [S1] and 500M messages [S2] as traction metrics (in a slide context "
                 "headed 'Traction by Apr-16'), and separately 500M messages/month [S3] on page 12 (" + CLARIFY + ").")
        self.assertEqual(self.full(text), (after, ['basis_source_context']))
        self.assertEqual(self.guard(text), (after, ['basis_source_context']))
        # Other context-aside wordings are the same shape.
        colon = "The deck lists 500M messages [S2, S3] (slide context: 'Traction by Apr-16')."
        self.assertEqual(self.guard(colon), ("The deck lists 500M messages [S2] (slide context: 'Traction by "
                                             "Apr-16'), and separately 500M messages/month [S3] on page 12 (" + CLARIFY
                                             + ").", ['basis_source_context']))

    def test_the_following_clause_and_its_qualifications_are_kept(self):
        text = ("The evidence establishes only that the company states 140,000+ bots [S1] and 500M messages [S2, S3] "
                "(in a slide context headed 'Traction by Apr-16'), and that it operates in software [P2] (current "
                "profile, undated) at Series A stage [P1].")
        out, changes = self.guard(text)
        self.assertEqual(changes, ['basis_source_context'])
        self.assertTrue(out.endswith(", and that it operates in software [P2] (current profile, undated) at Series "
                                     "A stage [P1]."), out)
        self.assertEqual(refs(out), refs(text))

    def test_correctly_separated_or_unrelated_wording_is_kept(self):
        for text in (
                # Page 10 under its own context, page 12 placed separately: correct already.
                "The deck states 500M messages [S2] (slide context: 'Traction by Apr-16') and 500M messages/month "
                "[S3] on page 12.",
                "The deck states '500M messages' (slide context: 'Traction by Apr-16') [C3/S2] and '500M "
                "messages/month' on a separate page [C2/S3].",
                # The aside's context is held by every cited ref.
                "The company states 140,000+ bots [S1] and 500M messages [S2] (in a slide context headed 'Traction by "
                "Apr-16').",
                # Unrelated figures, a different context, an unknown ref: not this pair's shape.
                "The company states 140,000+ bots [S1] and 2M downloads [S5] (in a slide context headed 'Traction by "
                "Apr-16').",
                "The deck lists 500M messages [S2, S3] (in a slide context headed 'Pricing').",
                "The deck lists 500M messages [S2, S9] (in a slide context headed 'Traction by Apr-16').",
                # The page-12 figure alone under the aside is not split: no page-10 side shares its mention.
                "The deck lists 500M messages/month [S3] (in a slide context headed 'Traction by Apr-16').",
                # Limitation (recorded): a separate page-12 mention before the aside is not moved either.
                "The deck lists 500M messages [S2] and 500M messages/month [S3] (in a slide context headed "
                "'Traction by Apr-16').",
                # Questions and conditions.
                "Are 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16') the same figure?",
                "If 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16') is one figure, it needs "
                "a date."):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_without_a_basis_note_nothing_changes(self):
        text = "The deck lists 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16')."
        self.assertEqual(self.guard(text, notes=()), (text, []))

    def test_a_narrated_figure_is_kept(self):
        items = [i if i.ref != 'S3' else GroundedItem(ref='S3', kind='statement', category='Traction',
                                                      statement='500M messages/month', status=SELF_REPORTED,
                                                      sources=i.sources, narrator='Pitch Deck Hunt')
                 for i in _context_items()]
        text = "The deck lists 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16')."
        self.assertEqual(self.guard(text, items=items), (text, []))


class Of806ReferentJudgmentTests(SimpleTestCase):
    """OF-806: "one or both figures" continuing a measurement-basis item resolves to its pair; an error judgment on
    them becomes the pair's clarification. Nothing else is resolved or replaced."""

    LEAD = "- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12. "

    def guard(self, text, status=INSUFFICIENT):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(status), (NOTE,)))

    def test_the_judgment_clause_becomes_the_clarification(self):
        text = self.LEAD + 'These cannot be compared without clarification; one or both figures may misrepresent actual activity.'
        self.assertEqual(self.guard(text), (self.LEAD + 'These cannot be compared without clarification; ' + CLARIFY + '.',
                                            ['basis_referent_judgment']))
        whole = self.LEAD + 'One or both figures may overstate the scale of actual activity.'
        self.assertEqual(self.guard(whole), (self.LEAD + CLARIFY[0].upper() + CLARIFY[1:] + '.',
                                             ['basis_referent_judgment']))

    def test_unresolved_or_supported_judgments_are_kept(self):
        for text in (
                # A new bullet, or a different metric before it: no pair to continue.
                self.LEAD + '\n- One or both figures may misrepresent actual activity.',
                'Revenue is $10M [C8]. One or both figures may misrepresent actual activity.',
                'One or both figures may misrepresent actual activity.',
                # Independent evidence cited for the concern; a question; a denial; no judgment at all.
                self.LEAD + 'One or both figures may misrepresent actual activity [S5].',
                self.LEAD + 'Could one or both figures misrepresent actual activity?',
                self.LEAD + 'Nothing shows that one or both figures misrepresent actual activity.',
                self.LEAD + 'One or both figures need clarification before comparison.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_contradicted_pair_keeps_the_judgment(self):
        # Truth Delta found a member CONTRADICTED: the concern may be independently evidenced.
        from .grounded_context import CONTRADICTED
        text = self.LEAD + 'One or both figures may misrepresent actual activity.'
        self.assertEqual(self.guard(text, status=CONTRADICTED), (text, []))


class Of807ConditionAttributionTests(SimpleTestCase):
    """OF-807: conditions an analysis places on stated figures stay hypotheses; only the figures are the company's."""

    COND = "If the 140,000+ bots [S1] reflect active, paying customers, ManyChat would show product-market fit. "

    def guard(self, text, items=None):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items or _context_items(), (NOTE,)))

    def test_the_conditions_are_not_company_statements(self):
        text = self.COND + 'These conditions are stated by the company [S1, S2] but have not been verified.'
        self.assertEqual(self.guard(text), (
            self.COND + 'The figures are stated by the company [S1, S2] but have not been verified; the conditions '
            'placed on them (active, paying customers) are hypotheses the evidence does not state, and would need '
            'evidence.', ['basis_condition_attribution']))

    def test_supported_unresolved_or_other_wording_is_kept(self):
        supported = _context_items() + [_statement('S7', '120,000 active paying customers', 10, 'Traction by Apr-16')]
        self.assertEqual(self.guard(self.COND + 'These conditions are stated by the company [S7].', supported),
                         (self.COND + 'These conditions are stated by the company [S7].', []))
        for text in (
                'These conditions are stated by the company [S1].',                       # no condition before it
                self.COND + 'These conditions are stated by the company.',                # no citation to check
                '- ' + self.COND + '\n- These conditions are stated by the company [S1].',  # another bullet
                self.COND + 'These figures are stated by the company [S1].',              # the figures are
                self.COND + 'These conditions are not stated by the company [S1].',       # a denial
                'The bots [S1] reflect active, paying customers. These conditions are stated by the company [S1].',  # no condition
                'If the 500M messages figure is a monthly rate [S3], usage is large. These conditions are stated by '
                'the company [S3].'):                                                     # nothing beyond the figure
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
