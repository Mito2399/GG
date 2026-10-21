# app/migrations/0056_clientstatus_due_day.py
# Green Garden — per-plan monthly due-day + auto sales associate

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0055_payment_months_covered"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="due_day",
            field=models.PositiveSmallIntegerField(
                default=2,
                help_text=(
                    "Day of the month (1–31) on which monthly installments "
                    "are due. The payment schedule is generated on this day "
                    "of every month."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="clientstatus",
            name="sales_agent",
            field=models.CharField(
                max_length=200,
                blank=True,
                null=True,
                help_text="Auto-assigned from the user who created the plan.",
            ),
        ),
    ]