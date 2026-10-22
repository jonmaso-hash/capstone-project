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


# --- review of 1801ec5: the earlier judgment rule bypassed OF-806's protections, and OF-805's split acted on
# denied, narrated and uncertain statements -------------------------------------------------------------------

JUDGED_DENIED = 'Nothing shows that one or both figures misrepresent activity [S2, S3].'
JUDGED = 'One or both figures may misrepresent activity [S2, S3].'
JUDGED_CLAUSE = 'These cannot be compared without clarification; one or both figures may misrepresent activity [S2, S3].'
JUDGED_CLAUSE_AFTER = 'These cannot be compared without clarification; ' + CLARIFY + ' [S2, S3].'
JUDGED_AFTER = CLARIFY[0].upper() + CLARIFY[1:] + ' [S2, S3].'
ASIDE_KEPT = (
    "The company does not state 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    "The company never states 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    "Pitch Deck Hunt lists 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    "The company may state 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    "The deck appears to list 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    "500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16') is the headline figure.",
    # The company's own subject and verb, with a denial or a hedge later in the clause.
    "The company states that it has not verified 500M messages [S2, S3] (in a slide context headed 'Traction by "
    "Apr-16').",
    "The company states what may be 500M messages [S2, S3] (in a slide context headed 'Traction by Apr-16').",
    # The company's own subject and verb, inside a condition.
    "The company states, if the slide is read as one figure, 500M messages [S2, S3] (in a slide context headed "
    "'Traction by Apr-16').",
)
# Through the full sequence the merged narrator-provenance rule (#281) answers the narrator's listing first; the
# basis guard then leaves its citations together and fires nothing.
NARRATOR_FULL = ("Pitch Deck Hunt lists 500M messages [S2, S3] (not Pitch Deck Hunt's: [S2, S3] are the company's own "
                 "traction statements) (in a slide context headed 'Traction by Apr-16').", ['provenance:Pitch Deck Hunt'])
MEMO98_JUDGMENT = ('If the cumulative figure is being presented as a monthly figure, the key traction claim is materially '
                   'overstated [C2, C3].')


def contradicted_items(payload):
    """Memo 100's items with the monthly claim CONTRADICTED, as if Truth Delta had found it."""
    from dataclasses import replace
    from .grounded_context import CONTRADICTED
    return [replace(i, status=CONTRADICTED) if i.ref == 'C2' else i for i in items_from(payload)]


class Review1801ec5Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 100's payload."""

    def setUp(self):
        self.payload = memo100_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text, items=None):
        out, changes = replay({'section': text}, items or self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_a_cited_referent_judgment_keeps_its_protections(self):
        self.assertEqual(self.full(JUDGED_DENIED), (JUDGED_DENIED, []))
        self.assertEqual(self.full(JUDGED, contradicted_items(self.payload)), (JUDGED, []))
        self.assertEqual(self.full(JUDGED_CLAUSE), (JUDGED_CLAUSE_AFTER, ['basis_referent_judgment']))

    def test_an_undefended_cited_referent_judgment_is_still_replaced(self):
        self.assertEqual(self.full(JUDGED), (JUDGED_AFTER, ['basis_referent_judgment']))

    def test_the_memo_98_overstatement_is_still_corrected_whole(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))

    def test_a_judgment_not_only_about_one_or_both_figures_stays_with_the_judgment_rule(self):
        # Only when every judging clause judges "one or both figures" is the clause rule in charge.
        text = 'The page-10 figure is overstated as a monthly figure [C2, C3]; one or both figures may mislead.'
        self.assertEqual(self.full(text), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))

    def test_a_denied_narrated_or_uncertain_statement_keeps_its_citations(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        facts = basis_facts(self.items, self.notes)
        for text in ASIDE_KEPT:
            with self.subTest(text=text):
                expected = NARRATOR_FULL if text.startswith('Pitch Deck Hunt') else (text, [])
                self.assertEqual(self.full(text), expected)
                self.assertEqual(guard_basis_wording(text, facts), (text, []))

    def test_the_company_s_own_affirmative_statement_is_still_split(self):
        out, changes = self.full("The company states 500M messages [S2, S3] (in a slide context headed 'Traction by "
                                 "Apr-16').")
        self.assertEqual(changes, ['basis_source_context'])
        self.assertTrue(out.startswith("The company states 500M messages [S2] (in a slide context headed"), out)


class PipelineReview1801ec5Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo) stores the same results."""

    def write(self, sections, items, name):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user(name, password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo100_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo100()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        return IntelligenceMemo.objects.get(document_id=doc.id)

    def test_the_writer_keeps_the_protections(self):
        payload = memo100_payload()
        memo = self.write({'market_analysis': JUDGED_DENIED, 'team_assessment': JUDGED_CLAUSE,
                           'problem_solution': ASIDE_KEPT[0], 'financial_analysis': ASIDE_KEPT[2]},
                          items_from(payload), 'review1801_a')
        self.assertEqual(memo.market_analysis, JUDGED_DENIED)
        self.assertEqual(memo.team_assessment, JUDGED_CLAUSE_AFTER)
        self.assertEqual(memo.problem_solution, ASIDE_KEPT[0])
        self.assertEqual(memo.financial_analysis, NARRATOR_FULL[0])
        # Memo 100's own repairs are unchanged in the same write.
        self.assertIn(BMA_100_AFTER, memo.business_model_analysis)
        self.assertIn(OPEN_100_AFTER, memo.open_concerns)

    def test_the_writer_keeps_a_contradicted_pair_s_judgment(self):
        memo = self.write({'market_analysis': JUDGED}, contradicted_items(memo100_payload()), 'review1801_b')
        self.assertEqual(memo.market_analysis, JUDGED)


# --- memo 101 (ManyChat, document 3143; graded at f7eb39d): OF-903, OF-904 (base), OF-905, OF-906 -----------------
#
#     OF-903  business_model_analysis: "500M messages (with an ambiguity ... [S2, S3]) in a slide context headed
#             'Traction by Apr-16'": page 12's source shares page 10's context, cited inside a parenthesis.
#     OF-904  base_scenario: "[S1, S2, S3], ManyChat had built ... by the period referenced in the 'Traction by
#             Apr-16' slide context": page 12's figure asserted under page 10's date. (The upside's "If ... [S3]
#             reflects a monthly run-rate as of the 'Traction by Apr-16' slide context" is a hypothesis: kept.)
#     OF-905  risk_assessment 1: "These figures ... — raising the possibility of metric inflation or imprecise
#             reporting": a judgment from measurement ambiguity alone.
#     OF-906  downside_scenario: "the cumulative and monthly presentations of the 500M messages figure [C2, C3]":
#             page 10 presupposed cumulative.
#
# The fixtures are memo 101's payload as sent and its raw reply (data/funding_fidelity/memo101*.json, from the
# committed evidence 82771ef). Memo 101 itself is not edited; these tests replay its reply.

def memo101():
    with open(os.path.join(DATA, 'memo101.json'), encoding='utf-8') as f:
        data = json.load(f)
    return json.loads(re.search(r'\{.*\}', data['model_reply_text'], re.S).group(0)), data['stored']


def memo101_payload():
    with open(os.path.join(DATA, 'memo101_payload.json'), encoding='utf-8') as f:
        return json.load(f)['payload']


BMA_101_BEFORE = ("the company states 140,000+ bots [S1] and 500M messages (with an ambiguity in measurement basis between "
                  "a cumulative total and a monthly rate [S2, S3]) in a slide context headed 'Traction by Apr-16'.")
BMA_101_AFTER = ("the company states 140,000+ bots [S1] and 500M messages (with an ambiguity in measurement basis between "
                 "a cumulative total and a monthly rate [S2]) in a slide context headed 'Traction by Apr-16', and separately "
                 "500M messages/month [S3] on page 12 (" + CLARIFY + ").")
BASE_101_BEFORE = ("Taking the self-reported traction metrics at face value [S1, S2, S3], ManyChat had built a sizeable "
                   "bot and messaging platform by the period referenced in the 'Traction by Apr-16' slide context.")
BASE_101_AFTER = ("Taking the self-reported traction metrics at face value [S1, S2], ManyChat had built a sizeable bot and "
                  "messaging platform by the period referenced in the 'Traction by Apr-16' slide context; the deck "
                  "separately states 500M messages/month [S3] on page 12 (" + CLARIFY + ").")
RISK_101_BEFORE = ('These figures carry different measurement bases and cannot be directly compared without '
                   'clarification — raising the possibility of metric inflation or imprecise reporting.')
RISK_101_AFTER = ('These figures carry different measurement bases and cannot be directly compared without '
                  'clarification — ' + CLARIFY + '.')
DOWN_101_BEFORE = ('If the inconsistency between the cumulative and monthly presentations of the 500M messages figure '
                   '[C2, C3] reflects imprecise metric reporting')
DOWN_101_AFTER = ('If the inconsistency between the unspecified-interval and monthly presentations of the 500M messages '
                  'figure [C2, C3] reflects imprecise metric reporting')
UPSIDE_101 = ("If the self-reported figure of 500M messages/month [S3] reflects a monthly run-rate as of the 'Traction by "
              "Apr-16' slide context")
CHANGED_101 = {'business_model_analysis', 'base_scenario', 'risk_assessment', 'downside_scenario'}


class Memo101ReplayTests(SimpleTestCase):
    """The actual memo-101 reply through the pipeline's guards: the graded shapes change, nothing else."""

    def setUp(self):
        self.raw, self.stored = memo101()
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)
        self.out, self.changes = replay(self.raw, self.items, self.notes)

    def test_the_fixture_is_memo_101_as_stored(self):
        for text, key in ((BMA_101_BEFORE, 'business_model_analysis'), (BASE_101_BEFORE, 'base_scenario'),
                          (RISK_101_BEFORE, 'risk_assessment'), (DOWN_101_BEFORE, 'downside_scenario'),
                          (UPSIDE_101, 'upside_scenario')):
            self.assertIn(text, self.stored[key], key)
        self.assertEqual(self.notes[0][1], ('C3', 'C2'))
        sources = {i['ref']: (i['sources'][0].get('page'), i.get('source_context')) for i in self.payload['items']}
        self.assertEqual((sources['S2'], sources['S3']), ((10, 'Traction by Apr-16'), (12, None)))

    def test_of903_page_12_does_not_share_page_10_s_context(self):
        self.assertEqual(self.out['business_model_analysis'],
                         self.stored['business_model_analysis'].replace(BMA_101_BEFORE, BMA_101_AFTER))

    def test_of904_the_asserted_base_date_is_page_10_s_alone(self):
        self.assertEqual(self.out['base_scenario'], self.stored['base_scenario'].replace(BASE_101_BEFORE, BASE_101_AFTER))

    def test_of904_the_upside_hypothesis_is_kept(self):
        # A condition: the upside proposes that date as a hypothesis. Recorded, not rewritten.
        self.assertEqual(self.out['upside_scenario'], self.stored['upside_scenario'])

    def test_of905_these_figures_continue_the_basis_item(self):
        self.assertEqual(self.out['risk_assessment'],
                         self.stored['risk_assessment'].replace(RISK_101_BEFORE, RISK_101_AFTER))
        self.assertNotIn('inflation', self.out['risk_assessment'])

    def test_of906_page_10_is_not_presupposed_cumulative(self):
        self.assertEqual(self.out['downside_scenario'],
                         self.stored['downside_scenario'].replace(DOWN_101_BEFORE, DOWN_101_AFTER))
        # The rest of the conditional, its other premise and its consequence stay.
        self.assertIn('and if the 140,000+ bots [S1] are predominantly unpaid or inactive', self.out['downside_scenario'])

    def test_every_other_field_is_exactly_as_stored(self):
        for key, value in self.out.items():
            if key in self.stored and key not in CHANGED_101:
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
            'business_model_analysis': ['basis_source_context'],
            'base_scenario': ['basis_source_context'],
            'risk_assessment': ['basis_referent_judgment'],
            'downside_scenario': ['basis_cumulative_presupposed'],
            'questions_for_management': ['attribution:Pitch Deck Hunt'],
        })


