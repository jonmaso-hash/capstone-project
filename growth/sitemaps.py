from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

from matchmaking.models import Application, InvestorApplication
from .models import PlatformInsightReport
from .views import _public_queryset


def _distinct_combos(model, fields):
    """
    Distinct (field1, field2, field3) value tuples actually present among
    public profiles — each becomes one pSEO sitemap entry. Values are used
    as-is (not split on commas) even though fields like investment_focus
    can hold a comma-separated list — the page view itself matches via
    icontains, so a URL built from the raw value still resolves correctly;
    this just keeps sitemap generation simple rather than computing a full
    cross-product of every individual industry token.
    """
    combos = _public_queryset(model).exclude(**{f'{f}__isnull': True for f in fields}) \
        .values_list(*fields).distinct()
    seen_slugs = set()
    result = []
    for combo in combos:
        if not all((v or '').strip() for v in combo):
            continue
        slugs = tuple(slugify(v) for v in combo)
        if not all(slugs) or slugs in seen_slugs:
            continue
        seen_slugs.add(slugs)
        result.append(slugs)
    return result


class InvestorDirectorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return _distinct_combos(InvestorApplication, ['investment_focus', 'investment_stage', 'location'])

    def location(self, item):
        sector_slug, stage_slug, location_slug = item
        return reverse('growth:investor_directory', args=[sector_slug, stage_slug, location_slug])


class FounderDirectorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return _distinct_combos(Application, ['sector', 'stage', 'geography'])

    def location(self, item):
        sector_slug, stage_slug, location_slug = item
        return reverse('growth:founder_directory', args=[sector_slug, stage_slug, location_slug])


class InsightReportSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return PlatformInsightReport.objects.filter(is_published=True)

    def location(self, obj):
        return reverse('growth:insights_detail', args=[obj.period_slug])

    def lastmod(self, obj):
        return obj.generated_at
