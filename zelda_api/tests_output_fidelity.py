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
        text, changes = self.guard('If the cumulative total is shown as monthly, the claim is inflated.', cumulative=True)
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
        text = 'If the cumulative figure is presented as monthly, the claim is materially overstated.'
        self.assertEqual(self.guard(text, notes=()), (text, []))

    def test_idempotent(self):
        once, _ = self.guard('If the cumulative figure is presented as monthly, the claim is materially overstated.')
        self.assertEqual(self.guard(once), (once, []))

    def test_a_list_marker_and_numbering_are_kept(self):
        text, _ = self.guard('1. If the cumulative figure is presented as monthly, the claim is overstated.')
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
