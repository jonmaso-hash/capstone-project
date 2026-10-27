// Runs the assistant panel's real memo/brief renderers (extracted from the
// Django template) against stubbed DOM and fetch, and prints the HTML each one
// produces as JSON. Used by zelda_api/tests_assistant_panel_escaping.py.
//
// Usage: node assistant_panel_escaping.js <path to zelda_ai_assistant_enhanced.html>
// Payload markers are inert markup only (<b>, <i>): the test asserts they come
// out as escaped text, never as elements.
'use strict';
const vm = require('vm');
const { extractFunction, extractConst } = require('./panel_source').panelSource(process.argv[2]);

const FUNCTIONS = ['zeldaEscape', 'addLogEntry', 'renderDisclaimerFooter', 'initPopovers',
    'renderLockedMemoCard', 'renderLiteMemo', 'fetchMemoWhenReady', 'renderMemoGenerating',
    'renderMemoFailed', 'renderMemoTimedOut', 'loadMemo', 'loadIntelligenceBrief'];
const code = [extractConst('ZELDA_LITE_SECTIONS'), ...FUNCTIONS.map(extractFunction)].join('\n\n');

function makeSandbox(respond) {
    const elements = {};
    const logEntries = [];
    const element = id => elements[id] || (elements[id] = {
        id, innerHTML: '', value: '', style: {}, scrollTop: 0, scrollHeight: 0,
        appendChild(child) { logEntries.push(child); }, querySelectorAll() { return []; },
    });
    const sandbox = {
        document: { getElementById: element, createElement: () => ({ className: '', innerHTML: '' }) },
        fetch: async () => respond(),
        getCookie: () => 'csrf', ZELDA_API: '/api/v1/zelda',
        ZELDA_MEMO_POLL_INTERVAL_MS: 1, ZELDA_MEMO_POLL_TIMEOUT_MS: 1, _zeldaMemoPolls: {},
        renderConfidenceGauge: () => {}, bootstrap: { Popover: { getInstance: () => null } },
        console: { log() {} }, setTimeout, Promise, JSON, Math, String, Date, Error, SyntaxError,
    };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    return { sandbox, element, logEntries };
}

const ok = payload => () => ({ status: 200, ok: true, json: async () => payload });
const badJson = () => ({
    status: 200, ok: true,
    // What Chrome reports when an HTML error page is parsed as JSON: the
    // message quotes the start of the response body.
    json: async () => { throw new SyntaxError('Unexpected token \'<\', "<b>bold-marker</b>" is not valid JSON'); },
});

const MARK = '<b>bold-marker</b>';
const SCENARIOS = {
    full: ok({
        locked: false, document_name: `Name ${MARK} & Co`, evidence_level: `LITTLE_EVIDENCE ${MARK}`,
        citations_count: `3 ${MARK}`, completeness_score: 0.4,
        sections: {
            executive_summary: `Line one [S1]\n${MARK} & more [S2]`,
            questions_for_management: '- First question [S3]\n- <i>q-marker</i> second [C1]',
        },
        insights_cited: [{ category: '<b>cat-marker</b>', text: `Insight ${MARK} [S4]`, confidence: 80 }],
        disclaimer: `Disclaimer ${MARK}`,
    }),
    lite: ok({
        locked: true, is_owner: false, tier: 'lite', document_name: `Name ${MARK} & Co`,
        lite_sections: {
            supported_points: `- ${MARK} point [S1]\n- second point [S2]`,
            // Not a Lite key: the renderer must not show it even if it arrived.
            executive_summary: 'FULL-ONLY-SECTION-MARKER',
        },
        disclaimer: `Disclaimer ${MARK}`,
    }),
    locked: ok({ locked: true, is_owner: false, document_name: `Name ${MARK} & Co` }),
    failed: ok({ status: 'failed', error: `Failed ${MARK}` }),
    bad_json: badJson,
};

(async () => {
    const results = {};
    for (const [view, respond] of Object.entries(SCENARIOS)) {
        // Memo tab
        {
            const { sandbox, element, logEntries } = makeSandbox(respond);
            element('memo-doc-id').value = '3133';
            await vm.runInContext('loadMemo()', sandbox);
            results[`memo:${view}`] = {
                html: element('memo-content').innerHTML,
                log: logEntries.map(e => e.innerHTML).join('\n'),
            };
        }
        // Intelligence tab
        {
            const { sandbox, element, logEntries } = makeSandbox(respond);
            await vm.runInContext('loadIntelligenceBrief(3133)', sandbox);
            results[`intelligence:${view}`] = {
                html: element('intelligence-content').innerHTML,
                log: logEntries.map(e => e.innerHTML).join('\n'),
            };
        }
    }
    process.stdout.write(JSON.stringify(results));
})().catch(err => { console.error(err && err.stack || err); process.exit(1); });
