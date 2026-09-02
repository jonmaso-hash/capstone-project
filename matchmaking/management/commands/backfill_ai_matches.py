from django.core.management.base import BaseCommand

from matchmaking.models import InvestorApplication
from matchmaking.match_cache import refresh_matches_for_investor


class Command(BaseCommand):
    help = (
        "One-time backfill: populates the AIMatch cache for every existing "
        "investor against every eligible founder. Only needed once, right "
        "after the AIMatch cache was introduced — from then on, profile "
        "saves and milestones keep it fresh automatically (see "
        "matchmaking/signals.py and matchmaking/match_cache.py)."
    )

    def handle(self, *args, **options):
        investors = InvestorApplication.objects.discoverable().exclude(review_status='DENIED')
        total = investors.count()
        for i, investor_profile in enumerate(investors, 1):
            refresh_matches_for_investor(investor_profile, "Initial match cache backfill")
            self.stdout.write(f"[{i}/{total}] Refreshed matches for investor {investor_profile.user.username}")
        self.stdout.write(self.style.SUCCESS(f"Backfilled AIMatch cache for {total} investors."))
