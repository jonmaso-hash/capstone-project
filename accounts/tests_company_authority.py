from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matchmaking.models import (
    Application,
    BusinessEmailVerification,
    CompanyRepresentationAttestation,
    business_email_verified,
    current_company_representation,
)
from matchmaking.tests import _mock_embedding_generation
from matchmaking.utils import compute_founder_journey_stage

User = get_user_model()


class CompanyAuthoritySemanticsTests(TestCase):
    def setUp(self):
        _mock_embedding_generation(self)
        self.user = User.objects.create_user('authority_founder', password='x')
        self.application = Application.objects.create(
            user=self.user,
            company_name='Authority Labs',
            founder_name='A Founder',
            email='founder@authoritylabs.com',
            description='Test company',
            sector='SaaS',
            stage='Seed',
        )
        self.client.force_login(self.user)

    def _verify_company_email(self):
        verification = BusinessEmailVerification.objects.create(
            user=self.user,
            business_email='founder@authoritylabs.com',
        )
        verification.status = 'VERIFIED'
        verification.verified_at = timezone.now()
        verification.save(update_fields=['status', 'verified_at'])
        return verification

    def test_email_verification_is_a_mailbox_fact_not_role_verification(self):
        self.assertFalse(self.application.is_verified)
        self._verify_company_email()
        self.assertTrue(business_email_verified(self.user))
        self.application.refresh_from_db()
        self.assertFalse(
            self.application.is_verified,
            'company-email OTP must not silently become broad profile verification',
        )

    def test_representation_attestation_requires_verified_company_email(self):
        response = self.client.post(reverse('accounts:company_representation_attest'), {
            'relationship': 'FOUNDER_OWNER',
            'role_title': 'Founder',
            'authorized_to_represent': 'on',
        })
        self.assertRedirects(response, reverse('accounts:business_verification'))
        self.assertFalse(CompanyRepresentationAttestation.objects.filter(user=self.user).exists())

    def test_representation_is_stored_as_a_separate_self_attestation(self):
        self._verify_company_email()
        response = self.client.post(reverse('accounts:company_representation_attest'), {
            'relationship': 'FOUNDER_OWNER',
            'role_title': 'Founder & CEO',
            'authorized_to_represent': 'on',
        })
        self.assertRedirects(response, reverse('accounts:business_verification'))

        attestation = current_company_representation(self.user, 'Authority Labs')
        self.assertIsNotNone(attestation)
        self.assertEqual(attestation.relationship, 'FOUNDER_OWNER')
        self.assertEqual(attestation.role_title, 'Founder & CEO')
        self.assertTrue(attestation.authorized_to_represent)

        self.application.refresh_from_db()
        self.assertFalse(self.application.is_verified)

    def test_attestation_requires_explicit_authority_checkbox(self):
        self._verify_company_email()
        response = self.client.post(reverse('accounts:company_representation_attest'), {
            'relationship': 'FOUNDER_OWNER',
            'role_title': 'Founder',
        })
        self.assertRedirects(response, reverse('accounts:business_verification'))
        self.assertIsNone(current_company_representation(self.user, 'Authority Labs'))

    def test_withdrawal_preserves_history_but_removes_current_state(self):
        self._verify_company_email()
        attestation = CompanyRepresentationAttestation.objects.create(
            user=self.user,
            company_name='Authority Labs',
            relationship='FOUNDER_OWNER',
            role_title='Founder',
            authorized_to_represent=True,
        )
        response = self.client.post(reverse('accounts:company_representation_withdraw'))
        self.assertRedirects(response, reverse('accounts:business_verification'))

        attestation.refresh_from_db()
        self.assertIsNotNone(attestation.withdrawn_at)
        self.assertIsNone(current_company_representation(self.user, 'Authority Labs'))

    def test_page_labels_email_and_representation_as_distinct_signals(self):
        self._verify_company_email()
        CompanyRepresentationAttestation.objects.create(
            user=self.user,
            company_name='Authority Labs',
            relationship='FOUNDER_OWNER',
            role_title='Founder',
            authorized_to_represent=True,
        )
        response = self.client.get(reverse('accounts:business_verification'))
        self.assertContains(response, 'Company Email Verified')
        self.assertContains(response, 'Representation Self-Attested')
        self.assertContains(response, 'not independent verification by Interlink')
        self.assertContains(response, 'It does not verify ownership, job title, or authority to represent the company.')

    def test_journey_email_step_reads_otp_evidence_not_is_verified(self):
        self.application.pitch_deck = SimpleUploadedFile(
            'deck.pdf', b'%PDF-1.4 test', content_type='application/pdf'
        )
        self.application.save(update_fields=['pitch_deck'])

        before = compute_founder_journey_stage(self.user)
        email_step = next(item for item in before['checklist'] if item['label'] == 'Verify your business email')
        self.assertFalse(email_step['done'])

        self._verify_company_email()
        after = compute_founder_journey_stage(self.user)
        email_step = next(item for item in after['checklist'] if item['label'] == 'Verify your business email')
        self.assertTrue(email_step['done'])
