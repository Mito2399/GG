from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def _column_exists(schema_editor, table: str, column: str) -> bool:
    """Check whether a column already exists in the SQLite table."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table})")
        return column in [row[1] for row in cursor.fetchall()]


def add_total_price_if_missing(apps, schema_editor):
    """Add total_price only if the column doesn't already exist."""
    if not _column_exists(schema_editor, "app_clientstatus", "total_price"):
        schema_editor.execute(
            "ALTER TABLE app_clientstatus "
            "ADD COLUMN total_price decimal(20, 2) NULL"
        )


def populate_total_price(apps, schema_editor):
    """Backfill total_price for all existing ClientStatus rows."""
    ClientStatus = apps.get_model("app", "ClientStatus")
    ZERO = Decimal("0.00")

    for cs in ClientStatus.objects.all():
        if cs.plan == "No Plan" or not cs.monthly_payment or not cs.duration:
            cs.total_price = ZERO
            cs.save(update_fields=["total_price"])
            continue

        monthly  = Decimal(cs.monthly_payment)
        duration = int(cs.duration)
        dp       = Decimal(cs.down_payment or "0")

        cs.total_price = (
            (monthly * duration) + dp
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cs.save(update_fields=["total_price"])


def reverse(apps, schema_editor):
    """No-op — we never drop the column on rollback."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0037_alter_booking_client_alter_payment_csi_number_and_more"),  # ← REPLACE THIS
    ]

    operations = [
        migrations.RunPython(add_total_price_if_missing, reverse),
        migrations.RunPython(populate_total_price, reverse),
    ]