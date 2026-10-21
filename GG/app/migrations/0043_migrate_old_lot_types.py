from django.db import migrations


OLD_TO_NEW = {
    "Junior court":    ("Mausoleum", "Junior Court"),
    "Executive court": ("Mausoleum", "Executive Court"),
    "Senior court":    ("Mausoleum", "Senior Court"),
    "Family estate":   ("Mausoleum", "The Estate"),
    "Grand estate":    ("Mausoleum", "The Estate"),
}


def migrate_old_plans(apps, schema_editor):
    ClientStatus = apps.get_model("app", "ClientStatus")
    for old_plan, (new_plan, mausoleum_type) in OLD_TO_NEW.items():
        ClientStatus.objects.filter(plan=old_plan).update(
            plan=new_plan,
            mausoleum_type=mausoleum_type,
        )


def reverse_migrate(apps, schema_editor):
    """
    Reverse migration — maps Mausoleum records back to the closest old
    plan name. Because 'Family estate' and 'Grand estate' both map forward
    to 'The Estate', the reverse is inherently lossy: all 'The Estate'
    records become 'Family estate'. This is acceptable — the forward
    direction preserves the original plan name in the mausoleum_type field.
    """
    ClientStatus = apps.get_model("app", "ClientStatus")

    ClientStatus.objects.filter(
        plan="Mausoleum", mausoleum_type="Junior Court"
    ).update(plan="Junior court", mausoleum_type=None)

    ClientStatus.objects.filter(
        plan="Mausoleum", mausoleum_type="Executive Court"
    ).update(plan="Executive court", mausoleum_type=None)

    ClientStatus.objects.filter(
        plan="Mausoleum", mausoleum_type="Senior Court"
    ).update(plan="Senior court", mausoleum_type=None)

    ClientStatus.objects.filter(
        plan="Mausoleum", mausoleum_type="The Estate"
    ).update(plan="Family estate", mausoleum_type=None)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0042_add_mausoleum_fields"),
    ]

    operations = [
        migrations.RunPython(migrate_old_plans, reverse_migrate),
    ]