# RA-107 review corrections at `77045b7`

**Separate, additive evidence** for two review findings on `7d8ce92` (`fix/memo-list-rendering`,
before merge). It does not edit `ra107-postfix-7d8ce92/` or any earlier record.

**Status: ungraded. Not deployed. Zelda hardening stays pending.**

## Findings, confirmed before the fix

They were reproduced against `7d8ce92` by calling `memo_list_items` / `memo_text` directly:

| # | Finding | Observed on `7d8ce92` |
|---|---|---|
| 1 | The size cap guarded only `ast.literal_eval`; `json.loads` caught only `ValueError` | `'[' * 20000 + ']' * 20000` (40,000 chars, below the cap) raised `RecursionError` out of the parser, which would 500 the memo page. A 60,004-char valid JSON list was parsed despite the cap |
| 2 | Multi-line items lost their boundaries | `memo_text(['First line [S1]\nsecond line [S2]', 'Other [S3]'])` wrote `'- First line [S1]\nsecond line [S2]\n- Other [S3]'`, which read back as **not a list** (`None`) |

## Corrections

1. **Size cap and parser errors.** `MAX_LITERAL_CHARS` is checked before **both** parsers. Any
   `ValueError`, `SyntaxError`, `TypeError`, `MemoryError` or `RecursionError` from either parser
   leaves the value shown exactly as stored.
2. **Multi-line items.**
   - **Writer:** an item's further lines are indented two spaces (Markdown list continuation).
   - **Reader:**
     - `- ` at column 0 starts an item;
     - indented lines continue it;
     - a blank line whose indentation was trimmed stays a blank line in the item;
     - any other unindented line means the value is prose.
   - **HTML:** each item renders with `linebreaksbr`, which escapes first.

## Results

- [logs/validation_output.txt](logs/validation_output.txt):
  - `check` clean; `makemigrations --check` reports no changes;
  - `tests_memo_list_rendering` 20 OK;
  - affected batch 510 OK (`tests_memo_list_rendering`, `tests_memo_persistence`,
    `tests_grounded_context`, `zelda_api.tests`, `pages.tests_ci_manifest`);
  - `matchmaking` 884 OK.
- [logs/mutations_output.txt](logs/mutations_output.txt), five mutations, all red:
  - the cap skipped;
  - resource errors not caught;
  - the writer without the continuation indent;
  - the reader dropping blank lines;
  - HTML without line breaks.

  The blank-line mutation first survived, because the writer never emits a bare blank line. A
  regression for trimmed trailing whitespace was added, and it is red now.
- [logs/saved_memo_readonly_check.txt](logs/saved_memo_readonly_check.txt), read-only:
  - memo 90 still parses to 7 items and memo 91 to 2/4/10;
  - no saved item contains a newline;
  - the prose fields still are not lists;
  - both rows hash identically to the pre-walk snapshot.

  The browser evidence in `ra107-postfix-7d8ce92/` therefore still describes what these memos
  render. No new browser walk was run.

Required CI remains the merge gate. The full blocking job was not run in one local process because
of RAM limits.
