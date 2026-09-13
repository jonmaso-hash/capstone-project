"""
Email behind configuration.

The backend used to be hard-wired to Gmail SMTP, with DEFAULT_FROM_EMAIL equal to
the Gmail login, no ADMINS (so mail_admins reached nobody) and no SERVER_EMAIL (so
error mail came from root@localhost, which Postmark refuses). The contact form
sent to a hard-coded personal address.

Backend selection and the address settings are evaluated at import, so those
cases load settings in a subprocess with every email variable set explicitly --
empty values included, so a developer's local .env can't leak in. The contact
form and mail_admins are exercised in-process against Django's in-memory
backend; no mail is ever sent.
"""
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

ROOT = Path(settings.BASE_DIR)

EMAIL_VARS = (
    'POSTMARK_SERVER_TOKEN', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL',
    'SERVER_EMAIL', 'ADMINS', 'ADMIN_EMAIL', 'CONTACT_FORM_RECIPIENT',
)

_PROBE = (
    "import json; from django.conf import settings as s; "
    "print('SETTINGS_JSON=' + json.dumps({"
    "'backend': s.EMAIL_BACKEND, "
    "'anymail_token': getattr(s, 'ANYMAIL', {}).get('POSTMARK_SERVER_TOKEN'), "
    "'default_from': s.DEFAULT_FROM_EMAIL, "
    "'server_email': s.SERVER_EMAIL, "
    "'admins': s.ADMINS, "
    "'contact_recipient': s.CONTACT_FORM_RECIPIENT, "
    "}))"
)


def _email_settings(**values):
    env = dict(os.environ)
    env.update({
        'DJANGO_SETTINGS_MODULE': 'config.settings',
        'SECRET_KEY': 'test-only-email-settings-probe',
        'DEBUG': 'True',
        'ALLOWED_HOSTS': 'localhost',
        'STRIPE_SECRET_KEY': 'sk_test_placeholder',
    })
    env.update({name: '' for name in EMAIL_VARS})
    env.update(values)
    result = subprocess.run([sys.executable, '-c', _PROBE], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=120)
    line = next((l for l in result.stdout.splitlines() if l.startswith('SETTINGS_JSON=')), None)
    if line is None:
        raise AssertionError(f'settings failed to load:\n{result.stderr[-2000:]}')
    return json.loads(line[len('SETTINGS_JSON='):])


class EmailBackendSelectionTests(TestCase):

    def test_with_nothing_configured_mail_is_printed_not_sent(self):
        self.assertEqual(_email_settings()['backend'], 'django.core.mail.backends.console.EmailBackend')

    def test_smtp_credentials_select_smtp(self):
        loaded = _email_settings(EMAIL_HOST_USER='sender@example.test', EMAIL_HOST_PASSWORD='app-password')
        self.assertEqual(loaded['backend'], 'django.core.mail.backends.smtp.EmailBackend')

    def test_a_postmark_token_selects_postmark_through_anymail(self):
        loaded = _email_settings(POSTMARK_SERVER_TOKEN='postmark-token')
        self.assertEqual(loaded['backend'], 'anymail.backends.postmark.EmailBackend')
        self.assertEqual(loaded['anymail_token'], 'postmark-token')

    def test_postmark_wins_when_smtp_credentials_are_also_present(self):
        loaded = _email_settings(POSTMARK_SERVER_TOKEN='postmark-token',
                                 EMAIL_HOST_USER='sender@example.test', EMAIL_HOST_PASSWORD='app-password')
        self.assertEqual(loaded['backend'], 'anymail.backends.postmark.EmailBackend')


