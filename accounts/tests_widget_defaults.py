"""
A form must never render a value its own widget rejects.

The investor mandate form did exactly that. The model defaults for the three
matching-weight fields are 0.334/0.333/0.333 -- equal thirds, meaning "no
stated preference" -- while the widgets declared `step="0.05"`. No three
multiples of 0.05 are both equal and sum to 1.00, so the grid could not express
the default at all. Every new investor got a form pre-filled with values the
browser refused to submit.

It failed silently. The three inputs live inside the collapsed "Advanced
matching preferences (optional)" section, and a browser cannot show a
validation bubble on a control it cannot focus, so Chrome logged

    An invalid form control with name='weight_problem_solution' is not focusable.

and did nothing visible. The investor filled in every field they could see,
clicked "Save & See My Matches", and the page just sat there.

Nothing caught it because `step` is enforced only by the browser. Django's test
client posts a dict straight to the view, so a POST of those same defaults
succeeded in tests before the fix and succeeds after it -- asserting that alone
proves nothing. These tests instead check what the browser checks: that the
values a page actually renders satisfy the constraints that page actually
declares.
"""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.forms import ApplicationForm, BuyerForm, InvestorForm, SellerForm
from matchmaking.tests import _mock_embedding_generation

User = get_user_model()

PASSWORD = 'Str0ng-Passw0rd-9x'


def html5_step_error(value, step, minimum):
    """
    Reproduce the browser's step-mismatch rule.

    Returns None if a browser would accept `value`, else a description. A step
    of "any" (or absent) accepts anything; otherwise the value must sit exactly
    on the grid anchored at `min` (default 0), which is what
    ValidityState.stepMismatch tests.
    """
    if value in (None, ''):
        return None
    if step in (None, '', 'any'):
        return None
    try:
        value = Decimal(str(value))
        step = Decimal(str(step))
        base = Decimal(str(minimum)) if minimum not in (None, '') else Decimal('0')
    except (InvalidOperation, ValueError):
        return None
    if step <= 0:
        return None
    offset = (value - base) % step
    if offset == 0:
        return None
    lower = value - offset
    return ('%s is not on the step="%s" grid; the nearest valid values are %s and %s'
            % (value, step, lower, lower + step))