class Memo101StoredSectionsTests(SimpleTestCase):
    """The stored memo-101 text through the basis guard: the same four repairs."""

    def test_the_stored_sections_get_the_same_repairs(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        payload = memo101_payload()
        facts = basis_facts(items_from(payload), notes_from(payload))
        _, stored = memo101()
        out = {key: guard_basis_wording(value, facts)[0] for key, value in stored.items()}
        self.assertIn(BMA_101_AFTER, out['business_model_analysis'])
        self.assertIn(BASE_101_AFTER, out['base_scenario'])
        self.assertIn(RISK_101_AFTER, out['risk_assessment'])
        self.assertIn(DOWN_101_AFTER, out['downside_scenario'])
        self.assertEqual({k for k in stored if out[k] != stored[k]}, CHANGED_101)


class PipelineMemo101Tests(TestCase):
    """The memo writer itself (intelligence_pipeline._generate_memo) stores the repaired memo-101 reply."""

    def test_the_stored_memo_carries_the_repairs(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo101_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo101()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)
        self.assertIn(UPSIDE_101, memo.upside_scenario)
        for key in ('executive_summary', 'information_readiness', 'supported_points', 'open_concerns', 'zelda_advantage',
                    'upside_scenario', 'financial_analysis'):
            self.assertEqual(getattr(memo, key), stored[key], key)


class Of903SharedContextTests(SimpleTestCase):
    """OF-903 / OF-904: a context phrase (parenthesised or not) after a citation group naming both sides of one pair
    keeps only the refs it belongs to; the other side follows as its own fact. Only at a clause end, never for a
    narrator, a denial, a hedge, a question or a condition."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_shared_context_is_split_by_source(self):
        cases = {
            # Citations inside a parenthesis, the context phrase after it, the company's own verb.
            "The company states 500M messages (an ambiguity between a total and a monthly rate [S2, S3]) in a slide "
            "context headed 'Traction by Apr-16'.":
                "The company states 500M messages (an ambiguity between a total and a monthly rate [S2]) in a slide "
                "context headed 'Traction by Apr-16', and separately 500M messages/month [S3] on page 12 (" + CLARIFY + ").",
            # No reporting verb: an asserted date for the cited figures.
            "Taking the self-reported figures at face value [S2, S3], the platform had scale by the period referenced in "
            "the 'Traction by Apr-16' slide context.":
                "Taking the self-reported figures at face value [S2], the platform had scale by the period referenced in the "
                "'Traction by Apr-16' slide context; the deck separately states 500M messages/month [S3] on page 12 ("
                + CLARIFY + ").",
            # A list item: the company's own verb after the list marker.
            "- The company states 500M messages [S2, S3] in a slide context headed 'Traction by Apr-16'.":
                "- The company states 500M messages [S2] in a slide context headed 'Traction by Apr-16', and separately "
                "500M messages/month [S3] on page 12 (" + CLARIFY + ").",
            # "self-reported" is an adjective, not a narrator's reporting verb.
            "The self-reported figures [S2, S3] date to the period referenced in the 'Traction by Apr-16' slide context.":
                "The self-reported figures [S2] date to the period referenced in the 'Traction by Apr-16' slide context; "
                "the deck separately states 500M messages/month [S3] on page 12 (" + CLARIFY + ").",
        }
        for text, after in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, ['basis_source_context']))

    def test_hypotheses_narrators_denials_hedges_and_correct_dates_are_kept(self):
        for text in (
                # A hypothesis inside a condition (memo 101's upside shape) and a condition over shared refs.
                UPSIDE_101 + ", adoption was large.",
                "If the figures [S2, S3] were counted by the period referenced in the 'Traction by Apr-16' slide "
                "context, adoption was large.",
                # A narrator's listing, without a reporting verb.
                "Pitch Deck Hunt's listing of 500M messages [S2, S3] sits in the 'Traction by Apr-16' slide context.",
                # Not at a clause end: nowhere to place the separate fact.
                "500M messages [S2, S3] in the 'Traction by Apr-16' slide context is the headline figure.",
                "The self-reported 500M messages [S2, S3] in the 'Traction by Apr-16' slide context are the headline "
                "figure.",
                # A denial and a hedge.
                "The deck does not place 500M messages [S2, S3] in the 'Traction by Apr-16' slide context.",
                "500M messages [S2, S3] may belong in the 'Traction by Apr-16' slide context.",
                # Correctly attributed: only page 10's refs before the context; page 12 separately; refs after it.
                "140,000+ bots [S1] and 500M messages [S2] in the 'Traction by Apr-16' slide context; 500M "
                "messages/month [S3] on page 12.",
                "The platform had scale by the period referenced in the 'Traction by Apr-16' slide context [S1, S2].",
                # A question.
                "Were 500M messages [S2, S3] counted in the 'Traction by Apr-16' slide context?",
                # A context phrase inside a parenthesis that is not a context aside: kept (limitation, recorded).
                "The deck states 500M messages [S2, S3] (within the 'Traction by Apr-16' slide context).",
                "- The self-reported 500M messages [S2, S3] (within the 'Traction by Apr-16' slide context)",
                # A third party's reporting verb (not a recorded narrator): not the company's statement.
                "An analyst lists 500M messages [S2, S3] in a slide context headed 'Traction by Apr-16'."):
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))


class Of905TheseFiguresTests(SimpleTestCase):
    """OF-905: "these figures" continues the item's resolved basis pair; a judgment after it (or after its dash)
    becomes the clarification. Unresolved, contradicted, denied or independently evidenced judgments stay."""

    LEAD = "- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12. "

    def guard(self, text, status=INSUFFICIENT):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_context_items(status), (NOTE,)))

    def test_the_judgment_after_these_figures_becomes_the_clarification(self):
        text = self.LEAD + 'These figures cannot be compared without clarification — raising the possibility of inflation.'
        self.assertEqual(self.guard(text), (self.LEAD + 'These figures cannot be compared without clarification — '
                                            + CLARIFY + '.', ['basis_referent_judgment']))
        whole = self.LEAD + 'These figures may be inflated.'
        self.assertEqual(self.guard(whole), (self.LEAD + CLARIFY[0].upper() + CLARIFY[1:] + '.',
                                             ['basis_referent_judgment']))

    def test_unresolved_unsupported_or_independent_cases_are_kept(self):
        for text in (
                self.LEAD + '\n- These figures may be inflated.',                       # a new bullet
                'Revenue is $10M [C8]. These figures may be inflated.',                  # another metric before
                'These figures may be inflated.',                                         # no antecedent
                self.LEAD + 'These figures may be inflated [S5].',                        # cites outside the pair
                self.LEAD + 'Nothing suggests that these figures are inflated.',          # a denial
                self.LEAD + 'Are these figures inflated?',                                # a question
                self.LEAD + 'These figures need clarification.',                          # no judgment
                # A judgment in an independent clause that is not about these figures.
                self.LEAD + 'These figures need clarification; the deck may be inflating usage.'):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_contradicted_pair_keeps_the_judgment(self):
        from .grounded_context import CONTRADICTED
        text = self.LEAD + 'These figures may be inflated.'
        self.assertEqual(self.guard(text, status=CONTRADICTED), (text, []))


class Of906CumulativePresuppositionTests(SimpleTestCase):
    """OF-906: "the cumulative and monthly ..." presupposes a cumulative side; for a pair whose no-interval side is
    not admitted cumulative, it becomes the unspecified interval, inside a condition too. A hypothesis that page 10
    is cumulative, an alternative, a question and an admitted cumulative side are kept."""

    def guard(self, text, items=None, notes=(NOTE,)):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items or _context_items(), notes))

    def test_the_presupposed_cumulative_side_is_the_unspecified_interval(self):
        cases = {
            'If the gap between the cumulative and monthly presentations [C2, C3] is real, usage is unclear.':
                'If the gap between the unspecified-interval and monthly presentations [C2, C3] is real, usage is unclear.',
            'The monthly and cumulative figures [C2, C3] differ in basis.':
                'The monthly and unspecified-interval figures [C2, C3] differ in basis.',
        }
        for text, after in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (after, ['basis_cumulative_presupposed']))

    def test_hypotheses_alternatives_questions_and_supported_cumulative_are_kept(self):
        for text in (
                'If the 500M figure is cumulative [C2, C3], monthly activity is lower.',      # a hypothesis
                'It is unclear whether 500M is a cumulative total or a monthly rate [C2, C3].',  # an alternative
                'Is the gap between the cumulative and monthly presentations real [C2, C3]?',  # a question
                'The cumulative and monthly downloads [S5, S6] differ.'):                     # not this pair
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))
        # A pair whose side is admitted cumulative ("3M messages to date") keeps "cumulative".
        supported = 'If the gap between the cumulative and weekly presentations [C7, C9] is real, usage is unclear.'
        self.assertEqual(self.guard(supported, items=_pairs_items(), notes=(NOTE_CUMULATIVE,)), (supported, []))


# --- review of b040c23 / 750de3f: four scope regressions -----------------------------------------------------------
#
#     1  A denial lost across a dash: "Nothing suggests these figures are wrong — or inflated."
#     2  A new subject after a dash inherited the figures' referent: "These figures need clarification — an analyst is
#        wrong."
#     3  A later message citation took ownership of another metric's phrase: "The cumulative and monthly revenue differ
#        while the message counts remain ambiguous [C2, C3]."
#     4  A third party's statement with no recognised reporting verb was split: "According to an analyst, 500M messages
#        [S2, S3] sit in a slide context headed 'Traction by Apr-16'."

PAIR_LEAD = "- The deck states 500M messages [S2] on page 10 and 500M messages/month [S3] on page 12. "
REVIEW_750_KEPT = (
    PAIR_LEAD + "Nothing suggests these figures are wrong — or inflated.",
    PAIR_LEAD + "These figures are not wrong — or inflated.",
    PAIR_LEAD + "These figures need clarification — an analyst is wrong.",
    PAIR_LEAD + "These figures need clarification — and the analyst is wrong.",
    "The cumulative and monthly revenue differ while the message counts remain ambiguous [C2, C3].",
    "The cumulative and monthly revenue [C2, C3] differ.",
    "According to an analyst, 500M messages [S2, S3] sit in a slide context headed 'Traction by Apr-16'.",
    # The company's own source named, but attributed to a third party.
    "According to an analyst, the self-reported 500M messages [S2, S3] sit in a slide context headed 'Traction by "
    "Apr-16'.",
    "Per an industry report, the self-reported 500M messages [S2, S3] sit in the 'Traction by Apr-16' slide context.",
    # Controls that only one check keeps: a denial far before the referent; a figure noun whose later citation is
    # another clause's; no reporting verb, no attribution and no own source named.
    PAIR_LEAD + "Nothing in the deck suggests that these figures, taken together on both pages, are wrong — or "
    "inflated.",
    "The cumulative and monthly figures differ while the message counts remain ambiguous [C2, C3].",
    "500M messages [S2, S3] sit in a slide context headed 'Traction by Apr-16'.",
    # A new subject after "perhaps" (dash), and an independent ";" clause.
    PAIR_LEAD + "These figures need clarification — perhaps the deck is inflating usage.",
    PAIR_LEAD + "These figures need clarification; possibly inflated.",
)


class Review750de3fTests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_denials_new_subjects_other_metrics_and_third_parties_are_kept(self):
        for text in REVIEW_750_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_intended_repairs_still_happen(self):
        cases = {
            # A judgment continuing "these figures" after a dash, as in memo 101.
            PAIR_LEAD + "These figures need clarification — possibly inflated.":
                PAIR_LEAD + "These figures need clarification — " + CLARIFY + ".",
            # Coordinated judgments of the same figures: one clarification, not two.
            PAIR_LEAD + "These figures are wrong — or inflated.":
                PAIR_LEAD + CLARIFY[0].upper() + CLARIFY[1:] + ".",
            # The phrase's own noun is a figure noun of the pair.
            "If the cumulative and monthly figures [C2, C3] diverge, usage is unclear.":
                "If the unspecified-interval and monthly figures [C2, C3] diverge, usage is unclear.",
        }
        for text, after in cases.items():
            with self.subTest(text=text):
                out, changes = self.full(text)
                self.assertEqual(out, after)
                self.assertTrue(changes, changes)


class PipelineReview750de3fTests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo) keeps the four preserved shapes."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review750_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        sections = {'market_analysis': REVIEW_750_KEPT[0], 'team_assessment': REVIEW_750_KEPT[2],
                    'problem_solution': REVIEW_750_KEPT[4], 'financial_analysis': REVIEW_750_KEPT[6]}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        for key, text in sections.items():
            self.assertEqual(getattr(memo, key), text, key)
        # Memo 101's own repairs are unchanged in the same write.
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# --- review of 7fb484b / bbe0ec4: three ownership regressions -----------------------------------------------------
#
#     1  A new subject after a dash inherited the figures' referent: "— or Bob is wrong", "— marketing is misleading"
#        (an unlisted subject after "or"; any word ending in "ing" counted as a participle).
#     2  A generic figure noun took the pair's ownership for another metric: "The cumulative and monthly figures for
#        revenue differ from message counts [C2, C3]."
#     3  A third party's statement naming the deck was split: "An analyst describes the deck's 500M messages [S2, S3]
#        in a slide context headed 'Traction by Apr-16'."

REVIEW_7FB_KEPT = (
    PAIR_LEAD + "These figures need clarification — or Bob is wrong.",
    PAIR_LEAD + "These figures need clarification — marketing is misleading.",
    PAIR_LEAD + "These figures need clarification — pricing is wrong.",
    # A listed participle whose complement has its own subject.
    PAIR_LEAD + "These figures need clarification — suggesting marketing is misleading.",
    "The cumulative and monthly figures for revenue differ from message counts [C2, C3].",
    # Controls that only one check keeps: a qualifier naming something other than the pair's noun; another metric
    # named before the owning citation with no qualifier.
    "The cumulative and monthly figures for bots differ [C2, C3].",
    "The cumulative and monthly figures differ from revenue [C2, C3].",
    "An analyst describes the deck's 500M messages [S2, S3] in a slide context headed 'Traction by Apr-16'.",
    # No attribution marker and no reporting verb: only the head's own wording shows a third party.
    "An analyst's reading of the deck's 500M messages [S2, S3] sits in a slide context headed 'Traction by Apr-16'.",
    # The company's own verb, but a narrator named in the clause: kept by the narrator check alone (the no-verb
    # narrator control is now also kept by the own-head allowlist).
    "The company states 500M messages [S2, S3] from the Pitch Deck Hunt copy in a slide context headed 'Traction by "
    "Apr-16'.",
    # An attribution after the citations, with the company's own words before them: kept by the attribution check
    # alone (", in short," in its place is split). The phrase's own noun is neither a figure noun nor the pair's
    # noun, and no listed metric: kept by the figure-noun check alone ("monthly messages" is rewritten).
    "The self-reported 500M messages [S2, S3], an analyst says, sit in a slide context headed 'Traction by Apr-16'.",
    "The cumulative and monthly bots [C2, C3] differ.",
)


class Review7fb484bTests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_new_subjects_other_metrics_and_third_parties_are_kept(self):
        for text in REVIEW_7FB_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_intended_repairs_still_happen(self):
        cases = {
            # A judgment continuing "these figures" after a dash: "or" + an adverb + the judgment.
            PAIR_LEAD + "These figures need clarification — or possibly inflated.":
                PAIR_LEAD + "These figures need clarification — " + CLARIFY + ".",
            # A listed participle followed by the judgment of the figures themselves.
            PAIR_LEAD + "These figures need clarification — suggesting possible inflation.":
                PAIR_LEAD + "These figures need clarification — " + CLARIFY + ".",
            # A qualifier naming the pair's own noun.
            "The cumulative and monthly figures for messages [C2, C3] differ.":
                "The unspecified-interval and monthly figures for messages [C2, C3] differ.",
            # The deck's own figures, with no reporting verb.
            "The deck's 500M messages [S2, S3] sit in a slide context headed 'Traction by Apr-16'.":
                "The deck's 500M messages [S2] sit in a slide context headed 'Traction by Apr-16'; the deck separately "
                "states 500M messages/month [S3] on page 12 (" + CLARIFY + ").",
        }
        for text, after in cases.items():
            with self.subTest(text=text):
                out, changes = self.full(text)
                self.assertEqual(out, after)
                self.assertTrue(changes, changes)


class PipelineReview7fb484bTests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo) keeps the three reviewed shapes and memo 101's repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review7fb_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        sections = {'market_analysis': REVIEW_7FB_KEPT[0], 'team_assessment': REVIEW_7FB_KEPT[1],
                    'problem_solution': REVIEW_7FB_KEPT[4], 'financial_analysis': REVIEW_7FB_KEPT[7]}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        for key, text in sections.items():
            self.assertEqual(getattr(memo, key), text, key)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# --- review of 377a142 / ee47a9a: a continuation prefix owned the rest of the clause -------------------------------
#
#     "These figures need clarification — misleading advertising is wrong." and "— inflation is affecting costs."
#     were replaced by the clarification: _CONTINUATION matched a judgment-like first word and never read the rest
#     of the fragment, which has its own subject.

CONT_LEAD = PAIR_LEAD + "These figures need clarification — "
REVIEW_377_KEPT = (
    CONT_LEAD + "misleading advertising is wrong.",
    CONT_LEAD + "inflation is affecting costs.",
    # Independent subjects beginning with judgment-like words, after each kind of continuation starter.
    CONT_LEAD + "wrong assumptions drive the model.",
    CONT_LEAD + "overstated expectations are common.",
    CONT_LEAD + "or inflation is affecting costs.",
    CONT_LEAD + "suggesting inflation is affecting costs.",
    CONT_LEAD + "possibly inflated expectations are common.",
    # A bare judgment noun: whose inflation is not stated.
    CONT_LEAD + "inflation.",
    # An unfamiliar tail after a genuine judgment: not classified, so kept (the conservative direction).
    CONT_LEAD + "possibly inflated by bots.",
)
REVIEW_377_REPAIRED = (
    CONT_LEAD + "or possibly inflated.",
    CONT_LEAD + "suggesting possible inflation.",
    CONT_LEAD + "misleading.",
    CONT_LEAD + "which may be overstated.",
    CONT_LEAD + "raising the possibility of metric inflation or imprecise reporting.",
)


class Review377a142Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_an_independent_subject_after_a_dash_is_kept(self):
        for text in REVIEW_377_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_genuine_continuations_are_repaired(self):
        for text in REVIEW_377_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (CONT_LEAD + CLARIFY + '.', ['basis_referent_judgment']))
        # Citations inside the continuation stay with the clarification.
        cited = CONT_LEAD + "possibly overstated [S2, S3]."
        self.assertEqual(self.full(cited), (CONT_LEAD + CLARIFY + ' [S2, S3].', ['basis_referent_judgment']))


class PipelineReview377a142Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps both reviewed clauses,
    repairs a genuine continuation and keeps memo 101's four repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review377_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        sections = {'market_analysis': REVIEW_377_KEPT[0], 'team_assessment': REVIEW_377_KEPT[1],
                    'problem_solution': REVIEW_377_REPAIRED[0]}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_377_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_377_KEPT[1])
        self.assertEqual(memo.problem_solution, CONT_LEAD + CLARIFY + '.')
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# --- review of 9b28e14 / e16ad6a: an independent cited fragment was taken over by the general judgment rule ---------
#
#     With the pair citations at the end, "These figures need clarification — misleading advertising is wrong [S2, S3]."
#     lost its whole second sentence through basis_overstatement: _CONTINUATION rejected the fragment, so no referent
#     governed it, and _judgment then replaced the whole sentence because citations were present. Present at 0664563,
#     377a142 and 9b28e14: an incomplete fix, not a new regression.

CLARIFY_SENTENCE = CLARIFY[0].upper() + CLARIFY[1:]
REVIEW_9B2_KEPT = (
    CONT_LEAD + "misleading advertising is wrong [S2, S3].",
    CONT_LEAD + "inflation is affecting costs [S2, S3].",
    CONT_LEAD + "wrong assumptions drive the model [S2, S3].",
    CONT_LEAD + "or inflation is affecting costs [S2, S3].",
    # A ";" clause and a standalone sentence: citations alone do not say what a judgment is about.
    PAIR_LEAD + "These figures need clarification; misleading advertising is wrong [S2, S3].",
    PAIR_LEAD + "Misleading advertising is wrong [S2, S3].",
    # Basis words outside the judging clause do not make it about the bases.
    PAIR_LEAD + "The monthly figure needs clarification — misleading advertising is wrong.",
)
REVIEW_9B2_REPAIRED = (
    # A clause naming the figures or their bases is still the pair's. Since the review of 8d7f8dc only that clause is
    # replaced and the clause before the dash stays (at 8d7f8dc the whole sentence was replaced).
    (PAIR_LEAD + "These figures need clarification — the cumulative figure is overstated [S2, S3].",
     CONT_LEAD + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The 500M messages figure is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "These figures need clarification — the larger figure is overstated [S2, S3].",
     CONT_LEAD + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    # The pair's clause is repaired and an independent clause in the same sentence is kept.
    (PAIR_LEAD + "The cumulative figure is overstated [S2, S3] — misleading advertising is wrong.",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3] — misleading advertising is wrong.", ['basis_overstatement']),
    (PAIR_LEAD + "Misleading advertising is wrong; the monthly figure is inflated [S2, S3].",
     PAIR_LEAD + "Misleading advertising is wrong; " + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "These figures may be inflated — misleading advertising is wrong [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " — misleading advertising is wrong [S2, S3].", ['basis_referent_judgment']),
    # A genuine cited continuation stays with the referent rule.
    (CONT_LEAD + "possibly overstated [S2, S3].", CONT_LEAD + CLARIFY + " [S2, S3].", ['basis_referent_judgment']),
)


class Review9b28e14Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_a_cited_independent_clause_is_kept(self):
        for text in REVIEW_9B2_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_pairs_own_judgments_are_still_repaired(self):
        for text, after, changes in REVIEW_9B2_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))

    def test_memo_98_conditional_correction_is_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))

    def test_earlier_controls_are_unchanged(self):
        for text in REVIEW_377_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))
        for text in REVIEW_377_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (CONT_LEAD + CLARIFY + '.', ['basis_referent_judgment']))


class PipelineReview9b28e14Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps both reviewed cited
    clauses, repairs the pair's own clause in a mixed sentence and keeps memo 101's four repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review9b2_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        mixed, mixed_after, _ = REVIEW_9B2_REPAIRED[2]
        sections = {'market_analysis': REVIEW_9B2_KEPT[0], 'team_assessment': REVIEW_9B2_KEPT[1],
                    'problem_solution': mixed}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_9B2_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_9B2_KEPT[1])
        self.assertEqual(memo.problem_solution, mixed_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# --- review of 8d7f8dc / eca3d8c: clause preservation, judged subject, pair-directed claims -------------------------
#
#     1. Whole-sentence replacement dropped independent clauses with no judgment word ("; management has not
#        clarified the definitions"), after ";", a dash or a linking comma, before or after the pair's judgment.
#     2. Ownership read incidental vocabulary anywhere in the clause ("— monthly costs are inflated", "— misleading
#        messages are wrong"), not the subject the judgment is about.
#     3. "The key traction claim may be overstated [S2, S3]." was kept at 8d7f8dc: its subject is the pair's claim.

MGMT = "management has not clarified the definitions"
MGMT_SENTENCE = MGMT[0].upper() + MGMT[1:]
REVIEW_8D7_KEPT = (
    CONT_LEAD + "monthly costs are inflated [S2, S3].",
    CONT_LEAD + "misleading messages are wrong [S2, S3].",
    PAIR_LEAD + "Monthly costs are inflated [S2, S3].",
    PAIR_LEAD + "Misleading messages are wrong [S2, S3].",
    PAIR_LEAD + "These figures need clarification, but monthly costs are inflated [S2, S3].",
    # A claim noun about something else: its own qualifier is not the pair's.
    PAIR_LEAD + "The hiring claim is overstated [S2, S3].",
    # A condition about the pair does not make an unrelated consequence the pair's.
    PAIR_LEAD + "If the figures are monthly, misleading advertising is wrong [S2, S3].",
    PAIR_LEAD + "If the figures are monthly, monthly costs are inflated [S2, S3].",
    PAIR_LEAD + "If the figures are monthly, hiring growth is overstated [S2, S3].",
    # The pair's noun without one of its figures: messages that are sent, not the counted figure.
    CONT_LEAD + "the messages are misleading [S2, S3].",
    # A condition that does not name the pair does not make a measure the pair's.
    PAIR_LEAD + "If the hiring plan slips, the implied monthly activity is overstated [S2, S3].",
)
REVIEW_8D7_REPAIRED = (
    # 1. The pair's judgment is repaired; the independent clause and every citation stay.
    (PAIR_LEAD + "The monthly figure is overstated [S2, S3]; " + MGMT + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3]; " + MGMT + ".", ['basis_overstatement']),
    (PAIR_LEAD + MGMT_SENTENCE + "; the monthly figure is overstated [S2, S3].",
     PAIR_LEAD + MGMT_SENTENCE + "; " + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The monthly figure is overstated [S2, S3] — " + MGMT + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3] — " + MGMT + ".", ['basis_overstatement']),
    (PAIR_LEAD + MGMT_SENTENCE + " — the monthly figure is overstated [S2, S3].",
     PAIR_LEAD + MGMT_SENTENCE + " — " + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The monthly figure is overstated [S2, S3], but " + MGMT + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], but " + MGMT + ".", ['basis_overstatement']),
    (PAIR_LEAD + MGMT_SENTENCE + ", and the monthly figure is overstated [S2, S3].",
     PAIR_LEAD + MGMT_SENTENCE + ", and " + CLARIFY + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "These figures may be inflated, but " + MGMT + " [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + ", but " + MGMT + " [S2, S3].", ['basis_referent_judgment']),
    # A coordinated judgment after a comma continues the pair's clause: one clarification.
    (PAIR_LEAD + "The monthly figure is overstated, and possibly inflated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    # 3. A claim whose qualifier is the pair's own evidence category.
    (PAIR_LEAD + "The key traction claim may be overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The key traction claim may be overstated [S2, S3], and monthly costs are inflated.",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], and monthly costs are inflated.", ['basis_overstatement']),
    # 2. Genuine pair subjects are still repaired.
    (CONT_LEAD + "the monthly figure is overstated [S2, S3].", CONT_LEAD + CLARIFY + " [S2, S3].",
     ['basis_overstatement']),
    (PAIR_LEAD + "The 500M messages are overstated [S2, S3].", PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].",
     ['basis_overstatement']),
    (PAIR_LEAD + "The reported usage is overstated [S2, S3].", PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].",
     ['basis_overstatement']),
    # Adjacent clauses judging the pair: one clarification with both clauses' citations.
    (PAIR_LEAD + "The monthly figure is overstated [S2]; the cumulative figure is inflated [S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2] [S3].", ['basis_overstatement']),
    # A relative clause after the pair's clause stays; a serial list is one clause, never split mid-list.
    (PAIR_LEAD + "The monthly figure is overstated [S2, S3], which management has not explained.",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], which management has not explained.", ['basis_overstatement']),
    # Corrected at the review of 8f11844: "daily" is not this pair's interval, so the list is another subject and kept.
    (PAIR_LEAD + "The cumulative, monthly, and daily figures are overstated [S2, S3].",
     PAIR_LEAD + "The cumulative, monthly, and daily figures are overstated [S2, S3].", []),
    (PAIR_LEAD + "The cumulative, monthly, and page-10 figures are overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    # A condition names the pair by a basis word, a figure referent or the pair's noun, each alone (memo 100's form).
    (PAIR_LEAD + "If the deck counts weekly, the implied monthly activity is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "If the larger figure is restated, the implied monthly activity is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "If the messages are restated, the implied monthly activity is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
)


class Review8d7f8dcTests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_independent_claims_with_incidental_pair_words_are_kept(self):
        for text in REVIEW_8D7_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_pairs_judgment_is_repaired_and_other_clauses_kept(self):
        for text, after, changes in REVIEW_8D7_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))
                if MGMT in text:
                    self.assertIn(MGMT, after)
                self.assertEqual(refs(after)[-2:], ['S2', 'S3'])

    def test_memo_98_and_earlier_rounds_are_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))
        for text in REVIEW_9B2_KEPT + REVIEW_377_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))


class PipelineReview8d7f8dcTests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps the management clause,
    keeps an independent claim with incidental pair words, repairs the pair-directed claim and keeps memo 101's
    four repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review8d7_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        (first, first_after, _), (claim, claim_after, _) = REVIEW_8D7_REPAIRED[0], REVIEW_8D7_REPAIRED[8]
        sections = {'market_analysis': first, 'team_assessment': REVIEW_8D7_KEPT[0], 'problem_solution': claim}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, first_after)
        self.assertEqual(memo.team_assessment, REVIEW_8D7_KEPT[0])
        self.assertEqual(memo.problem_solution, claim_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# --- review of a6dcddf / 9532c46: a condition overrode foreign qualifiers; a list guard merged an aside and a clause --
#
#     1. "If the figures are monthly, the hiring claim is overstated [S2, S3]." was rewritten: after a condition
#        naming the pair, a figure or claim head was enough and the foreign qualifier ("hiring") was not read.
#     2. "The monthly figure is inflated, in management's view, but the definitions remain unclear [S2, S3]." lost
#        the attribution and the clause: the serial-list guard read ", in management's view" as a list item, merged
#        the ", but" clause, and the whole chain was replaced.

UNCLEAR = "the definitions remain unclear"
REVIEW_A6D_KEPT = (
    PAIR_LEAD + "If the figures are monthly, the hiring claim is overstated [S2, S3].",
    PAIR_LEAD + "If the figures are monthly, the hiring growth rate is overstated [S2, S3].",
    PAIR_LEAD + "The monthly figure is inflated, in management's view, but " + UNCLEAR + " [S2, S3].",
    # An attribution or aside around the pair's clause: whose judgment it is cannot be established, so it is kept.
    PAIR_LEAD + "The monthly figure is inflated, in management's view [S2, S3].",
    PAIR_LEAD + "In management's view, the monthly figure is inflated [S2, S3].",
    PAIR_LEAD + "Management says the monthly figure is overstated [S2, S3].",
    # After a condition: an aside inside it, or a measure without the pair's basis, leaves the owner open.
    PAIR_LEAD + "If the figures are monthly, in management's view, the claim is overstated [S2, S3].",
    PAIR_LEAD + "If the figures are monthly, the implied activity is overstated [S2, S3].",
    # A linking comma after text with no verb joins a compound subject, not two clauses: the extent of the pair's
    # clause cannot be established, so the sentence is kept (afbf715 replaced the second half).
    PAIR_LEAD + "The monthly figure [S2, S3], and the larger figure are overstated.",
    PAIR_LEAD + "The monthly figure [S2], and the larger figure [S3] are overstated.",
)
REVIEW_A6D_REPAIRED = (
    (PAIR_LEAD + "The monthly figure is inflated [S2, S3], but " + UNCLEAR + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], but " + UNCLEAR + ".", ['basis_overstatement']),
    # A genuine serial list is still one clause, and a clause after it is still its own.
    # Corrected at the review of 8f11844: "daily" is not this pair's interval, so the list is kept.
    (PAIR_LEAD + "The cumulative, monthly, and daily figures are overstated [S2, S3], but " + UNCLEAR + ".",
     PAIR_LEAD + "The cumulative, monthly, and daily figures are overstated [S2, S3], but " + UNCLEAR + ".", []),
    (PAIR_LEAD + "The cumulative, monthly, and page-12 figures are overstated [S2, S3], but " + UNCLEAR + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], but " + UNCLEAR + ".", ['basis_overstatement']),
    # A condition naming the pair, then the pair's own subject (memo 98) or a measure with its basis (memo 100).
    (PAIR_LEAD + "If the figures are monthly, the key traction claim is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "If the cumulative figure was restated as a monthly figure, the implied monthly activity would be "
                 "materially overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    # A clause with a verb is not a list item, whatever its commas: the ", but" clause after it is its own.
    (PAIR_LEAD + "Management has not clarified the definitions, in its view, but the monthly figure is overstated [S2, S3].",
     PAIR_LEAD + "Management has not clarified the definitions, in its view, but " + CLARIFY + " [S2, S3].",
     ['basis_overstatement']),
    # A list item's marker is not a word before the subject.
    (PAIR_LEAD.rstrip() + "\n- The monthly figure is overstated [S2, S3].",
     PAIR_LEAD.rstrip() + "\n- " + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
)


class ReviewA6dcddfTests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_foreign_qualifiers_attributions_and_asides_are_kept(self):
        for text in REVIEW_A6D_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_pairs_own_clauses_are_still_repaired(self):
        for text, after, changes in REVIEW_A6D_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))
                if UNCLEAR in text:
                    self.assertIn(UNCLEAR, after)
                self.assertEqual(refs(after)[-2:], ['S2', 'S3'])

    def test_memo_98_and_earlier_rounds_are_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))
        for text in REVIEW_8D7_KEPT + REVIEW_9B2_KEPT + REVIEW_377_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))
        for text, after, changes in REVIEW_8D7_REPAIRED + REVIEW_9B2_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))


class PipelineReviewA6dcddfTests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps the conditional foreign
    claim and the attributed sentence, repairs the pair's clause before an independent one and keeps memo 101's four
    repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('reviewa6d_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        repaired, repaired_after, _ = REVIEW_A6D_REPAIRED[0]
        sections = {'market_analysis': REVIEW_A6D_KEPT[0], 'team_assessment': REVIEW_A6D_KEPT[2],
                    'problem_solution': repaired}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_A6D_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_A6D_KEPT[2])
        self.assertEqual(memo.problem_solution, repaired_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# Review of 72418e2: two preservation gaps, both present since a6dcddf.
#     1. "The reported monthly figure [S2], and the larger figure [S3] are overstated." was garbled: the compound-subject
#        and list guards read "reported" (any "-ed" word) as a verb, so the subject was split as two clauses and its
#        second half replaced. A participle after its determiner ("the reported", "the company's stated") modifies the
#        figure; it is not a verb.
#     2. "The monthly figure is overstated (in management's view) [S2, S3]." lost its attribution: only a comma after the
#        judgment left the owner open. What follows the judgment must now be text the clarification may replace:
#        coordinated judgments, hedges, citations and closing punctuation; anything else keeps the clause. The referent
#        rule ("These figures may be inflated (in management's view)") had the same gap.

REVIEW_724_KEPT = (
    PAIR_LEAD + "The reported monthly figure [S2], and the larger figure [S3] are overstated.",
    PAIR_LEAD + "The stated monthly figure [S2], and the larger figure [S3] are overstated.",
    PAIR_LEAD + "The claimed figure [S2], and the larger figure [S3] are overstated.",
    PAIR_LEAD + "The company's reported monthly figure [S2], and the larger figure [S3] are overstated.",
    PAIR_LEAD + "The monthly figure is overstated (in management's view) [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated according to management [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated in management's view [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated [S2, S3] (in management's view).",
    PAIR_LEAD + "These figures may be inflated (in management's view) [S2, S3].",
    PAIR_LEAD + "One or both figures may be overstated according to management [S2, S3].",
    # An object after the judgment is replaceable only when it names the pair's measure (memo 100, below).
    PAIR_LEAD + "One or both figures may misrepresent the scale of hiring [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the hiring plan [S2, S3].",
)
REVIEW_724_REPAIRED = (
    # "reported" with no determiner before it is the clause's verb: two clauses, and the second is the pair's.
    (PAIR_LEAD + "Management reported the monthly figure [S2], and the larger figure [S3] is overstated.",
     PAIR_LEAD + "Management reported the monthly figure [S2], and " + CLARIFY + " [S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The reported figure is monthly [S2], and the larger figure [S3] is overstated.",
     PAIR_LEAD + "The reported figure is monthly [S2], and " + CLARIFY + " [S3].", ['basis_overstatement']),
    # A serial list led by a participle is still one clause, and the clause after it is still its own.
    # Corrected at the review of 8f11844: "daily" is not this pair's interval, so the list is kept.
    (PAIR_LEAD + "The reported, monthly, and daily figures are overstated [S2, S3], but " + UNCLEAR + ".",
     PAIR_LEAD + "The reported, monthly, and daily figures are overstated [S2, S3], but " + UNCLEAR + ".", []),
    (PAIR_LEAD + "The reported, monthly, and cumulative figures are overstated [S2, S3], but " + UNCLEAR + ".",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3], but " + UNCLEAR + ".", ['basis_overstatement']),
    # Coordinated judgments and hedges are replaceable text, in both rules.
    (PAIR_LEAD + "The monthly figure is overstated and possibly misleading [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "One or both figures may be overstated or misleading [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_referent_judgment']),
    # The memo 100 form: an object naming the pair's measure.
    (PAIR_LEAD + "One or both figures may misrepresent the scale of actual activity [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_referent_judgment']),
    # A comparison with the pair's other figure (the BasisGuardTests forms: "overstates the page-10 count").
    (PAIR_LEAD + "The monthly figure is overstated compared with the cumulative figure [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
)


class Review72418e2Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_participle_subjects_and_trailing_attributions_are_kept(self):
        for text in REVIEW_724_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_the_pairs_own_clauses_are_still_repaired(self):
        for text, after, changes in REVIEW_724_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))
                if UNCLEAR in text:
                    self.assertIn(UNCLEAR, after)

    def test_memo_98_and_earlier_rounds_are_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))
        for text in REVIEW_A6D_KEPT + REVIEW_8D7_KEPT + REVIEW_9B2_KEPT + REVIEW_377_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))
        for text, after, changes in REVIEW_A6D_REPAIRED + REVIEW_8D7_REPAIRED + REVIEW_9B2_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))


class PipelineReview72418e2Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps the participle compound
    subject and both trailing attributions, repairs the pair's clause after a reporting verb and keeps memo 101's four
    repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review724_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        repaired, repaired_after, _ = REVIEW_724_REPAIRED[0]
        sections = {'market_analysis': REVIEW_724_KEPT[0], 'team_assessment': REVIEW_724_KEPT[4],
                    'financial_analysis': REVIEW_724_KEPT[8], 'problem_solution': repaired}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_724_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_724_KEPT[4])
        self.assertEqual(memo.financial_analysis, REVIEW_724_KEPT[8])
        self.assertEqual(memo.problem_solution, repaired_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# Review of 71ece83: the tail allowlist accepted any page and any basis word, so a comparison with something that is
# not the pair's ("compared with the page-99 count", "compared with the yearly count") was deleted by the
# clarification, in both rules. Present at 72418e2 too. A page after the judgment must be one the pair's members are on
# and a basis word one of the pair's own bases (memo 101: pages 10 and 12; unstated and monthly, the unstated side
# being the one the memos call "cumulative").

REVIEW_71E_KEPT = (
    PAIR_LEAD + "The monthly figure is overstated compared with the page-99 count [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the page 99 count [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the slide-7 figure [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the weekly figure [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the daily count [S2, S3].",
    PAIR_LEAD + "The monthly figure is overstated compared with the run-rate [S2, S3].",
    PAIR_LEAD + "These figures are overstated compared with the yearly count [S2, S3].",
    PAIR_LEAD + "One or both figures may be overstated compared with the yearly count [S2, S3].",
    PAIR_LEAD + "One or both figures may misrepresent the page-99 count [S2, S3].",
    PAIR_LEAD + "These figures may overstate the weekly activity [S2, S3].",
)
REVIEW_71E_REPAIRED = (
    (PAIR_LEAD + "The monthly figure is overstated compared with the page-10 count [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The monthly figure is overstated compared with the page 10 count [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The monthly figure is overstated compared with the slide-12 figure [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The page-10 figure is overstated compared with the per month figure [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "These figures are overstated compared with the monthly count [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_referent_judgment']),
    (PAIR_LEAD + "One or both figures may overstate the page-12 count [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_referent_judgment']),
    (PAIR_LEAD + "These figures may overstate the monthly activity [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_referent_judgment']),
    # "interval" names no other figure.
    (PAIR_LEAD + "The monthly figure is overstated relative to its stated interval [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
)


class Review71ece83Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload; and per pair,
    with three pairs on different pages and bases."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def pairs(self, text):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(_pairs_items(), (NOTE, NOTE_BOTS, NOTE_CUMULATIVE)))

    def test_comparisons_with_other_pages_and_intervals_are_kept(self):
        for text in REVIEW_71E_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_comparisons_with_the_pairs_own_pages_and_intervals_are_repaired(self):
        for text, after, changes in REVIEW_71E_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))

    def test_pages_and_intervals_are_each_pairs_own(self):
        cumulative = 'How the cumulative figure relates to the weekly figure needs clarification before either is relied on'
        for text, expected in (
                # Another pair's page or interval is not this pair's.
                ('The daily bot figure [C6] is overstated compared with the page-12 bot count [C5].', None),
                ('The daily bot figure [C6] is overstated compared with the monthly bot count [C5].', None),
                ('The weekly figure [C9] is overstated compared with the daily figure [C7].', None),
                ('The weekly figure [C9] is overstated compared with the page-10 figure [C7].', None),
                # Its own are.
                ('The daily bot figure [C6] is overstated compared with the page-5 bot count [C5].',
                 DAILY_CLARIFICATION + ' [C6] [C5].'),
                ('The weekly figure [C9] is overstated compared with the cumulative figure [C7].',
                 cumulative + ' [C9] [C7].'),
                ('The weekly figure [C9] is overstated compared with the page-7 figure [C7].',
                 cumulative + ' [C9] [C7].')):
            with self.subTest(text=text):
                out, changes = self.pairs(text)
                self.assertEqual(out, text if expected is None else expected)
                self.assertEqual(bool(changes), expected is not None)

    def test_a_pair_of_two_stated_rates_has_no_cumulative_side(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = [_usage('C10', '4M messages/month', 3), _usage('C11', '4M messages/day', 4)]
        note = ('measurement_basis', ('C10', 'C11'), 'Page 3 states 4M messages/month; page 4 states 4M messages/day. '
                'These use different measurement bases and need clarification before comparison.')
        facts = basis_facts(items, (note,))
        kept = 'The daily figure [C11] is overstated compared with the cumulative activity [C10].'
        self.assertEqual(guard_basis_wording(kept, facts), (kept, []))
        self.assertEqual(
            guard_basis_wording('The daily figure [C11] is overstated compared with the monthly activity [C10].', facts),
            ('How the monthly figure relates to the daily figure needs clarification before either is relied on '
             '[C11] [C10].', ['basis_overstatement']))

    def test_earlier_rounds_are_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))
        for text in REVIEW_724_KEPT + REVIEW_A6D_KEPT + REVIEW_8D7_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))
        for text, after, changes in REVIEW_724_REPAIRED + REVIEW_A6D_REPAIRED + REVIEW_8D7_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))


class PipelineReview71ece83Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps comparisons with another
    page and another interval, in both rules, repairs the pair's own page-10 comparison and keeps memo 101's repairs."""

    def test_the_writer_keeps_them(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('review71e_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo101_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, _ = memo101()
        repaired, repaired_after, _ = REVIEW_71E_REPAIRED[0]
        sections = {'market_analysis': REVIEW_71E_KEPT[0], 'team_assessment': REVIEW_71E_KEPT[6],
                    'financial_analysis': REVIEW_71E_KEPT[8], 'problem_solution': repaired}
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_71E_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_71E_KEPT[6])
        self.assertEqual(memo.financial_analysis, REVIEW_71E_KEPT[8])
        self.assertEqual(memo.problem_solution, repaired_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)


# Review of 8f11844: two disclosed gaps, both present before this branch's recent rounds.
#     1. A subject naming a page or interval the pair does not have was still the pair's: "The page-99 figure is
#        overstated [S2, S3]" and "The yearly figure is overstated [S2, S3]" became the clarification (memo 101's pair:
#        pages 10 and 12, unstated and monthly). Subject qualifiers now use the same pair-specific reading as the text
#        after the judgment. Three earlier expectations that a list naming "daily" is rewritten are corrected to kept;
#        each gains a list of the pair's own words that is still repaired as one clause.
#     2. For a pair of two stated rates (monthly and daily), "the cumulative figure [C10]" became "the figure stated
#        without an explicit interval [C10]", and "the cumulative and daily figures" became "the unspecified-interval
#        and daily figures", although both sides state an interval. Both relabels now need a side with no stated
#        interval.

REVIEW_8F1_KEPT = (
    PAIR_LEAD + "The page-99 figure is overstated [S2, S3].",
    PAIR_LEAD + "The yearly figure is overstated [S2, S3].",
    PAIR_LEAD + "The slide-7 figure is overstated [S2, S3].",
    PAIR_LEAD + "The weekly figure is overstated compared with the monthly figure [S2, S3].",
    PAIR_LEAD + "The page-99 monthly figure is overstated [S2, S3].",
    PAIR_LEAD + "The run-rate figure is overstated [S2, S3].",
    PAIR_LEAD + "The 500M messages/week figure is overstated [S2, S3].",
    PAIR_LEAD + "The costs/month figure is overstated [S2, S3].",
    PAIR_LEAD + "If the figures are monthly, the implied weekly activity is overstated [S2, S3].",
    PAIR_LEAD + "The monthly figure is accurate [S2], and the daily figure [S3] is overstated.",
)
REVIEW_8F1_REPAIRED = (
    (PAIR_LEAD + "The page-10 figure is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The slide-12 monthly figure is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The cumulative figure is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The 500M messages/month figure is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "If the figures are monthly, the implied monthly activity is overstated [S2, S3].",
     PAIR_LEAD + CLARIFY_SENTENCE + " [S2, S3].", ['basis_overstatement']),
    (PAIR_LEAD + "The monthly figure is accurate [S2], and the larger figure [S3] is overstated.",
     PAIR_LEAD + "The monthly figure is accurate [S2], and " + CLARIFY + " [S3].", ['basis_overstatement']),
)
TWO_RATE_ITEMS = lambda: [_usage('C10', '4M messages/month', 3), _usage('C11', '4M messages/day', 4)]
TWO_RATE_NOTE = ('measurement_basis', ('C10', 'C11'), 'Page 3 states 4M messages/month; page 4 states 4M messages/day. '
                 'These use different measurement bases and need clarification before comparison.')
TWO_RATE_KEPT = (
    'The daily figure [C11] is overstated compared with the cumulative figure [C10].',
    'The cumulative figure [C10] sits beside a daily rate [C11].',
    'The cumulative and daily figures [C10, C11] differ.',
    'The cumulative and monthly presentations [C10, C11] need clarification.',
)


class Review8f11844Tests(SimpleTestCase):
    """Through the complete normalisation -> time -> funding -> basis sequence on memo 101's payload; the two-rate
    pair through the basis guard, with the single-unstated-side controls (BasisGuardTests' pair) beside it."""

    def setUp(self):
        self.payload = memo101_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'section': text}, self.items, self.notes)
        return out['section'], changes.get('section', [])

    def test_subjects_naming_another_page_or_interval_are_kept(self):
        for text in REVIEW_8F1_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_subjects_naming_the_pairs_own_are_repaired(self):
        for text, after, changes in REVIEW_8F1_REPAIRED:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))

    def test_subjects_are_each_pairs_own(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        facts = basis_facts(_pairs_items(), (NOTE, NOTE_BOTS, NOTE_CUMULATIVE))
        for text, expected in (
                ('The weekly bot figure [C6] is overstated [C5].', None),
                ('The page-6 bot figure [C6] is overstated [C5].', DAILY_CLARIFICATION + ' [C6] [C5].'),
                ('The daily bot figure [C6] is overstated [C5].', DAILY_CLARIFICATION + ' [C6] [C5].'),
                ('The page-12 bot figure [C6] is overstated [C5].', None)):
            with self.subTest(text=text):
                out, changes = guard_basis_wording(text, facts)
                self.assertEqual(out, text if expected is None else expected)
                self.assertEqual(bool(changes), expected is not None)

    def test_a_pair_of_two_stated_rates_gains_no_unstated_interval(self):
        from .basis_fidelity import basis_facts, guard_basis_wording, UNSPECIFIED, UNSPECIFIED_ADJECTIVE
        facts = basis_facts(TWO_RATE_ITEMS(), (TWO_RATE_NOTE,))
        for text in TWO_RATE_KEPT:
            with self.subTest(text=text):
                out, changes = guard_basis_wording(text, facts)
                self.assertEqual((out, changes), (text, []))
                self.assertNotIn(UNSPECIFIED[4:], out)
                self.assertNotIn(UNSPECIFIED_ADJECTIVE, out)

    def test_a_pair_with_an_unstated_side_is_still_relabelled(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = [_usage('C2', '500M messages/month', 12), _usage('C3', '500M messages', 10)]
        facts = basis_facts(items, (NOTE,))
        self.assertEqual(guard_basis_wording('The cumulative figure [C3] sits beside a monthly rate [C2].', facts),
                         ('The figure stated without an explicit interval [C3] sits beside a monthly rate [C2].',
                          ['basis_cumulative_referent']))
        self.assertEqual(guard_basis_wording('The cumulative and monthly figures [C3, C2] differ.', facts),
                         ('The unspecified-interval and monthly figures [C3, C2] differ.',
                          ['basis_cumulative_presupposed']))

    def test_an_admitted_cumulative_side_is_never_relabelled_beside_an_unstated_one(self):
        # A pair of a cumulative side and an unstated side: "cumulative" names the admitted side, so neither relabel
        # applies, although the pair has a side with no stated interval.
        from .basis_fidelity import basis_facts, guard_basis_wording
        items = [_usage('C7', '3M messages to date', 7), _usage('C8', '3M messages', 8)]
        note = ('measurement_basis', ('C7', 'C8'), 'Page 7 states 3M messages as a cumulative total; page 8 states 3M '
                'messages without an explicit interval. These use different measurement bases and need clarification '
                'before comparison.')
        facts = basis_facts(items, (note,))
        for text in ('The cumulative figure [C7] sits beside the figure on page 8 [C8].',
                     'The cumulative and monthly presentations [C7, C8] differ.'):
            with self.subTest(text=text):
                self.assertEqual(guard_basis_wording(text, facts), (text, []))

    def test_earlier_rounds_are_unchanged(self):
        self.assertEqual(self.full(MEMO98_JUDGMENT), (RISK_AFTER[:-1] + ' [C2, C3].', ['basis_overstatement']))
        for text in REVIEW_71E_KEPT + REVIEW_724_KEPT + REVIEW_A6D_KEPT + REVIEW_8D7_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))
        for text, after, changes in (REVIEW_71E_REPAIRED + REVIEW_724_REPAIRED + REVIEW_A6D_REPAIRED +
                                     REVIEW_8D7_REPAIRED):
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (after, changes))


