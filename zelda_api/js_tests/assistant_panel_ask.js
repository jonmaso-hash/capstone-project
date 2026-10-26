// Runs the assistant panel's real Ask functions (extracted from the Django
// template) against a stubbed DOM and a fetch whose answers the scenario
// releases in any order, and prints what each scenario left on screen as JSON.
// Used by zelda_api/tests_assistant_panel_ask.py (RA-114; review of 8d08fe5:
// a delayed answer rendered under another document's context).
//
// Usage: node assistant_panel_ask.js <path to zelda_ai_assistant_enhanced.html>
'use strict';
const vm = require('vm');
const { source, extractFunction } = require('./panel_source').panelSource(process.argv[2]);

function statement(prefix) {
    const line = source.split('\n').find(l => l.trim().startsWith(prefix));
    if (!line) throw new Error(`statement ${prefix} not found`);
    return line.trim();
}

const code = [
    statement('let zeldaAskDocument ='), statement('let zeldaAskRequest ='), statement('const ZELDA_ASK_PLACEHOLDER ='),
    ...['zeldaEscape', 'addLogEntry', 'setZeldaAskDocument', 'zeldaAskBody', 'renderDocumentEvidence',
        'renderSearchResults', 'submitZeldaAsk'].map(extractFunction),
].join('\n\n');

function makeSandbox() {
    const elements = {};
    const log = [];
    const calls = [];
    const element = id => elements[id] || (elements[id] = {
        id, innerHTML: '', value: '', textContent: '', placeholder: id === 'zeldaAskQuery' ? 'MARKETPLACE-PLACEHOLDER' : '',
        style: {}, scrollTop: 0, scrollHeight: 0,
        appendChild(child) { log.push(child.innerHTML); }, querySelectorAll() { return []; },
    });
    const sandbox = {
        document: { getElementById: element, createElement: () => ({ className: '', innerHTML: '' }) },
        fetch: (url, options) => new Promise((resolve, reject) => calls.push({
            url, body: JSON.parse(options.body),
            answer: payload => resolve({ status: 200, ok: true, json: async () => payload }),
            fail: message => reject(new Error(message)),
        })),
        getCookie: () => 'csrf', ZELDA_API: '/api/v1/zelda', analyzeFounderWithZelda: () => {},
        console: { log() {} }, Promise, JSON, Math, String, Number, Array, Date, Error,
    };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    const run = expr => vm.runInContext(expr, sandbox);
    const screen = () => ({
        context: element('zelda-ask-document-name').textContent,
        card: element('ask-results-card').style.display || '',
        list: element('ask-results-list').innerHTML,
        log: log.map(entry => entry.replace(/^<strong>\[[^\]]*\]<\/strong>\s*/, '')),
        bodies: calls.map(call => call.body),
    });
    return { run, calls, screen };
}

const evidence = (page, text) => ({ status: 'success', response: `1 passage (page ${page}).`, evidence: [
    { chunk_id: page, page, section: '', text, relevance: 0.3 }], no_relevant_evidence: false, results: [] });
const A = evidence(2, 'DECK-A-EXCERPT');
const B_OLD = evidence(3, 'DECK-B-OLDER-EXCERPT');
const B_NEW = evidence(2, 'DECK-B-NEWER-EXCERPT');
const MARKET = { status: 'success', response: 'Found 1 founder.', results: [
    { type: 'Founder Profile', title: 'MARKET-CARD', url: '/f/1', description: '' }] };

const SCENARIOS = {
    // The current answer renders: the positive control.
    current_answer: async ({ run, calls }) => {
        run("setZeldaAskDocument(1, 'Deck A')");
        const pending = run("submitZeldaAsk('How much has A raised?')");
        calls[0].answer(A); await pending;
    },
    // The reviewer's case: ask about A, choose B before A answers.
    switched_document: async ({ run, calls }) => {
        run("setZeldaAskDocument(1, 'Deck A')");
        const pending = run("submitZeldaAsk('How much has A raised?')");
        run("setZeldaAskDocument(2, 'Deck B')");
        calls[0].answer(A); await pending;
    },
    // Two questions on one document; the newer is answered first.
    newer_question_wins: async ({ run, calls }) => {
        run("setZeldaAskDocument(2, 'Deck B')");
        const older = run("submitZeldaAsk('older question')");
        const newer = run("submitZeldaAsk('newer question')");
        calls[1].answer(B_NEW); await newer;
        calls[0].answer(B_OLD); await older;
    },
    // Back to the marketplace while a document answer is pending.
    cleared_while_pending: async ({ run, calls }) => {
        run("setZeldaAskDocument(2, 'Deck B')");
        const pending = run("submitZeldaAsk('How much has B raised?')");
        run('setZeldaAskDocument(null)');
        calls[0].answer(B_OLD); await pending;
    },
    // A stale failure or refusal says nothing about the current context either.
    stale_error: async ({ run, calls }) => {
        run("setZeldaAskDocument(1, 'Deck A')");
        const refused = run("submitZeldaAsk('first')");
        const failed = run("submitZeldaAsk('second')");
        run("setZeldaAskDocument(2, 'Deck B')");
        calls[0].answer({ status: 'error', message: 'STALE-REFUSAL' }); await refused;
        calls[1].fail('STALE-NETWORK-FAILURE'); await failed;
    },
    // The marketplace: {q} only, and its cards render.
    marketplace: async ({ run, calls }) => {
        const pending = run("submitZeldaAsk('seed founders')");
        calls[0].answer(MARKET); await pending;
    },
    // An older marketplace answer does not replace a newer one either.
    marketplace_newer_wins: async ({ run, calls }) => {
        const older = run("submitZeldaAsk('older search')");
        const newer = run("submitZeldaAsk('newer search')");
        calls[1].answer(MARKET); await newer;
        calls[0].answer({ status: 'success', response: 'Found 0.', results: [] }); await older;
    },
};

(async () => {
    const results = {};
    for (const [name, scenario] of Object.entries(SCENARIOS)) {
        const sandbox = makeSandbox();
        await scenario(sandbox);
        results[name] = sandbox.screen();
    }
    process.stdout.write(JSON.stringify(results));
})().catch(err => { console.error(err && err.stack || err); process.exit(1); });
