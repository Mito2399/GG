from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0041_add_tctar_contract_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="mausoleum_type",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                choices=[
                    ("Junior Court",    "Junior Court"),
                    ("Senior Court",    "Senior Court"),
                    ("Executive Court", "Executive Court"),
                    ("The Estate",      "The Estate"),
                ],
                help_text="Mausoleum subcategory (relevant for Mausoleum plans).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="sqm",
            field=models.DecimalField(
                blank=True, null=True,
                max_digits=10, decimal_places=2,
                help_text="Size in square meters (relevant for Mausoleum plans).",
            ),
        ),
        migrations.AlterField(
            model_name="clientstatus",
            name="plan",
            field=models.CharField(
                max_length=200,
                choices=[
                    ("No Plan",    "No Plan"),
                    ("Lawn Lot",   "Lawn Lot"),
                    ("Garden Lot", "Garden Lot"),
                    ("Mausoleum",  "Mausoleum"),
                    ("THS",        "THS"),
                    ("THTC",       "THTC"),
                    ("TCT A/R",    "TCT A/R"),
                ],
            ),
        ),
    ]