"""
Migration 0022 — Revised staff role structure

Old roles:  General Staff, Financial Staff
New roles:  Accounting Staff, Marketing Staff, General Staff

- "Financial Staff" is renamed to "Accounting Staff" (data migrated).
- "Marketing Staff" is a new role (assign manually via Employee → Edit).
- "General Staff" keeps its name but is now view-only at the view-permission
  level (see views.py / templates — no schema change needed for that part).
"""

from django.db import migrations, models


def rename_financial_to_accounting(apps, schema_editor):
    UserLog = apps.get_model("app", "UserLog")
    UserLog.objects.filter(role="Financial Staff").update(role="Accounting Staff")


def reverse_rename(apps, schema_editor):
    UserLog = apps.get_model("app", "UserLog")
    UserLog.objects.filter(role="Accounting Staff").update(role="Financial Staff")


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0021_rename_tct_ar_to_columbarium"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userlog",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Accounting Staff", "Accounting Staff"),
                    ("Marketing Staff",  "Marketing Staff"),
                    ("General Staff",    "General Staff"),
                ],
                max_length=200,
                null=True,
            ),
        ),
        migrations.RunPython(rename_financial_to_accounting, reverse_rename),
    ]
