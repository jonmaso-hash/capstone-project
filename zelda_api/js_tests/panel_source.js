// Extracts named functions and constants from the assistant panel template
// (templates/includes/zelda_ai_assistant_enhanced.html), so the Node harnesses
// run the template's real code. Shared by assistant_panel_escaping.js and
// assistant_panel_ask.js.
'use strict';
const fs = require('fs');

function panelSource(path) {
    const source = fs.readFileSync(path, 'utf8').replace(/\r\n/g, '\n');

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

    return { source, extractFunction, extractConst };
}

module.exports = { panelSource };
