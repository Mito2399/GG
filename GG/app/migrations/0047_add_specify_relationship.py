from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0046_migrate_government_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="beneficiary",
            name="specify_relationship",
            field=models.CharField(
                blank=True, null=True, max_length=200,
                help_text="Custom relationship when 'Other' is selected.",
            ),
        ),
        migrations.AlterField(
            model_name="beneficiary",
            name="relationship",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("Husband", "Husband"),
                    ("Wife",    "Wife"),
                    ("Other",   "Other"),
                ],
                help_text="Beneficiary's relationship to the client.",
            ),
        ),
    ]