class EmailAddressSettingsTests(TestCase):

    def test_the_from_address_can_be_set_explicitly(self):
        loaded = _email_settings(DEFAULT_FROM_EMAIL='Interlink Foundry <hello@interlinkfoundry.com>',
                                 EMAIL_HOST_USER='sender@example.test')
        self.assertEqual(loaded['default_from'], 'Interlink Foundry <hello@interlinkfoundry.com>')

    def test_the_from_address_falls_back_to_the_smtp_login_then_a_site_address(self):
        self.assertEqual(_email_settings(EMAIL_HOST_USER='sender@example.test')['default_from'], 'sender@example.test')
        self.assertEqual(_email_settings()['default_from'], 'noreply@interlinkfoundry.com')

    def test_error_mail_is_not_sent_from_root_at_localhost(self):
        loaded = _email_settings(DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com')
        self.assertEqual(loaded['server_email'], 'hello@interlinkfoundry.com')
        self.assertEqual(
            _email_settings(DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com',
                            SERVER_EMAIL='alerts@interlinkfoundry.com')['server_email'],
            'alerts@interlinkfoundry.com')

    def test_admins_are_a_trimmed_list_of_addresses(self):
        self.assertEqual(_email_settings(ADMINS='ops@example.test, alerts@example.test')['admins'],
                         ['ops@example.test', 'alerts@example.test'])
        self.assertEqual(_email_settings()['admins'], [])

    def test_contact_form_recipient_precedence(self):
        base = {'DEFAULT_FROM_EMAIL': 'hello@interlinkfoundry.com'}
        self.assertEqual(_email_settings(**base)['contact_recipient'], 'hello@interlinkfoundry.com')
        self.assertEqual(_email_settings(ADMIN_EMAIL='admin@example.test', **base)['contact_recipient'],
                         'admin@example.test')
        self.assertEqual(
            _email_settings(ADMIN_EMAIL='admin@example.test', CONTACT_FORM_RECIPIENT='inbox@example.test',
                            **base)['contact_recipient'],
            'inbox@example.test')


@override_settings(ADMINS=['ops@example.test'], SERVER_EMAIL='alerts@interlinkfoundry.com')
class MailAdminsTests(TestCase):

    def test_mail_admins_reaches_the_configured_admins_without_a_deprecation_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            mail.mail_admins('Pitch reported', 'An elevator pitch was reported.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ops@example.test'])
        self.assertEqual(mail.outbox[0].from_email, 'alerts@interlinkfoundry.com')


@override_settings(DEFAULT_FROM_EMAIL='hello@interlinkfoundry.com', CONTACT_FORM_RECIPIENT='inbox@example.test')
class ContactFormEmailTests(TestCase):

    VALID = {
        'name': 'Ada Visitor', 'email': 'ada@visitor.test', 'company': 'Visitor Co',
        'phone': '', 'message': 'I would like to learn more.',
    }

    def test_a_valid_message_goes_to_the_configured_inbox_and_redirects(self):
        response = self.client.post(reverse('pages:contact'), self.VALID)

        self.assertRedirects(response, reverse('pages:contact'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['inbox@example.test'])
        self.assertEqual(sent.from_email, 'hello@interlinkfoundry.com')
        self.assertEqual(sent.reply_to, ['ada@visitor.test'])
        self.assertIn('Interlink Foundry', sent.subject)
        self.assertIn('I would like to learn more.', sent.body)

    def test_the_visitor_is_told_it_was_sent(self):
        response = self.client.post(reverse('pages:contact'), self.VALID, follow=True)
        self.assertContains(response, 'Message sent successfully!')
        self.assertNotContains(response, 'Error sending email')

    def test_an_invalid_message_sends_nothing(self):
        self.client.post(reverse('pages:contact'), {**self.VALID, 'email': 'not-an-email'})
        self.assertEqual(len(mail.outbox), 0)

    def test_a_send_failure_shows_a_generic_message_without_the_exception(self):
        with mock.patch('pages.views.EmailMessage.send', side_effect=RuntimeError('SMTP auth failed for secret-user')):
            response = self.client.post(reverse('pages:contact'), self.VALID)

        self.assertEqual(response.status_code, 200)
        # Read the message itself: the rendered page HTML-escapes the apostrophe.
        shown = [str(m) for m in response.context['messages']]
        self.assertEqual(shown, ["We couldn't send your message right now. Please try again in a few minutes."])
        self.assertNotContains(response, 'secret-user')
        self.assertEqual(len(mail.outbox), 0)
