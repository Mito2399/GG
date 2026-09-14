from django.db import migrations, models


def migrate_forward(apps, schema_editor):
    ClientStatus = apps.get_model("app", "ClientStatus")

    # Preserve old integer Level (1-4) into the new free-text column_level
    # field before renaming things, so no data is lost.
    for cs in ClientStatus.objects.filter(plan="Columbarium"):
        if cs.columbarium_level and not cs.column_level:
            cs.column_level = str(cs.columbarium_level)
            cs.save(update_fields=["column_level"])

    ClientStatus.objects.filter(plan="Columbarium").update(plan="TCT A/R")

    ClientStatus.objects.filter(
        columbarium_type="TCT A/R Condo Niche 1"
    ).update(columbarium_type="TCT A/R Niche 1")
    ClientStatus.objects.filter(
        columbarium_type="TCT A/R Condo Niche 2"
    ).update(columbarium_type="TCT A/R Niche 2")


def migrate_backward(apps, schema_editor):
    ClientStatus = apps.get_model("app", "ClientStatus")
    ClientStatus.objects.filter(plan="TCT A/R").update(plan="Columbarium")
    ClientStatus.objects.filter(
        columbarium_type="TCT A/R Niche 1"
    ).update(columbarium_type="TCT A/R Condo Niche 1")
    ClientStatus.objects.filter(
        columbarium_type="TCT A/R Niche 2"
    ).update(columbarium_type="TCT A/R Condo Niche 2")


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0024_ths_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientstatus",
            name="plan",
            field=models.CharField(
                max_length=200,
                choices=[
                    ("No Plan",         "No Plan"),
                    ("Lawn lot",        "Lawn lot"),
                    ("Garden lot",      "Garden lot"),
                    ("Junior court",    "Junior court"),
                    ("Executive court", "Executive court"),
                    ("Senior court",    "Senior court"),
                    ("Family estate",   "Family estate"),
                    ("Grand estate",    "Grand estate"),
                    ("THS",             "THS"),
                    ("THTC",            "THTC"),
                    ("TCT A/R",         "TCT A/R"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="clientstatus",
            name="columbarium_type",
            field=models.CharField(
                max_length=50,
                blank=True,
                null=True,
                choices=[
                    ("TCT A/R Niche 1", "TCT A/R Niche 1"),
                    ("TCT A/R Niche 2", "TCT A/R Niche 2"),
                ],
            ),
        ),
        migrations.RunPython(migrate_forward, migrate_backward),
    ]