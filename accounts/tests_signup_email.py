"""
Password signups give an email address, and no two accounts share one.

Signup used Django's stock UserCreationForm: a username and two passwords, no
email. Every password account therefore had an empty email, so "Forgot your
password?" could never reach one, and neither could the account-deletion
confirmation or any other transactional email.

Now:

- the signup form requires an email, trims it and lower-cases its domain
  (Django's normalize_email), and refuses one already used by any account,
  whatever its case
- below the form, the database refuses a second account with the same email
  (a partial unique index on LOWER(email), skipping blank emails), so the
  admin, social signups and code can't create one either
- accounts with no email -- staff tools, older records, test users -- are
  still allowed; only a non-blank email must be unique

No confirmation email yet: that waits for transactional email (Postmark) to
be live.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import RateLimitEvent

User = get_user_model()

PASSWORD = 'SignupEmail!2026xyz'
FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']
INDEX_NAME = 'accounts_auth_user_email_ci_uniq'


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class SignupFormTests(TestCase):

    def _signup(self, username='se_user', email='new.founder@example.com', role='founder'):
        data = {'username': username, 'password1': PASSWORD, 'password2': PASSWORD, 'role': role}
        if email is not None:
            data['email'] = email
        return self.client.post(reverse('accounts:signup'), data)

    def test_the_signup_page_asks_for_an_email(self):
        html = self.client.get(reverse('accounts:signup')).content.decode()
        self.assertIn('name="email"', html)

    def test_an_email_is_required(self):
        for email in (None, '', '   '):
            with self.subTest(email=email):
                response = self._signup(email=email)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors.get('email'))
                self.assertFalse(User.objects.filter(username='se_user').exists())

    def test_a_refused_signup_does_not_use_up_the_signup_limit(self):
        self._signup(email='')
        self.assertFalse(RateLimitEvent.objects.filter(scope='signup_ip').exists())

    def test_the_account_keeps_its_email(self):
        response = self._signup(email='  New.Founder@EXAMPLE.com ')
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='se_user')
        # Trimmed, with the domain lower-cased as Django normalises it.
        self.assertEqual(user.email, 'New.Founder@example.com')

    def test_an_email_already_in_use_is_refused_whatever_its_case(self):
        User.objects.create_user('se_existing', email='Taken@Example.com', password=PASSWORD)
        for email in ('taken@example.com', 'TAKEN@EXAMPLE.COM', ' Taken@Example.com '):
            with self.subTest(email=email):
                response = self._signup(email=email)
                self.assertEqual(response.status_code, 200)
                self.assertIn('already', ' '.join(response.context['form'].errors['email']).lower())
                self.assertFalse(User.objects.filter(username='se_user').exists())

    def test_an_invalid_email_is_refused(self):
        response = self._signup(email='not-an-email')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='se_user').exists())

    def test_a_password_signup_user_can_reset_their_password(self):
        self._signup(email='reset.me@example.com')
        self.client.logout()
        mail.outbox.clear()
        response = self.client.post(reverse('password_reset'), {'email': 'reset.me@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['reset.me@example.com'])


class DatabaseGuardTests(TestCase):
    """The rule holds below the form: admin, social signup and code alike."""

    def test_two_accounts_cannot_share_an_email_whatever_its_case(self):
        User.objects.create_user('dg_one', email='same@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('dg_two', email='SAME@example.com')

    def test_an_account_cannot_be_changed_to_an_email_in_use(self):
        User.objects.create_user('dg_one', email='first@example.com')
        second = User.objects.create_user('dg_two', email='second@example.com')
        second.email = 'First@Example.com'
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()

    def test_accounts_without_an_email_are_still_allowed(self):
        User.objects.create_user('dg_blank_one')
        User.objects.create_user('dg_blank_two')
        User.objects.create_user('dg_blank_three', email='')
        self.assertEqual(User.objects.filter(email='').count(), 3)

    def test_the_unique_index_is_on_the_user_table(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, User._meta.db_table)
        self.assertIn(INDEX_NAME, constraints)
        self.assertTrue(constraints[INDEX_NAME]['unique'])
