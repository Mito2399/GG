from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0032_remove_clientstatus_pcare_rate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="client",
            field=models.ForeignKey(
                blank=True,
                help_text="Link to existing client record. Leave blank for walk-in clients.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bookings",
                to="app.clientpersonalinfo",
            ),
        ),
    ]