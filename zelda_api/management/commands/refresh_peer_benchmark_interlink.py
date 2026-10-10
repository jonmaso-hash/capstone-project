"""
One-time rebuild of Peer Market Benchmark Interlink comparisons saved under an
older privacy version.

Older snapshots are suppressed on render, so owners and share links see no
Interlink comparison until the report is regenerated, which the 30-day
allowance can delay for a month. This recalculates only the Interlink half from
current data under current public-viewer rules. It never runs external research
(no paid web search) and never touches the external half, sources, narrative or
the owner's refresh allowance.

Dry run by default; pass --apply to write. Safe to run twice: current snapshots
are skipped. Prints report ids and counts only, never company data.
"""
from django.core.management.base import BaseCommand

from matchmaking.models import PeerMarketBenchmark
from zelda_api.peer_benchmark import interlink_snapshot_is_current, refresh_interlink_snapshot


class Command(BaseCommand):
    help = 'Rebuild stale Peer Market Benchmark Interlink comparisons (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the rebuilt comparisons.')

    def handle(self, *args, **options):
        apply = options['apply']
        ready = PeerMarketBenchmark.objects.filter(status='ready').only('id', 'interlink_benchmark')
        stale = [b.id for b in ready.iterator() if not interlink_snapshot_is_current(b.interlink_benchmark)]
        self.stdout.write(f'{len(stale)} ready benchmark(s) need an Interlink rebuild: {stale}')
        if not apply:
            self.stdout.write('Dry run: nothing written. Re-run with --apply to rebuild.')
            return
        refreshed = [pk for pk in stale if refresh_interlink_snapshot(pk)]
        self.stdout.write(f'Rebuilt {len(refreshed)}: {refreshed}')
        skipped = sorted(set(stale) - set(refreshed))
        if skipped:
            self.stdout.write(f'Skipped {len(skipped)} (no longer ready, already current, or no profile): {skipped}')
