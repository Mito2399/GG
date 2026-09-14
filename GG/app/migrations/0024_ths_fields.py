from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0023_flexible_payments"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="ths_type",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[("Niche", "Niche"), ("Columbarium", "Columbarium")],
                help_text="THS classification — Niche or Columbarium.",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="ths_section",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[
                    ("St. Vincent", "St. Vincent"),
                    ("St. John",    "St. John"),
                    ("St. Luke",    "St. Luke"),
                    ("St. Mathew",  "St. Mathew"),
                    ("St. Mark",    "St. Mark"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="ths_column",
            field=models.CharField(blank=True, null=True, max_length=200),
        ),
    ]