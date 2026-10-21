from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0028_clientstatus_la_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientpersonalinfo",
            name="client_id_type_other",
            field=models.CharField(
                blank=True,
                help_text="Specify ID type when 'Other' is selected.",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="clientpersonalinfo",
            name="client_id_type",
            field=models.CharField(
                choices=[
                    ("Passport", "Passport"),
                    ("Driver's License", "Driver's License"),
                    ("National ID", "National ID"),
                    ("SSS ID", "SSS ID"),
                    ("GSIS ID", "GSIS ID"),
                    ("UMID", "UMID"),
                    ("Postal ID", "Postal ID"),
                    ("Other", "Other"),
                ],
                max_length=50,
            ),
        ),
    ]