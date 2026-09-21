"""
Tell existing founders that their profile defaults changed under them.

Per-field visibility arrived with defaults rather than a blank slate: a
founder's raise amount, revenue, prior funding, use of funds and name moved
from "any signed-in account" to "investors you have accepted". That is a
tightening, so nobody is newly exposed -- but a founder who never opens the
settings page will still find their profile quieter than it was, and the
honest thing is to say so rather than let them infer it from fewer
introduction requests.

A command rather than a migration or a signal. Migrations run in tests and on
every developer's machine, so sending from one would mean a test suite that
mails people; a signal would fire on unrelated saves. This runs once, when you
decide the release is live, and can be rehearsed with --dry-run first.

Idempotent by construction: a founder who already has a notification of this
type is skipped, so running it twice, or running it again after new profiles
are backfilled, does not send twice.
"""
from django.core.management.base import BaseCommand

from matchmaking.models import Application

NOTIFICATION_TYPE = 'PROFILE_VISIBILITY_DEFAULTS'

# Notification.message is 255 characters. Says what changed, what it means, and
# where to act -- in that order, because a founder reading half of it should
# still come away with the part that affects them.
MESSAGE = (
    "You can now choose who sees each part of your profile. Your raise amount, "
    "revenue, prior funding and use of funds now show only to investors you have "
    "accepted. Your company name and description stay public. Change any of this "
    "in your profile settings."
)


class Command(BaseCommand):
    help = "Notify founders once that per-field profile visibility defaults were applied."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report who would be notified without creating anything.',
        )

    def handle(self, *args, **options):
        from django.urls import reverse
        from notifications.models import Notification

        already = set(
            Notification.objects.filter(notification_type=NOTIFICATION_TYPE)
            .values_list('recipient_id', flat=True)
        )
        # Only founders the backfill actually touched: a profile created after
        # the feature shipped chose its own settings and was never surprised.
        pending = (
            Application.objects
            .filter(field_visibility_defaults_applied_at__isnull=False)
            .exclude(user_id__in=already)
            .select_related('user')
        )

        target = reverse('usersettings:edit_founder_profile')
        count = 0
        for application in pending:
            if options['dry_run']:
                self.stdout.write(f'would notify {application.user.username}')
            else:
                Notification.objects.create(
                    recipient=application.user,
                    sender=None,  # from the platform, not a person
                    notification_type=NOTIFICATION_TYPE,
                    message=MESSAGE,
                    target_url=target,
                )
            count += 1

        verb = 'Would notify' if options['dry_run'] else 'Notified'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {count} founder(s); {len(already)} already had this notice.'
        ))
