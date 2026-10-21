from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models


def populate_total_price(apps, schema_editor):
    """
    Backfill total_price for existing ClientStatus rows.

    Formula: total_price = (monthly_payment × duration) + down_payment

    For rows with 'No Plan', total_price = 0.
    """
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
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0035_alter_clientstatus_pcare_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="total_price",
            field=models.DecimalField(
                max_digits=20, decimal_places=2,
                null=True, blank=True,
                help_text="Contract price as entered in the plan form (full price before down payment).",
            ),
        ),
        migrations.RunPython(populate_total_price, reverse),
    ]