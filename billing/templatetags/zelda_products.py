from django import template
from billing.zelda_catalog import catalog, role_catalog, REPORTS

register = template.Library()


@register.simple_tag
def zelda_products():
    return catalog()


@register.simple_tag
def zelda_individual_reports():
    return [{'key': key, 'name': value[0]} for key, value in REPORTS.items()]


@register.simple_tag
def valuation_range_disclosure():
    from zelda_api.disclaimers import VALUATION_RANGE_DISCLOSURE
    return VALUATION_RANGE_DISCLOSURE


@register.simple_tag(takes_context=True)
def zelda_role_products(context):
    return role_catalog(context.get('user'))


@register.simple_tag(takes_context=True)
def truth_delta_credit_balance(context):
    user = context.get('user')
    if not user or not getattr(user, 'is_authenticated', False):
        return 0
    from billing.models import TruthDeltaCreditWallet
    return TruthDeltaCreditWallet.objects.filter(user=user).values_list('balance', flat=True).first() or 0
