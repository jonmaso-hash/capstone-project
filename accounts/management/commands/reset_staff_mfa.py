"""Last-resort recovery through the already trusted server shell."""
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import StaffMFA


class Command(BaseCommand):
    help = 'Reset staff MFA after independently verifying the account owner. Requires trusted server-shell access.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--confirm-username', required=True)

    def handle(self, *args, **options):
        if options['username'] != options['confirm_username']:
            raise CommandError('Username confirmation does not match.')
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().filter(username=options['username'], is_staff=True).first()
            if user is None:
                raise CommandError('Staff account not found.')
            StaffMFA.objects.filter(user=user).delete()
        logging.getLogger(__name__).warning('Staff MFA reset through trusted server shell for user_id=%s', user.pk)
        self.stdout.write('MFA reset. Staff access stays blocked until the account completes new enrollment.')
