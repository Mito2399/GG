# app/management/commands/fix_balances.py
#
# One-time repair: recompute ClientStatus.balance for all non-TCT A/R plans
# using the CORRECT formula (subtract down payment from Lot balance).
#
# Run:  python manage.py fix_balances
#
from decimal import Decimal

from django.core.management.base import BaseCommand

from app.models import ClientStatus


class Command(BaseCommand):
    help = (
        "Recompute ClientStatus.balance for all non-TCT A/R plans. "
        "Fixes legacy records that used the old (incorrect) formula which "
        "did not subtract the down payment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would change; don't save.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        qs = (
            ClientStatus.objects
            .exclude(plan="No Plan")
            .exclude(plan="TCT A/R")
        )

        total   = qs.count()
        fixed   = 0
        skipped = 0

        self.stdout.write(f"Scanning {total} non-TCT A/R plan(s)…")

        for cs in qs:
            # Correct starting Lot balance (after DP)
            correct_starting_lot = cs.financed_balance_lot   # total_lot − dp_lot

            # Already-paid portion
            paid_lot = sum(
                (p.lot_amount or Decimal('0.00'))
                for p in cs.payments.filter(is_paid=True)
            )

            correct_balance = correct_starting_lot - paid_lot
            if correct_balance < 0:
                correct_balance = Decimal('0.00')

            if cs.balance == correct_balance:
                skipped += 1
                continue

            old = cs.balance
            self.stdout.write(
                f"  Plan #{cs.pk} ({cs.client.full_name} — {cs.plan}): "
                f"{old} → {correct_balance}"
            )

            if not dry_run:
                cs.balance = correct_balance
                cs.save(update_fields=["balance"])

            fixed += 1

        action = "would be" if dry_run else "were"
        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {fixed} record(s) {action} corrected; {skipped} already correct."
        ))