class InputCollector(HTMLParser):
    """
    Every <input> in a rendered page, with its attributes.

    Page-wide rather than form-scoped, so callers must select by name: the
    layout also renders a global search sidebar whose fields include `location`,
    `industry` and `stage`, which collide with investor-mandate field names.
    Number inputs are exposed separately for the constraint assertions -- the
    sidebar's own number inputs render empty and are skipped by
    html5_step_error, so they cannot mask a real failure.
    """

    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            self.inputs.append(dict(attrs))

    @property
    def number_inputs(self):
        return [a for a in self.inputs if a.get('type') == 'number']

    def first(self, name):
        """First rendered value for `name` -- the mandate form precedes the sidebar."""
        for attrs in self.inputs:
            if attrs.get('name') == name:
                return attrs.get('value')
        return None


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WidgetDefaultConsistencyTests(TestCase):
    """
    The invariant, across every role form: a rendered default must satisfy the
    widget rendering it. Cheap to keep, and it fails the moment someone tightens
    a step without checking what the field is initialised to.
    """

    ROLE_FORMS = {
        'founder': ApplicationForm,
        'investor': InvestorForm,
        'seller': SellerForm,
        'buyer': BuyerForm,
    }

    def test_no_role_form_renders_a_default_its_own_widget_rejects(self):
        for role, form_class in self.ROLE_FORMS.items():
            form = form_class()
            for name, field in form.fields.items():
                attrs = field.widget.attrs
                value = form.get_initial_for_field(field, name)
                if value is None:
                    continue
                error = html5_step_error(value, attrs.get('step'), attrs.get('min'))
                with self.subTest(role=role, field=name):
                    self.assertIsNone(
                        error,
                        '%s form field %r renders %r, which its own widget rejects: %s. '
                        'A browser will refuse to submit the form and, if the field is '
                        'inside a collapsed section, will not say why.'
                        % (role, name, value, error))

    def test_the_weight_fields_keep_their_equal_thirds_defaults(self):
        """
        The fix relaxed the constraint rather than moving the defaults. If a
        later change snaps these to a coarser grid, that is a product statement
        -- "market context matters less" -- and should not happen by accident.
        """
        form = InvestorForm()
        self.assertEqual(
            [form.get_initial_for_field(form.fields[n], n) for n in (
                'weight_problem_solution', 'weight_capital_plan', 'weight_market_context')],
            [0.334, 0.333, 0.333])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvestorOnboardingUntouchedDefaultsTests(TestCase):
    """
    The production failure itself, through the real page a new investor sees.

    Parses the rendered HTML rather than inspecting the form object, so a
    template that adds or overrides widget attrs is covered too -- the browser
    only ever sees the HTML.
    """

    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('wd_investor', password=PASSWORD)
        self.client.force_login(self.user)

    def _rendered_page(self):
        response = self.client.get('/settings/profile/investor/')
        self.assertEqual(response.status_code, 200)
        collector = InputCollector()
        collector.feed(response.content.decode(errors='ignore'))
        return collector

    def _rendered_number_inputs(self):
        return self._rendered_page().number_inputs

    def test_a_browser_would_accept_every_untouched_default_on_the_page(self):
        inputs = self._rendered_number_inputs()
        self.assertTrue(inputs, 'expected the mandate form to render number inputs')

        for attrs in inputs:
            name = attrs.get('name', '<unnamed>')
            error = html5_step_error(attrs.get('value'), attrs.get('step'), attrs.get('min'))
            with self.subTest(field=name):
                self.assertIsNone(
                    error,
                    'the investor mandate page renders %s=%r, which the browser rejects: %s. '
                    'Save & See My Matches will do nothing, with no visible error.'
                    % (name, attrs.get('value'), error))

    def test_the_weight_inputs_are_rendered_and_prefilled(self):
        """Guards the test above from passing vacuously if the section disappears."""
        rendered = {a.get('name'): a for a in self._rendered_number_inputs()}
        for name in ('weight_problem_solution', 'weight_capital_plan', 'weight_market_context'):
            with self.subTest(field=name):
                self.assertIn(name, rendered)
                self.assertTrue(rendered[name].get('value'))

    def test_submitting_the_untouched_rendered_defaults_succeeds(self):
        """
        End to end: take the values the page actually rendered, add only the
        fields a new investor can see and must fill, and submit.

        On its own this would prove little -- Django never enforced step, so it
        passed before the fix too. It earns its place next to the assertions
        above: together they say the page a browser is handed can be submitted
        by that browser, and that the server accepts the result.
        """
        page = self._rendered_page()
        # Only what a new investor actually types.
        payload = {
            'full_name': 'Untouched Defaults',
            'company_name': 'Defaults Capital',
            'email': 'untouched@t.com',
            'investment_focus': 'Climate Tech',
            'investment_stage': 'Seed',
        }
        # Everything else comes from the page as rendered, untouched.
        # investment_amount belongs here too: it is required and ships
        # pre-filled, so leaving it out would test a submission no real
        # investor makes.
        for name in ('weight_problem_solution', 'weight_capital_plan',
                     'weight_market_context', 'investment_amount'):
            value = page.first(name)
            self.assertIsNotNone(value, '%s was expected to render pre-filled' % name)
            payload[name] = value

        response = self.client.post('/settings/profile/investor/', payload)
        self.assertEqual(
            response.status_code, 302,
            'a first submission with untouched defaults must be accepted; got a '
            're-rendered form instead')
        self.assertIn('/thank-you/', response.url)

        self.user.refresh_from_db()
        profile = self.user.match_investor_profile
        self.assertAlmostEqual(profile.weight_problem_solution, 0.334)
        self.assertAlmostEqual(profile.weight_capital_plan, 0.333)
        self.assertAlmostEqual(profile.weight_market_context, 0.333)
