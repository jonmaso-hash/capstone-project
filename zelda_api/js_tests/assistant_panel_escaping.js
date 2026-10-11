// Runs the assistant panel's real memo/brief renderers (extracted from the
// Django template) against stubbed DOM and fetch, and prints the HTML each one
// produces as JSON. Used by zelda_api/tests_assistant_panel_escaping.py.
//
// Usage: node assistant_panel_escaping.js <path to zelda_ai_assistant_enhanced.html>
// Payload markers are inert markup only (<b>, <i>): the test asserts they come
// out as escaped text, never as elements.
'use strict';
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync(process.argv[2], 'utf8').replace(/\r\n/g, '\n');

function prevSignificant(src, i) {
    let j = i - 1;
    while (j >= 0 && /\s/.test(src[j])) j--;
    return j >= 0 ? src[j] : '(';
}

// Index just past the brace/bracket that closes the one opening at `open`,
// skipping strings, comments and template literals (including ${} nesting).
function matchClose(src, open) {
    const closer = { '{': '}', '[': ']' };
    const stack = [closer[src[open]]];
    let i = open + 1;
    const templateDepth = [];       // stack depths at which a `${` opened
    while (i < src.length && stack.length) {
        const ch = src[i];
        const top = stack[stack.length - 1];
        if (top === '`') {
            if (ch === '\\') { i += 2; continue; }
            if (ch === '`') { stack.pop(); i++; continue; }
            if (ch === '$' && src[i + 1] === '{') { stack.push('}'); templateDepth.push(stack.length); i += 2; continue; }
            i++; continue;
        }
        if (ch === '/' && src[i + 1] === '/') { i = src.indexOf('\n', i); continue; }
        if (ch === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i) + 2; continue; }
        if (ch === '/' && /[(,=:[!&|?{};]/.test(prevSignificant(src, i))) {
            // A regex literal (e.g. /[&<>"']/g): skip it, honouring classes and escapes.
            let j = i + 1, inClass = false;
            while (j < src.length && (src[j] !== '/' || inClass)) {
                if (src[j] === '\\') j++;
                else if (src[j] === '[') inClass = true;
                else if (src[j] === ']') inClass = false;
                j++;
            }
            i = j + 1; continue;
        }
        if (ch === '"' || ch === "'") {
            let j = i + 1;
            while (src[j] !== ch) { if (src[j] === '\\') j++; j++; }
            i = j + 1; continue;
        }
        if (ch === '`') { stack.push('`'); i++; continue; }
        if (ch === '{' || ch === '[') { stack.push(closer[ch]); i++; continue; }
        if (ch === top) {
            if (ch === '}' && templateDepth[templateDepth.length - 1] === stack.length) templateDepth.pop();
            stack.pop(); i++; continue;
        }
        i++;
    }
    return i;
}

function extractFunction(name) {
    const re = new RegExp(`\\n    (async )?function ${name}\\(`);
    const m = re.exec(source);
    if (!m) throw new Error(`function ${name} not found`);
    const start = m.index + 1;
    return source.slice(start, matchClose(source, source.indexOf('{', source.indexOf(')', start))));
}

function extractConst(name) {
    const start = source.indexOf(`const ${name} =`);
    if (start < 0) throw new Error(`const ${name} not found`);
    const open = source.indexOf('[', start);
    return source.slice(start, matchClose(source, open)) + ';';
}

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