class PipelineReview8f11844Tests(TestCase):
    """The memo writer (intelligence_pipeline._generate_memo, model response mocked) keeps subjects naming another page
    or interval and repairs the pair's own (memo 101's payload); and for a pair of two stated rates, relabels
    nothing as unstated."""

    def _context(self, username, items, notes):
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .vector_models import DocumentSource
        user = get_user_model().objects.create_user(username, password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        return doc, GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items),
                                    gaps=(), verification='complete', analysis_confidence=0.5,
                                    consistency_notes=tuple(notes))

    def _write(self, context, sections):
        from unittest import mock
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        raw, _ = memo101()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw, **sections)):
            pipeline._generate_memo(context)

    def test_the_writer_keeps_another_figures_subject(self):
        from .vector_models import IntelligenceMemo
        payload = memo101_payload()
        doc, context = self._context('review8f1_writer', items_from(payload), notes_from(payload))
        repaired, repaired_after, _ = REVIEW_8F1_REPAIRED[0]
        self._write(context, {'market_analysis': REVIEW_8F1_KEPT[0], 'team_assessment': REVIEW_8F1_KEPT[1],
                              'problem_solution': repaired})
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, REVIEW_8F1_KEPT[0])
        self.assertEqual(memo.team_assessment, REVIEW_8F1_KEPT[1])
        self.assertEqual(memo.problem_solution, repaired_after)
        self.assertIn(BMA_101_AFTER, memo.business_model_analysis)
        self.assertIn(BASE_101_AFTER, memo.base_scenario)
        self.assertIn(RISK_101_AFTER, memo.risk_assessment)
        self.assertIn(DOWN_101_AFTER, memo.downside_scenario)

    def test_the_writer_relabels_nothing_for_two_stated_rates(self):
        from .vector_models import IntelligenceMemo
        doc, context = self._context('review8f1_two_rate', TWO_RATE_ITEMS(), (TWO_RATE_NOTE,))
        repaired = 'The daily figure [C11] is overstated compared with the monthly activity [C10].'
        self._write(context, {'market_analysis': TWO_RATE_KEPT[0], 'team_assessment': TWO_RATE_KEPT[2],
                              'problem_solution': repaired})
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.market_analysis, TWO_RATE_KEPT[0])
        self.assertEqual(memo.team_assessment, TWO_RATE_KEPT[2])
        # Positive control: the guard ran on this pair.
        self.assertEqual(memo.problem_solution, 'How the monthly figure relates to the daily figure needs clarification '
                                                'before either is relied on [C11] [C10].')


