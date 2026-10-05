from django import template
from billing.zelda_catalog import catalog, REPORTS

register = template.Library()


@register.simple_tag
def zelda_products():
    return catalog()


@register.simple_tag
def zelda_individual_reports():
    return [{'key': key, 'name': value[0]} for key, value in REPORTS.items()]
