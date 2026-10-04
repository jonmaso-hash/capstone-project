"""
The structural boundary around document text (Phase 1 Task 4).

Raw document text lives in DocumentChunk. The locked contract (point 5) says
the AI layer may not read it directly: retrieval enters only through the
principal-scoped interface in zelda_api/retrieval.py. This module finds every
place first-party code reaches chunk content, so a test can hold that set to
an explicit, justified allowlist -- and any new direct read fails CI before
it merges.

What counts as reaching chunk content:
  - DocumentChunk.objects / ._default_manager / ._base_manager
  - the model name used any other way: aliased, passed as an argument,
    imported under another name, or named as a string (get_model)
  - the `chunks` / `source_chunks` relations, unless the chain only counts
    (.count() / .exists()) or projects positional metadata
    (.values_list('page_number') and the like -- no text)
  - a query lookup through a chunk relation ('chunks__…', 'source_chunks__…')
  - the table name in a string (raw SQL)

Counting and positional metadata are allowed anywhere: they carry no document text.
"""
import ast
import os
import re

MODEL = 'DocumentChunk'
MANAGERS = {'objects', '_default_manager', '_base_manager'}
RELATIONS = {'chunks', 'source_chunks'}
COUNT_ONLY = {'count', 'exists'}
PROJECTIONS = {'values_list', 'values'}
METADATA_FIELDS = {'id', 'pk', 'page_number', 'chunk_index', 'token_count'}
LOOKUP = re.compile(r'(^|__)(source_)?chunks__')
TABLE = 'zelda_api_documentchunk'

SKIP_DIRS = {'venv', '.venv', 'env', 'node_modules', 'staticfiles', 'static', 'media',
             'migrations', '__pycache__', '.git', 'frontend', 'docs', 'logs', 'tools'}


def is_test_file(path):
    name = os.path.basename(path)
    parts = path.replace('\\', '/').split('/')
    return name.startswith('tests') or name.startswith('test_') or 'tests' in parts[:-1]


SELF = os.path.abspath(__file__)


def first_party_files(root):
    """Every non-test, non-migration .py file in the project, except this scanner."""
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
        for name in sorted(files):
            path = os.path.join(directory, name)
            if (name.endswith('.py') and os.path.abspath(path) != SELF
                    and not is_test_file(os.path.relpath(path, root))):
                yield path


class _Finder(ast.NodeVisitor):
    def __init__(self):
        self.hits = []          # (qualname, lineno, what)
        self.scope = []
        self.parents = {}

    def _qualname(self):
        return '.'.join(self.scope) or '<module>'

    def _hit(self, node, what):
        self.hits.append((self._qualname(), node.lineno, what))

    def visit(self, node):
        for child in ast.iter_child_nodes(node):
            self.parents[child] = node
        return super().visit(node)

    def _scoped(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == MODEL and alias.asname not in (None, MODEL):
                self._hit(node, f'imported as {alias.asname}')
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == MODEL:
            if node.attr in MANAGERS:
                self._hit(node, f'{MODEL}.{node.attr}')
            # other attributes (DoesNotExist, _meta) carry no text
        elif node.attr in RELATIONS and not self._carries_no_text(node):
            self._hit(node, f'.{node.attr} relation')
        self.generic_visit(node)

    def visit_Name(self, node):
        parent = self.parents.get(node)
        if node.id == MODEL and not (isinstance(parent, ast.Attribute) and parent.value is node):
            self._hit(node, f'{MODEL} used directly')

    def visit_keyword(self, node):
        # filter(chunks__raw_text__icontains=...), Q(source_chunks__...=...)
        if node.arg and LOOKUP.search(node.arg):
            self._hit(node.value, f'lookup {node.arg}=')
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            text = node.value
            if text == MODEL or text.lower().endswith('.documentchunk') or text.lower() == 'documentchunk':
                self._hit(node, f'model named in string {text!r}')
            elif TABLE in text.lower():
                self._hit(node, 'chunk table in string')
            elif LOOKUP.search(text):
                self._hit(node, f'lookup {text!r}')

    def _carries_no_text(self, node):
        """
        `x.chunks[.filter(...)...].count()`, or a projection of metadata fields
        only (`.values_list('page_number', flat=True)`): the chain ends without
        ever yielding chunk text.
        """
        current = node
        while True:
            parent = self.parents.get(current)
            if isinstance(parent, ast.Attribute):
                current = parent
                call = self.parents.get(parent)
                is_call = isinstance(call, ast.Call) and call.func is parent
                if parent.attr in COUNT_ONLY:
                    return is_call
                if parent.attr in PROJECTIONS:
                    return is_call and self._metadata_only(call) and not isinstance(
                        self.parents.get(call), ast.Attribute)
                continue
            if isinstance(parent, ast.Call) and parent.func is current:
                current = parent
                continue
            return False


    @staticmethod
    def _metadata_only(call):
        fields = [a.value for a in call.args if isinstance(a, ast.Constant)]
        return (fields and len(fields) == len(call.args)
                and set(fields) <= METADATA_FIELDS
                and all(k.arg == 'flat' for k in call.keywords))


def find_chunk_access(source):
    """[(qualname, lineno, what)] for one module's source."""
    finder = _Finder()
    finder.visit(ast.parse(source))
    return finder.hits


def scan(root):
    """{(relative_path, qualname): [(lineno, what), ...]} across the project."""
    found = {}
    for path in first_party_files(root):
        with open(path, encoding='utf8') as handle:
            source = handle.read()
        rel = os.path.relpath(path, root).replace('\\', '/')
        for qualname, lineno, what in find_chunk_access(source):
            found.setdefault((rel, qualname), []).append((lineno, what))
    return found