# --- Memo 102 (ManyChat, document 3144, live at d0bad8f; independent grade f2a282f) ------------------------------
#
#     OF-1003  base_scenario: "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by
#              Apr-16' framing, ManyChat had reached meaningful platform scale at that point in time." S3 is page
#              12's monthly statement with no supplied context; "taken at face value" does not give it page 10's
#              date. P2, blocking.
#     OF-1004  open_concerns and business_model_analysis cite page 12's monthly figure [C3, S3]; C3 is page 10's
#              claim (C3 / S2: page 10, 500M messages, interval unstated; C2 / S3: page 12, 500M messages/month).
#              P2, blocking. OF-1005 is not an additional blocker: the sentence places the monthly figure
#              "elsewhere [S3]".
#
# The fixtures are memo 102's payload as sent and its raw reply (data/funding_fidelity/memo102*.json, from the
# committed evidence 6d131f5). Memo 102 itself is not edited; these tests replay its reply.

def memo102():
    with open(os.path.join(DATA, 'memo102.json'), encoding='utf-8') as f:
        data = json.load(f)
    return json.loads(re.search(r'\{.*\}', data['model_reply_text'], re.S).group(0)), data['stored']


def memo102_payload():
    with open(os.path.join(DATA, 'memo102_payload.json'), encoding='utf-8') as f:
        return json.load(f)['payload']


