from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0043_migrate_old_lot_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="lawn_lot_type",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[
                    ("Regular", "Regular"),
                    ("Deluxe",  "Deluxe"),
                    ("Prime B", "Prime B"),
                    ("Prime A", "Prime A"),
                ],
                help_text="Lawn Lot subcategory (relevant for Lawn Lot plans).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="regular_lot_package",
            field=models.CharField(
                blank=True, null=True, max_length=100,
                choices=[
                    ("3 in 1",                     "3 in 1 — Lot / 3 Days Viewing / Interment Service"),
                    ("2 in 1 - Lot/Interment",     "2 in 1 — Lawn Lot Regular / Interment"),
                    ("2 in 1 - Viewing/Interment", "2 in 1 — 3-Days Viewing / Interment Service"),
                ],
                help_text="Regular Lawn Lot package (only for Regular Lawn Lot).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="garden_type",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[
                    ("Love",      "Love"),
                    ("Happiness", "Happiness"),
                    ("Peace",     "Peace"),
                ],
                help_text="Garden Lot subcategory (relevant for Garden Lot plans).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="garden_section",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[
                    ("Regular", "Regular"),
                    ("Deluxe",  "Deluxe"),
                    ("Prime",   "Prime"),
                ],
                help_text="Garden Lot section (relevant for Garden Lot plans).",
            ),
        ),
    ]