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
      (parsed with json.loads / ast.literal_eval -- never eval)
    text whose every non-empty line is a "- " bullet (the form written below)

Anything else -- prose, prose with [S1] citations, a malformed or unsupported
value -- is not a list and is shown exactly as stored. Brackets are never
stripped: a citation is a bracket, and only a whole-value list is unwrapped.
"""
import ast
import json
import re

# ast.literal_eval is safe but not free; a memo section is a few KB.
MAX_LITERAL_CHARS = 50_000

_BULLET = re.compile(r'^\s*-\s+(\S.*?)\s*$')


def _string_items(value):
    if not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(item, str) for item in value):
        return None                      # unsupported: shown as stored, never dropped
    return [item.strip() for item in value if item.strip()]


def memo_list_items(value):
    """The section's items in order, or None when the value is not a list."""
    if isinstance(value, (list, tuple)):
        return _string_items(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith('[') and text.endswith(']'):
        try:
            return _string_items(json.loads(text))
        except ValueError:
            pass
        if len(text) <= MAX_LITERAL_CHARS:
            try:
                return _string_items(ast.literal_eval(text))
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                pass
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    matches = [_BULLET.match(line) for line in lines]
    if lines and all(matches):
        return [match.group(1) for match in matches]
    return None


def memo_text(value):
    """
    The section as plain text: a list becomes one "- item" line per item, so
    it reads as bullets in Markdown, the admin, the memo API and anything else
    that prints the field. Every other value is returned unchanged; a value
    that is neither text nor a list of strings is serialised whole as JSON
    rather than repr'd or dropped.
    """
    items = memo_list_items(value)
    if items is not None:
        return '\n'.join(f'- {item}' for item in items)
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)