BASE_102_BEFORE = ("If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, "
                   "ManyChat had reached meaningful platform scale at that point in time.")
BASE_102_AFTER = ("If the traction figures [S1, S2] are taken at face value under the 'Traction by Apr-16' framing, "
                  "ManyChat had reached meaningful platform scale at that point in time; the deck separately states 500M "
                  "messages/month [S3] on page 12 (" + CLARIFY + ").")
OPEN_102_BEFORE = "while a separate page states '500M messages/month' [C3, S3]."
OPEN_102_AFTER = "while a separate page states '500M messages/month' [C2, S3]."
BMA_102_BEFORE = "see consistency note on [C3, S2] vs [C3, S3])"
BMA_102_AFTER = "see consistency note on [C3, S2] vs [C2, S3])"
# OF-1005: the same sentence's own placing, unchanged.
BMA_102_PLACES = ("in a slide headed 'Traction by Apr-16' [S1, S2], and 500M messages/month elsewhere [S3], indicating "
                  "platform-level usage")
UPSIDE_102 = "If the 500M messages figure reflects a monthly run rate [S3] rather than a cumulative total"
DOWN_102 = "If the 500M messages figure [C3, S2] is a cumulative total rather than a monthly rate"
QUESTION_102 = "The deck presents both framings [C3, S2 vs S3]"
RISK_102 = "'500M messages' without an explicit interval on page 10 (slide headed 'Traction by Apr-16') [C3, S2] and '500M messages/month' on page 12 [C2, S3]"
COMPARE_102 = ("the two slides present conflicting bases [C3, C2]", "and as a monthly figure on another [C3, C2]",
               "All traction figures — none independently verified [C2, C3, C4, S1, S2, S3]")
