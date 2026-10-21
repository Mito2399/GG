# app/migrations/0057_clientstatus_penalty_rate_payment_overpayment.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0056_clientstatus_due_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="penalty_rate",
            field=models.DecimalField(
                decimal_places=2, 
                default=3.0, 
                help_text="Monthly penalty rate for overdue installments (%).", 
                max_digits=5
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="overpayment",
            field=models.DecimalField(
                decimal_places=2, 
                default=0.0, 
                help_text="Excess payment carried forward to next installment.", 
                max_digits=20
            ),
        ),
    ]