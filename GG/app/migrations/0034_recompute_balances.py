from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def recompute_balances(apps, schema_editor):
    """
    Recompute ClientStatus.balance using the corrected formula:
        total_contract = monthly_payment × duration
        total_pcare    = total_contract × pcare_percent / 100
        total_lot      = total_contract − total_pcare
        balance        = max(total_lot − Σ(lot_amount of paid payments), 0)

    Run once on every existing row. Plans already using the new code path
    will be idempotent (recomputes the same value).
    """
    ClientStatus = apps.get_model("app", "ClientStatus")
    Payment      = apps.get_model("app", "Payment")

    ZERO = Decimal("0.00")

    for cs in ClientStatus.objects.all():

        # Skip placeholder / empty plans
        if cs.plan == "No Plan" or not cs.monthly_payment or not cs.duration:
            if cs.balance != ZERO:
                cs.balance = ZERO
                cs.save(update_fields=["balance"])
            continue

        # ── Rebuild totals from scratch ──────────────────────────────
        monthly  = Decimal(cs.monthly_payment)
        duration = int(cs.duration)

        total_contract = (monthly * duration).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        pcare_pct = Decimal(cs.pcare_percent or "0")
        total_pcare = (
            total_contract * (pcare_pct / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_lot = total_contract - total_pcare

        # ── Sum what's already been paid toward the LOT side ─────────
        paid_lot = ZERO
        for p in Payment.objects.filter(client_status=cs, is_paid=True):
            paid_lot += Decimal(p.lot_amount or "0")

        new_balance = max(total_lot - paid_lot, ZERO)

        if cs.balance != new_balance:
            cs.balance = new_balance
            cs.save(update_fields=["balance"])


def reverse(apps, schema_editor):
    """No-op — we don't know the old (buggy) values to restore."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0033_booking_client_fk"),
    ]

    operations = [
        migrations.RunPython(recompute_balances, reverse),
    ]