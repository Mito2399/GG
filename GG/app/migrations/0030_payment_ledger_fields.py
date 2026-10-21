from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0029_client_id_type_other"),
    ]

    operations = [
        # Add pcare_rate to ClientStatus
        migrations.AddField(
            model_name="clientstatus",
            name="pcare_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=267.0,
                help_text="Perpetual care rate per installment.",
                max_digits=20,
            ),
        ),
        # Add new fields to Payment
        migrations.AddField(
            model_name="payment",
            name="installment_no",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Sequential installment number (1, 2, 3...).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="csi_number",
            field=models.CharField(
                blank=True,
                help_text="Control/Receipt Serial Number for audit trail.",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="lot_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Portion of payment applied to the lot installment.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="pcare_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Portion of payment applied to perpetual care.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="penalty_charges",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Late payment penalty charged.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="payment_charges",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Service/processing fee charged.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="installment_due",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Amount that was due for this installment period.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="running_balance",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Lot receivable balance after this payment.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="running_pcare_balance",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Perpetual care balance after this payment.",
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="running_total_balance",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Combined total balance after this payment.",
                max_digits=20,
            ),
        ),
    ]