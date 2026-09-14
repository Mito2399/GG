# GG/app/migrations/0023_flexible_payments.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0022_update_staff_roles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="month",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="note",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
    ]