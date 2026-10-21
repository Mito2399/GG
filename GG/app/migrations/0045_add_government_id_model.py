from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0044_add_lawn_garden_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="GovernmentID",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("id_type", models.CharField(
                    max_length=50,
                    choices=[
                        ("Passport",         "Passport"),
                        ("Driver's License", "Driver's License"),
                        ("National ID",      "National ID"),
                        ("SSS ID",           "SSS ID"),
                        ("GSIS ID",          "GSIS ID"),
                        ("UMID",             "UMID"),
                        ("Postal ID",        "Postal ID"),
                        ("Other",            "Other"),
                    ],
                )),
                ("id_type_other", models.CharField(
                    blank=True, max_length=100, null=True,
                    help_text="Specify ID type when 'Other' is selected.",
                )),
                ("id_number", models.CharField(max_length=50)),
                ("client", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="government_ids",
                    to="app.clientpersonalinfo",
                )),
            ],
            options={
                "ordering": ["pk"],
            },
        ),
        migrations.AlterField(
            model_name="clientpersonalinfo",
            name="client_id_type",
            field=models.CharField(
                max_length=50, blank=True, null=True,
                choices=[
                    ("Passport",         "Passport"),
                    ("Driver's License", "Driver's License"),
                    ("National ID",      "National ID"),
                    ("SSS ID",           "SSS ID"),
                    ("GSIS ID",          "GSIS ID"),
                    ("UMID",             "UMID"),
                    ("Postal ID",        "Postal ID"),
                    ("Other",            "Other"),
                ],
                help_text="DEPRECATED — use GovernmentID model instead.",
            ),
        ),
        migrations.AlterField(
            model_name="clientpersonalinfo",
            name="client_id_type_other",
            field=models.CharField(
                max_length=100, blank=True, null=True,
                help_text="DEPRECATED — specify ID type when 'Other' was selected.",
            ),
        ),
        migrations.AlterField(
            model_name="clientpersonalinfo",
            name="client_id_number",
            field=models.CharField(
                max_length=50, blank=True, null=True,
                help_text="DEPRECATED — use GovernmentID model instead.",
            ),
        ),
        migrations.RemoveField(
            model_name="clientpersonalinfo",
            name="client_date_issued",
        ),
        migrations.RemoveField(
            model_name="clientpersonalinfo",
            name="client_place_issued",
        ),
    ]