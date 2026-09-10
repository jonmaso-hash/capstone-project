"""
Presentation of deal figures that can legitimately be absent.

`SellerApplication.asking_price` is a non-null DecimalField defaulting to 0, so
"has not priced the business yet" and "is asking zero" are the same stored
value. The matching engine already draws that distinction correctly --
`deal_size_signal` treats 0 as unstated and abstains rather than scoring the
seller against a number they never gave.

The templates did not. Four of them rendered `Asking: $0`, turning an absence
into a stated price of zero on the buyer's screen: exactly the "absence never
becomes a value" rule the match contract exists to enforce, broken on the one
surface a user actually reads.

This filter is the single place that distinction is made for display, so the
next template to show an asking price inherits it instead of re-deciding.
"""
from django import template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()

# What the user sees where no price has been given. Deliberately words the
# absence rather than substituting a number, a dash, or a zero.
UNSTATED_LABEL = 'Not stated'


@register.filter(name='asking_price_display')
def asking_price_display(value):
    """
    `$4,200,000` when a price was given, `Not stated` when it was not.

    0 and None both mean "not stated" -- the field cannot distinguish them, and
    a business genuinely priced at zero is not a case this marketplace serves.
    """
    if not value:
        return UNSTATED_LABEL
    try:
        return '$%s' % intcomma(int(round(float(value))))
    except (TypeError, ValueError):
        return UNSTATED_LABEL