CHANGED_102 = {'business_model_analysis', 'open_concerns', 'base_scenario'}


class Memo102ReplayTests(SimpleTestCase):
    """The actual memo-102 reply through the pipeline's guards: the two graded defects change, nothing else."""

    def setUp(self):
        self.raw, self.stored = memo102()
        self.payload = memo102_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)
        self.out, self.changes = replay(self.raw, self.items, self.notes)

    def test_the_fixture_is_memo_102_as_stored(self):
        for text, key in ((BASE_102_BEFORE, 'base_scenario'), (OPEN_102_BEFORE, 'open_concerns'),
                          (BMA_102_BEFORE, 'business_model_analysis'), (BMA_102_PLACES, 'business_model_analysis'),
                          (UPSIDE_102, 'upside_scenario'), (DOWN_102, 'downside_scenario'),
                          (QUESTION_102, 'questions_for_management'), (RISK_102, 'risk_assessment')):
            self.assertIn(text, self.stored[key], key)
        self.assertEqual(self.notes[0][1], ('C3', 'C2'))
        sources = {i['ref']: (i['statement'], i['sources'][0].get('page'), i.get('source_context'))
                   for i in self.payload['items']}
        self.assertEqual(sources['C3'], ('500M messages', 10, 'Traction by Apr-16'))
        self.assertEqual(sources['S2'], ('500M messages', 10, 'Traction by Apr-16'))
        self.assertEqual(sources['C2'], ('500M messages/month', 12, None))
        self.assertEqual(sources['S3'], ('500M messages/month', 12, None))

    def test_of1003_page_12_is_not_dated_by_page_10_s_heading(self):
        self.assertEqual(self.out['base_scenario'], self.stored['base_scenario'].replace(BASE_102_BEFORE, BASE_102_AFTER))

    def test_of1004_the_monthly_figure_cites_its_own_claim(self):
        self.assertEqual(self.out['open_concerns'], self.stored['open_concerns'].replace(OPEN_102_BEFORE, OPEN_102_AFTER))
        # The page-10 figure's own correct citation, earlier in the same sentence, is unchanged.
        self.assertIn("states '500M messages' without an interval [C3, S2], while", self.out['open_concerns'])

    def test_of1004_the_monthly_operand_cites_its_own_claim(self):
        self.assertEqual(self.out['business_model_analysis'],
                         self.stored['business_model_analysis'].replace(BMA_102_BEFORE, BMA_102_AFTER))
        self.assertIn(BMA_102_PLACES, self.out['business_model_analysis'])

    def test_hypotheses_questions_and_comparisons_are_kept(self):
        self.assertIn(UPSIDE_102, self.out['upside_scenario'])
        self.assertIn(DOWN_102, self.out['downside_scenario'])
        self.assertIn(QUESTION_102, self.out['questions_for_management'])
        self.assertIn(RISK_102, self.out['risk_assessment'])
        joined = '\n'.join(v for v in self.out.values() if isinstance(v, str))
        for text in COMPARE_102:
            self.assertIn(text, joined)

    def test_every_other_field_is_exactly_as_stored(self):
        for key, value in self.out.items():
            if key in self.stored and key not in CHANGED_102:
                self.assertEqual(value, self.stored[key], key)

    def test_citations_change_only_where_corrected(self):
        for key, value in self.out.items():
            if isinstance(value, str) and key in self.stored:
                expected = refs(self.stored[key])
                if key == 'open_concerns':
                    expected[expected.index('S3') - 1] = 'C2'
                if key == 'business_model_analysis':
                    self.assertEqual(expected[:4], ['C3', 'S2', 'C3', 'S3'])
                    expected[2] = 'C2'
                self.assertEqual(refs(value), expected, key)

    def test_every_citation_names_a_supplied_ref(self):
        supplied = {i['ref'] for i in self.payload['items']}
        for key, value in self.out.items():
            if isinstance(value, str):
                self.assertLessEqual(set(refs(value)), supplied, key)

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
            'business_model_analysis': ['basis_citation_identity'],
            'open_concerns': ['basis_citation_identity'],
            'base_scenario': ['basis_condition_context'],
            'information_readiness': ['attribution:Pitch Deck Hunt'],
        })

    def test_earlier_memos_get_neither_new_rule(self):
        for n in (96, 98, 99, 100, 101):
            with open(os.path.join(DATA, f'memo{n}.json'), encoding='utf-8') as f:
                raw = json.loads(re.search(r'\{.*\}', json.load(f)['model_reply_text'], re.S).group(0))
            with open(os.path.join(DATA, f'memo{n}_payload.json'), encoding='utf-8') as f:
                payload = json.load(f)['payload']
            _, changes = replay(raw, items_from(payload), notes_from(payload))
            fired = {rule for rules in changes.values() for rule in rules}
            with self.subTest(memo=n):
                self.assertFalse(fired & {'basis_citation_identity', 'basis_citation_identity_unresolved',
                                          'basis_condition_context'}, fired)


