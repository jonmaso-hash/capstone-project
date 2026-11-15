"""Consolidated income-statement figures read from a filing's own page text.

Pure parsing: no model call, no network, no company-specific values. A figure
qualifies only when its page carries a consolidated statement of operations
(or income/earnings) title, states the scale ("In millions") and currency,
and labels every column with an annual period-end date. Anything less is left
out rather than guessed: a prose sentence that names the statement, a
quarterly table, a deferred-revenue balance or a row whose column count does
not match the header never becomes revenue.

Each figure keeps its line item, entity and consolidated scope, period,
currency, scale and source page, so a report can show where it came from.
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .utils import split_pages

STATEMENT_TITLES = {
    'CONSOLIDATEDSTATEMENTSOFOPERATIONS': 'Consolidated Statements of Operations',
    'CONSOLIDATEDSTATEMENTSOFINCOME': 'Consolidated Statements of Income',
    'CONSOLIDATEDSTATEMENTSOFEARNINGS': 'Consolidated Statements of Earnings',
}

SCALE_FACTORS = {'thousands': Decimal(10) ** 3, 'millions': Decimal(10) ** 6, 'billions': Decimal(10) ** 9}

# Row labels, compared after lower-casing and collapsing spaces. Exact labels
# only: "net sales by reportable segment" or "deferred revenue" never match.
ROW_LABELS = {
    'net_sales': ('total net sales', 'net sales', 'total net revenues', 'net revenues', 'net revenue',
                  'total revenues', 'total revenue', 'revenues', 'revenue'),
    'gross_margin': ('total gross margin', 'gross margin', 'gross profit'),
    'net_income': ('net income', 'net income (loss)', 'net (loss) income', 'net earnings', 'net loss'),
}
METRIC_NAMES = {'net_sales': 'Total net sales', 'gross_margin': 'Gross margin', 'net_income': 'Net income'}

_DEFERRED_REVENUE = re.compile(r'\b(?:deferred|unearned)\s+revenues?\b|\bcontract\s+liabilit', re.IGNORECASE)
_MONTHS = ('january february march april may june july august september october november december').split()
# No \b before the month: PDF text runs columns together ("2026September 27,").
_PERIOD_END = re.compile(r'(?<![A-Za-z])(' + '|'.join(_MONTHS) + r')\s+(\d{1,2}),\s*(\d{4})', re.IGNORECASE)
_ANNUAL_HEADER = re.compile(r'\b(?:fiscal\s+)?years?\s+ended\b|\btwelve\s+months\s+ended\b', re.IGNORECASE)
_INTERIM_HEADER = re.compile(r'\b(?:three|six|nine)\s+months\s+ended\b|\bquarters?\s+ended\b', re.IGNORECASE)
_SCALE = re.compile(r'\(\s*in\s+(thousands|millions|billions)\b', re.IGNORECASE)
_FOREIGN_CURRENCY = re.compile(r'[€£¥]|\b(?:euros?|pounds\s+sterling|yen|renminbi|RMB|canadian\s+dollars|'
                               r'australian\s+dollars|swiss\s+francs)\b', re.IGNORECASE)
_GROUPED_NUMBER = re.compile(r'^\(?\d{1,3}(?:,\d{3})*\)?$')
_HAS_GROUPED_NUMBER = re.compile(r'\d{1,3},\d{3}')
_DASHES = {'—', '–', '-'}


def names_deferred_revenue(text):
    """True when the text is about deferred/unearned revenue, which is never net sales."""
    return bool(_DEFERRED_REVENUE.search(text or ''))


def _letters(line):
    return re.sub(r'[^A-Z]', '', line.upper())


def _label(line):
    """The row label: text before the first value, lower-cased, spaces collapsed."""
    match = re.search(r'\$|\(?\d', line)
    label = line[:match.start()] if match else line
    return re.sub(r'\s+', ' ', label).strip().rstrip(':').strip().lower(), (line[match.start():] if match else '')


def _values(rest, columns):
    """Exactly `columns` numbers from a row, rejoining digit groups a PDF split ("194,1 16")."""
    tokens = rest.replace('$', ' ').split()
    values, i = [], 0
    while i < len(tokens):
        token = tokens[i]
        if token in _DASHES:
            values.append(Decimal(0))
            i += 1
            continue
        if _GROUPED_NUMBER.match(token):
            joined, i = token, i + 1
        elif i + 1 < len(tokens) and _GROUPED_NUMBER.match(token + tokens[i + 1]):
            joined, i = token + tokens[i + 1], i + 2
        else:
            return None
        negative = joined.startswith('(')
        number = Decimal(joined.strip('()').replace(',', ''))
        values.append(-number if negative else number)
    return values if len(values) == columns else None


def _money(value):
    """$478.834 billion, keeping every reported digit."""
    for unit, factor in (('trillion', Decimal(10) ** 12), ('billion', Decimal(10) ** 9),
                         ('million', Decimal(10) ** 6), ('thousand', Decimal(10) ** 3)):
        if abs(value) >= factor:
            text = format((value / factor).normalize(), 'f')
            return f'{"-" if value < 0 else ""}${text.lstrip("-")} {unit}'
    return f'${value:,}'


def _percent(value, places):
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StatementFigure:
    metric: str
    line_item: str
    entity: str
    scope: str
    statement: str
    period_end: date
    period_type: str
    currency: str
    scale: str
    reported: Decimal
    source_page: int

    @property
    def fiscal_year(self):
        return self.period_end.year

    @property
    def value(self):
        return self.reported * SCALE_FACTORS[self.scale]

    @property
    def period_label(self):
        return f'FY{self.fiscal_year} (fiscal year ended {self.period_end:%B} {self.period_end.day}, {self.period_end.year})'

    def amount(self):
        return _money(self.value)

    def reported_text(self):
        return f'${self.reported:,} {self.scale[:-1]}'


@dataclass(frozen=True)
class DerivedRatio:
    name: str
    value: Decimal
    formula: str
    source_page: int


@dataclass(frozen=True)
class IncomeStatement:
    entity: str
    statement: str
    currency: str
    scale: str
    source_page: int
    period_ends: tuple
    figures: dict  # metric -> tuple of StatementFigure, one per column, in column order

    def latest(self, metric):
        column = self.period_ends.index(max(self.period_ends))
        return self.figures[metric][column] if metric in self.figures else None

    def prior(self, metric):
        ordered = sorted(self.period_ends, reverse=True)
        if len(ordered) < 2 or metric not in self.figures:
            return None
        return self.figures[metric][self.period_ends.index(ordered[1])]

    def net_sales_growth(self):
        current, prior = self.latest('net_sales'), self.prior('net_sales')
        if not current or not prior or prior.reported <= 0:
            return None
        return DerivedRatio(
            f'Total net sales growth, FY{current.fiscal_year} vs FY{prior.fiscal_year}',
            (current.reported - prior.reported) / prior.reported * 100,
            f'({current.reported_text()} - {prior.reported_text()}) / {prior.reported_text()}',
            self.source_page)

    def gross_margin_percentage(self):
        sales, margin = self.latest('net_sales'), self.latest('gross_margin')
        if not sales or not margin or sales.reported <= 0:
            return None
        return DerivedRatio(
            f'Gross margin percentage, FY{sales.fiscal_year}',
            margin.reported / sales.reported * 100,
            f'{margin.line_item} {margin.reported_text()} / {sales.line_item} {sales.reported_text()}',
            self.source_page)

    def net_margins(self):
        """Net income / net sales for each period the statement reports both, latest first.

        Both figures come from the same column, so the ratio never mixes periods.
        """
        if 'net_sales' not in self.figures or 'net_income' not in self.figures:
            return []
        ratios = []
        for sales, income in zip(self.figures['net_sales'], self.figures['net_income']):
            if sales.period_end != income.period_end or sales.reported <= 0:
                continue
            ratios.append((sales.period_end, DerivedRatio(
                f'Net margin, FY{sales.fiscal_year}',
                income.reported / sales.reported * 100,
                f'{income.line_item} {income.reported_text()} / {sales.line_item} {sales.reported_text()}, '
                f'both for the fiscal year ended {sales.period_end:%B} {sales.period_end.day}, {sales.period_end.year}',
                self.source_page)))
        return [ratio for _, ratio in sorted(ratios, key=lambda pair: pair[0], reverse=True)]

    def summary_lines(self):
        """Report bullets; each carries its line item, period, currency, scale and page."""
        lines = []

        def figure(f):
            return (f'• {f.line_item}, {f.period_label}: {f.amount()} '
                    f'({f.currency}; reported as {f.reported_text()}; PDF page {f.source_page})')

        for f in (self.latest('net_sales'), self.prior('net_sales')):
            if f:
                lines.append(figure(f))
        growth = self.net_sales_growth()
        if growth:
            lines.append(f'• {growth.name}: {_percent(growth.value, 0)}% ({_percent(growth.value, 2)}% before rounding; '
                         f'computed as {growth.formula}; PDF page {growth.source_page})')
        margin = self.latest('gross_margin')
        if margin:
            lines.append(figure(margin))
        percentage = self.gross_margin_percentage()
        if percentage:
            lines.append(f'• {percentage.name}: {_percent(percentage.value, 1)}% '
                         f'(computed as {percentage.formula}; PDF page {percentage.source_page})')
        income = self.latest('net_income')
        if income:
            lines.append(figure(income))
            latest = next((ratio for ratio in self.net_margins()
                           if ratio.name.endswith(f'FY{income.fiscal_year}')), None)
            if latest:
                lines.append(f'• {latest.name}: {_percent(latest.value, 1)}% '
                             f'(computed as {latest.formula}; PDF page {latest.source_page})')
        return lines

    def heading(self):
        return (f'Verified from the {self.statement} of {self.entity} (consolidated; {self.currency}; '
                f'amounts reported in {self.scale}; PDF page {self.source_page}):')


def _statement_on_page(number, text):
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        statement = STATEMENT_TITLES.get(_letters(line))
        if not statement:
            continue
        body = lines[index + 1:]
        first_row = next((i for i, row in enumerate(body) if _HAS_GROUPED_NUMBER.search(row)), None)
        if first_row is None:
            continue
        header = ' '.join(body[:first_row])
        scale = _SCALE.search(header)
        period_ends = []
        for month, day, year in _PERIOD_END.findall(header):
            period_ends.append(date(int(year), _MONTHS.index(month.lower()) + 1, int(day)))
        # Fail closed: no scale, no annual period header, an interim header,
        # or a currency other than dollars means no figure from this table.
        if (not scale or not period_ends or len(set(period_ends)) != len(period_ends)
                or not _ANNUAL_HEADER.search(header) or _INTERIM_HEADER.search(header)
                or _FOREIGN_CURRENCY.search(header)):
            continue
        rows = body[first_row:]
        if not any('$' in row for row in rows):
            continue
        entity = next((prior for prior in reversed(lines[:index]) if prior), '')
        entity = entity if 0 < len(entity) <= 80 and not _HAS_GROUPED_NUMBER.search(entity) else 'the filer'
        figures = {}
        for row in rows:
            label, rest = _label(row)
            if not rest or names_deferred_revenue(label):
                continue
            for metric, labels in ROW_LABELS.items():
                if label not in labels:
                    continue
                values = _values(rest, len(period_ends))
                if values is None:
                    continue
                current = figures.get(metric)
                # The table's own total wins over a plain row of the same metric.
                if current and not (label.startswith('total') and not current[0].line_item.lower().startswith('total')):
                    continue
                line_item = re.sub(r'\s+', ' ', row[:len(row) - len(rest)]).strip().rstrip(':')
                figures[metric] = tuple(
                    StatementFigure(metric, line_item, entity, 'consolidated', statement, end, 'annual',
                                    'USD', scale.group(1).lower(), value, number)
                    for end, value in zip(period_ends, values))
        if 'net_sales' in figures:
            return IncomeStatement(entity, statement, 'USD', scale.group(1).lower(), number,
                                   tuple(period_ends), figures)
    return None


def read_income_statement(raw_text):
    """The first page holding a qualifying consolidated income statement, else None."""
    for number, text in split_pages(raw_text or ''):
        statement = _statement_on_page(number, text)
        if statement:
            return statement
    return None
