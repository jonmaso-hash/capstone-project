"""
Django's `{# #}` comment is single-line only.

Spanning one across lines does not comment anything out — the template engine
stops treating it as a comment and renders the text, so implementation notes
appear on the page. Five of these were live in production templates, including
`_role_cards.html`, whose note rendered as a paragraph directly under
"I AM JOINING AS A…" on the signup page, and `thank_you.html`, whose note showed
under the celebration.

This is a recurring mistake in this codebase rather than a one-off, and it is
invisible to every other kind of test: the templates render fine, the views
return 200, and nothing raises. Only a reader notices. So the rule is checked
directly.

`{% comment %}…{% endcomment %}` is the multi-line form.
"""
import glob
import io
import os

from django.test import SimpleTestCase

NEWLINE = chr(10)


def multiline_hash_comments(root='templates'):
    """Every `{# … #}` that spans lines, as (path, line number, text)."""
    found = []
    for path in sorted(glob.glob(os.path.join(root, '**', '*.html'), recursive=True)):
        source = io.open(path, encoding='utf-8').read()
        cursor = 0
        while True:
            start = source.find('{#', cursor)
            if start == -1:
                break
            end = source.find('#}', start)
            if end == -1:
                break
            body = source[start + 2:end]
            if NEWLINE in body:
                found.append((
                    path.replace(os.sep, '/'),
                    source[:start].count(NEWLINE) + 1,
                    ' '.join(body.split())[:60],
                ))
            cursor = end + 2
    return found


class TemplateCommentSyntaxTests(SimpleTestCase):

    def test_no_template_comment_spans_lines(self):
        leaks = multiline_hash_comments()
        self.assertEqual(
            leaks, [],
            'These `{# #}` comments span lines, so Django renders them as visible '
            'page text. Use `{% comment %}`/`{% endcomment %}` instead:'
            + NEWLINE
            + NEWLINE.join('  %s:%d  %s...' % leak for leak in leaks))

    def test_the_detector_actually_detects(self):
        """A guard whose own logic is broken guards nothing."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            single = os.path.join(tmp, 'ok.html')
            io.open(single, 'w', encoding='utf-8').write('{# fine, one line #}' + NEWLINE)
            spanning = os.path.join(tmp, 'bad.html')
            io.open(spanning, 'w', encoding='utf-8').write(
                '{# this one' + NEWLINE + '   spans lines #}' + NEWLINE)

            found = multiline_hash_comments(tmp)
            self.assertEqual(len(found), 1, 'expected exactly the spanning comment')
            self.assertTrue(found[0][0].endswith('bad.html'))