class Memo102StoredSectionsTests(SimpleTestCase):
    """The stored memo-102 text through the basis guard: the same three repairs, nothing else."""

    def test_the_stored_sections_get_the_same_repairs(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        payload = memo102_payload()
        facts = basis_facts(items_from(payload), notes_from(payload))
        _, stored = memo102()
        out = {key: guard_basis_wording(value, facts)[0] for key, value in stored.items()}
        self.assertIn(BASE_102_AFTER, out['base_scenario'])
        self.assertIn(OPEN_102_AFTER, out['open_concerns'])
        self.assertIn(BMA_102_AFTER, out['business_model_analysis'])
        self.assertEqual({k for k in stored if out[k] != stored[k]}, CHANGED_102)


class PipelineMemo102Tests(TestCase):
    """The memo writer itself (intelligence_pipeline._generate_memo) stores the repaired memo-102 reply."""

    def test_the_stored_memo_carries_the_repairs(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from .grounded_context import GroundedContext
        from .intelligence_pipeline import ZeldaIntelligencePipelineV2
        from .vector_models import DocumentSource, IntelligenceMemo
        user = get_user_model().objects.create_user('memo102_writer', password='x')
        doc = DocumentSource.objects.create(filename='mc.pptx', source_entity='ManyChat', uploaded_by=user,
                                            document_type='pitch_deck')
        payload = memo102_payload()
        context = GroundedContext(document_id=doc.id, company='ManyChat', built_for='test', items=tuple(items_from(payload)),
                                  gaps=(), verification='complete', analysis_confidence=0.5,
                                  consistency_notes=notes_from(payload))
        raw, stored = memo102()
        pipeline = ZeldaIntelligencePipelineV2()
        with mock.patch.object(pipeline, '_call_claude_for_memo', return_value=dict(raw)):
            pipeline._generate_memo(context)
        memo = IntelligenceMemo.objects.get(document_id=doc.id)
        self.assertEqual(memo.base_scenario, stored['base_scenario'].replace(BASE_102_BEFORE, BASE_102_AFTER))
        self.assertEqual(memo.open_concerns, stored['open_concerns'].replace(OPEN_102_BEFORE, OPEN_102_AFTER))
        self.assertEqual(memo.business_model_analysis,
                         stored['business_model_analysis'].replace(BMA_102_BEFORE, BMA_102_AFTER))
        for key in ('executive_summary', 'information_readiness', 'supported_points', 'risk_assessment',
                    'upside_scenario', 'downside_scenario', 'zelda_advantage', 'financial_analysis',
                    'questions_for_management'):
            self.assertEqual(getattr(memo, key), stored[key], key)


def _evidence(ref, kind, statement, page, context=''):
    return GroundedItem(ref=ref, kind=kind, category='usage' if kind == 'claim' else 'Traction', statement=statement,
                        status=INSUFFICIENT if kind == 'claim' else SELF_REPORTED,
                        sources=(SourceRef(document_id=1, page_number=page),), source_context=context)


# A second pair with other refs, figures, noun, pages, interval and context: the rules are not memo 102's strings.
OTHER_PAIR_ITEMS = lambda: [_evidence('C7', 'claim', '3M bots', 7, 'Growth by Q3-19'),
                            _evidence('C8', 'claim', '3M bots/week', 8),
                            _evidence('S7', 'statement', '3M bots', 7, 'Growth by Q3-19'),
                            _evidence('S8', 'statement', '3M bots/week', 8),
                            _evidence('S9', 'statement', '40 staff', 9)]
OTHER_PAIR_NOTE = ('measurement_basis', ('C7', 'C8'), 'Page 7 states 3M bots; page 8 states 3M bots/week.')
CLARIFY_WEEKLY = ('how the figure stated without an explicit interval relates to the weekly figure needs clarification '
                  'before either is relied on')

IDENTITY_FIXED = (
    ("Page 12 states '500M messages/month' [C3].", "Page 12 states '500M messages/month' [C2]."),
    ("Page 10 states '500M messages' [C2, S3].", "Page 10 states '500M messages' [C3, S2]."),
    ("The deck states 500M messages/month [C3, S3] on page 12.", "The deck states 500M messages/month [C2, S3] on page 12."),
    # Compound sentences: the unrelated fact, its narrator and its qualification keep their citations.
    ("Pitch Deck Hunt lists $23.1M raised [C1, S4], and the deck separately states '500M messages/month' [C3, S3], "
     "which is unverified.",
     "Pitch Deck Hunt lists $23.1M raised [C1, S4], and the deck separately states '500M messages/month' [C2, S3], "
     "which is unverified."),
    ("Compare [C3, S2] versus [C3, S3] before relying on either.",
     "Compare [C3, S2] versus [C2, S3] before relying on either."),
    # A ref outside the pair in the same group is untouched.
    ("The deck states 500M messages/month [C3, S3, P1].", "The deck states 500M messages/month [C2, S3, P1]."),
)
IDENTITY_KEPT = (
    "Page 12 states '500M messages/month' [C2, S3].",
    "Page 10 states '500M messages' without an interval while page 12 states '500M messages/month' [C2, C3].",
    # One group after a list of both figures cites each figure once: C3 is page 10's.
    "Page 10 states '500M messages' and page 12 states '500M messages/month' [C3, S3].",
    # Both operands mixed: which is meant is unknown.
    "Compare [C3, S3] vs [C2, S2] before relying on either.",
    "The monthly figure, '500M messages/month' [C2, C3], needs clarification against page 10.",
    "The deck states 500M messages/month [S2, S3].",
    "The two slides present conflicting bases [C3, C2].",
    "All traction figures are unverified [C2, C3, C4, S1, S2, S3].",
    "The deck presents both framings [C3, S2 vs S3].",
    "Compare [C3, S2] vs [C2, S3] before relying on either.",
    "The deck states 500M messages [C2].",                     # the same number alone names no side
    "The deck states 500M messages/day [C3, S3].",             # an interval neither side states
    "The deck states 140,000+ bots [S1] and 500M messages/month [C2, S3].",
    "Pitch Deck Hunt lists $23.1M raised [C1, S4].",
    "Is '500M messages/month' [C2, S3] a run rate?",
)


class Of1004CitationIdentityTests(SimpleTestCase):
    """OF-1004: a citation group attached to one figure cites that figure's own side; comparisons, lists, other
    figures and correct citations are kept."""

    def setUp(self):
        self.payload = memo102_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'s': text}, self.items, self.notes)
        return out['s'], changes.get('s', [])

    def test_a_figure_s_wrong_claim_becomes_its_own(self):
        for before, after in IDENTITY_FIXED:
            with self.subTest(text=before):
                self.assertEqual(self.full(before), (after, ['basis_citation_identity']))

    def test_comparisons_lists_and_correct_citations_are_kept(self):
        for text in IDENTITY_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def guard(self, text, items=None):
        from .basis_fidelity import basis_facts, guard_basis_wording
        return guard_basis_wording(text, basis_facts(items or OTHER_PAIR_ITEMS(), (OTHER_PAIR_NOTE,)))

    def test_another_pair_s_refs_are_corrected_alike(self):
        self.assertEqual(self.guard("Page 8 states '3M bots/week' [C7, S8]."),
                         ("Page 8 states '3M bots/week' [C8, S8].", ['basis_citation_identity']))
        self.assertEqual(self.guard("See [C7, S7] vs [C7, S8]."), ("See [C7, S7] vs [C8, S8].", ['basis_citation_identity']))
        self.assertEqual(self.guard("The team counts 40 staff [S9] and page 8 states '3M bots/week' [C7, S8]."),
                         ("The team counts 40 staff [S9] and page 8 states '3M bots/week' [C8, S8].",
                          ['basis_citation_identity']))
        for text in ("Page 8 states '3M bots/week' [C8, S8].", "Page 7 states '3M bots' and page 8 states '3M bots/week' [C7, C8].",
                     "The team counts 40 staff [S9]."):
            with self.subTest(text=text):
                self.assertEqual(self.guard(text), (text, []))

    def test_a_side_without_one_statement_is_not_invented(self):
        # Two statements repeat page 8's figure: none can be chosen for a wrong statement ref. With a correct ref of
        # the side beside it, the wrong one is dropped; alone, it is kept and logged as unresolved.
        items = OTHER_PAIR_ITEMS() + [_evidence('S10', 'statement', '3M bots/week', 8)]
        self.assertEqual(self.guard("Page 8 states '3M bots/week' [C8, S7].", items),
                         ("Page 8 states '3M bots/week' [C8].", ['basis_citation_identity']))
        # Both sides' statements are a comparison, as with both claims: kept.
        self.assertEqual(self.guard("Page 8 states '3M bots/week' [S7, S8].", items),
                         ("Page 8 states '3M bots/week' [S7, S8].", []))
        self.assertEqual(self.guard("Page 8 states '3M bots/week' [S7].", items),
                         ("Page 8 states '3M bots/week' [S7].", ['basis_citation_identity_unresolved']))


