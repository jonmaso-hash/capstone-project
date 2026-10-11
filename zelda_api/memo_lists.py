"""
List-valued memo sections, read and written one way (RA-002, RA-107 / BW-004).

The memo model may answer a section such as questions_for_management with a
list. IntelligenceMemo stores every section in a TextField, and a TextField
saves a Python list as its repr, so ManyChat's memo holds
"['The company states …', '…']". Ben & Jerry's memo holds the model's own
JSON text, '["What are …", "…"]'. Both reached the IC memo page, its Markdown
export and the memo API as raw list syntax.

Three things are recognised as a list, and nothing else:

    a native list or tuple of strings
    a JSON list of strings, or a Python list literal of strings
      (parsed with json.loads / ast.literal_eval -- never eval -- and only
      when no longer than MAX_LITERAL_CHARS)
    "- " bullet text as written below: each item starts at column 0 with
      "- ", and an item's further lines are indented two spaces

Anything else -- prose, prose with [S1] citations, a malformed, oversized or
unsupported value -- is not a list and is shown exactly as stored. Brackets
are never stripped: a citation is a bracket, and only a whole-value list is
unwrapped.
"""
import ast
import json
import re

# Parsing is safe but not free: a memo section is a few KB, so a longer value
# is never handed to either parser and is shown as stored.
MAX_LITERAL_CHARS = 50_000
# What a parser may raise on hostile or pathological input (deep nesting).
_PARSE_ERRORS = (ValueError, SyntaxError, TypeError, MemoryError, RecursionError)

# An item starts at column 0 with "- "; its further lines are indented two
# spaces (Markdown list continuation), so an item may contain newlines.
_BULLET = re.compile(r'^-\s+(\S.*?)\s*$')
_CONTINUATION = '  '


def _string_items(value):
    if not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(item, str) for item in value):
        return None                      # unsupported: shown as stored, never dropped
    return [item.strip() for item in value if item.strip()]


def _parsed_items(text):
    if len(text) > MAX_LITERAL_CHARS:
        return None
    for parse in (json.loads, ast.literal_eval):
        try:
            return _string_items(parse(text))
        except _PARSE_ERRORS:
            continue
    return None


def _bullet_items(text):
    items = []
    for line in text.splitlines():
        match = _BULLET.match(line)
        if match:
            items.append([match.group(1)])
        elif items and line.startswith(_CONTINUATION):
            items[-1].append(line[len(_CONTINUATION):])
        elif items and not line.strip():
            items[-1].append('')
        elif line.strip():
            return None                  # an unindented non-bullet line: prose
    return ['\n'.join(parts).strip() for parts in items] or None


def memo_list_items(value):
    """The section's items in order, or None when the value is not a list."""
    if isinstance(value, (list, tuple)):
        return _string_items(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith('[') and text.endswith(']'):
        return _parsed_items(text)
    return _bullet_items(text)


def memo_text(value):
    """
    The section as plain text: a list becomes one "- item" line per item, with
    an item's further lines indented two spaces, so it reads as bullets in
    Markdown, the admin, the memo API and anything else that prints the field,
    and reads back as the same items. Every other value is returned unchanged;
    a value that is neither text nor a list of strings is serialised whole as
    JSON rather than repr'd or dropped.
    """
    items = memo_list_items(value)
    if items is not None:
        return '\n'.join('- ' + item.replace('\n', '\n' + _CONTINUATION) for item in items)
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)
