from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0039_fix_booking_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientstatus",
            name="date_of_death",
            field=models.DateField(
                blank=True, null=True,
                help_text="Date of death (relevant for TCT A/R plans).",
            ),
        ),
        migrations.AddField(
            model_name="clientstatus",
            name="death_certificate_number",
            field=models.CharField(
                blank=True, null=True, max_length=200,
                help_text="Death certificate number (relevant for TCT A/R plans).",
            ),
        ),
    ]