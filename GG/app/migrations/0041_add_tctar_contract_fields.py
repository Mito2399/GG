from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0040_add_death_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="documentation_fee",
            field=models.DecimalField(
                max_digits=20, decimal_places=2, default=0,
                help_text="Documentation fee (relevant for TCT A/R contracts).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="sales_agent",
            field=models.CharField(
                max_length=200, blank=True, null=True,
                help_text="Sales agent (relevant for TCT A/R contracts).",
            ),
        ),
    ]