CONDITION_FIXED = (
    ("If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had "
     "reached meaningful scale, though revenue is not found [C1].",
     "If the traction figures [S1, S2] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had "
     "reached meaningful scale, though revenue is not found [C1]; the deck separately states 500M messages/month [S3] on "
     "page 12 (" + CLARIFY + ")."),
    ("Assuming the traction figures [S1, S2, S3] are accepted as stated under the 'Traction by Apr-16' heading, the "
     "platform was sizeable by then.",
     "Assuming the traction figures [S1, S2] are accepted as stated under the 'Traction by Apr-16' heading, the "
     "platform was sizeable by then; the deck separately states 500M messages/month [S3] on page 12 (" + CLARIFY + ")."),
)
CONDITION_KEPT = (
    # Correct already: only page 10's refs under page 10's heading.
    "If the traction figures [S1, S2] are taken at face value under the 'Traction by Apr-16' framing, ManyChat had "
    "reached meaningful platform scale at that point in time.",
    # Explicit hypotheses about the figure's date or basis.
    "If the 500M messages/month figure [S3] reflects a monthly run rate under the 'Traction by Apr-16' heading, the "
    "platform was sizeable.",
    "If the traction figures [S1, S2, S3] all fall under the 'Traction by Apr-16' heading, the platform was sizeable by then.",
    "If the self-reported figure of 500M messages/month [S3] reflects a monthly run-rate as of the 'Traction by Apr-16' "
    "slide context, the platform was sizeable.",
    "If the 500M messages figure reflects a monthly run rate [S3] rather than a cumulative total, the platform is large.",
    "If the 500M messages figure [C3, S2] is a cumulative total rather than a monthly rate, the implied activity level is lower.",
    # Whether, questions, denials, hedges, another speaker, another metric, a longer antecedent.
    "Whether the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing is unclear.",
    "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, what scale had "
    "ManyChat reached?",
    "If the traction figures [S1, S2, S3] are not taken at face value under the 'Traction by Apr-16' framing, the picture "
    "changes.",
    "If the traction figures [S1, S2, S3] are perhaps taken at face value under the 'Traction by Apr-16' framing, the "
    "picture changes.",
    "If an analyst's figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, the picture changes.",
    "According to an analyst, if the traction figures [S1, S2, S3] are taken at face value under the 'Traction by "
    "Apr-16' framing, the platform was sizeable.",
    # Nothing would stay under the heading: page 12's figure alone (a limitation, not a hypothesis kept by design).
    "If the monthly figure [S3] is taken at face value under the 'Traction by Apr-16' framing, the platform was sizeable.",
    "If the revenue and traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing, the "
    "picture changes.",
    "If the traction figures [S1, S2, S3] are taken at face value under the 'Traction by Apr-16' framing and revenue "
    "follows, the picture changes.",
)


class Of1003ConditionContextTests(SimpleTestCase):
    """OF-1003: a condition that only accepts the figures does not give page 12's figure page 10's heading; explicit
    hypotheses, questions, denials, hedges and other speakers keep their wording and citations."""

    def setUp(self):
        self.payload = memo102_payload()
        self.items, self.notes = items_from(self.payload), notes_from(self.payload)

    def full(self, text):
        out, changes = replay({'s': text}, self.items, self.notes)
        return out['s'], changes.get('s', [])

    def test_an_accepting_condition_does_not_carry_the_heading(self):
        for before, after in CONDITION_FIXED:
            with self.subTest(text=before):
                self.assertEqual(self.full(before), (after, ['basis_condition_context']))

    def test_hypotheses_and_other_conditions_are_kept(self):
        for text in CONDITION_KEPT:
            with self.subTest(text=text):
                self.assertEqual(self.full(text), (text, []))

    def test_a_narrator_s_condition_is_not_the_deck_s(self):
        # The funding guard notes the narrator here (its own rule); the basis guard leaves the citations alone.
        from .basis_fidelity import basis_facts, guard_basis_wording
        text = ("Pitch Deck Hunt suggests that if the traction figures [S1, S2, S3] are taken at face value under the "
                "'Traction by Apr-16' framing, the platform was sizeable.")
        self.assertEqual(guard_basis_wording(text, basis_facts(self.items, self.notes)), (text, []))
        out, changes = self.full(text)
        self.assertNotIn('basis_condition_context', changes)
        self.assertIn('the traction figures [S1, S2, S3]', out)
        self.assertNotIn('the deck separately states', out)

    def test_another_pair_s_context_is_handled_alike(self):
        from .basis_fidelity import basis_facts, guard_basis_wording
        facts = basis_facts(OTHER_PAIR_ITEMS(), (OTHER_PAIR_NOTE,))
        text = "If the usage figures [S7, S8] are taken at face value under the 'Growth by Q3-19' framing, the platform was sizeable then."
        self.assertEqual(guard_basis_wording(text, facts), (
            "If the usage figures [S7] are taken at face value under the 'Growth by Q3-19' framing, the platform was "
            "sizeable then; the deck separately states 3M bots/week [S8] on page 8 (" + CLARIFY_WEEKLY + ").",
            ['basis_condition_context']))
        for kept in ("If the growth figures [S7, S8] are taken at face value under the 'Growth by Q3-19' framing, the "
                     "platform was sizeable then.",
                     "If the usage figures [S7] are taken at face value under the 'Growth by Q3-19' framing, the "
                     "platform was sizeable then."):
            with self.subTest(text=kept):
                self.assertEqual(guard_basis_wording(kept, facts), (kept, []))

    def test_the_affirmative_framing_is_the_context_rule_s(self):
        # "framing" names a context for the merged affirmative rule too.
        text = "The company states 140,000+ bots and 500M messages [S1, S2, S3] under the 'Traction by Apr-16' framing."
        self.assertEqual(self.full(text), (
            "The company states 140,000+ bots and 500M messages [S1, S2] under the 'Traction by Apr-16' framing, and "
            "separately 500M messages/month [S3] on page 12 (" + CLARIFY + ").", ['basis_source_context']))
