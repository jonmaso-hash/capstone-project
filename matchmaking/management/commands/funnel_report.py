from django.core.management.base import BaseCommand

from matchmaking.funnel import funnel_summary


class Command(BaseCommand):
    help = (
        "Prints the digest -> subscription funnel summary for a rolling "
        "window: digests sent/opened/clicked, profile views, analyses "
        "generated, subscriptions started, intros sent, deal rooms created."
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Rolling window size in days (default: 7)')

    def handle(self, *args, **options):
        summary = funnel_summary(days=options['days'])

        self.stdout.write(f"Funnel summary — last {summary['window_days']} days")
        self.stdout.write("-" * 40)
        self.stdout.write(f"Digests sent:          {summary['digests_sent']}")
        self.stdout.write(f"Digests opened:        {summary['digests_opened']} ({summary['open_rate_pct'] or 0}%)")
        self.stdout.write(f"Hero match clicked:    {summary['digests_clicked']} ({summary['click_rate_pct'] or 0}%)")
        self.stdout.write(f"Profile views:         {summary['profile_views']}")
        self.stdout.write(f"Analyses generated:    {summary['analyses_generated']}")
        self.stdout.write(f"Subscriptions started: {summary['subscriptions_started']}")
        self.stdout.write(f"Intros sent:           {summary['intros_sent']}")
        self.stdout.write(f"Intros accepted:       {summary['deal_rooms_created']}")
