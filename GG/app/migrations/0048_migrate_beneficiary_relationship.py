from django.db import migrations


NEW_VALID = {"Husband", "Wife", "Other"}


def migrate_old_relationships(apps, schema_editor):
    """
    Existing Beneficiary.relationship values come from the OLD choice list
    (Spouse, Son, Daughter, Father, Mother, Brother, Sister, ...).
    None of those match the new choices (Husband / Wife / Other).

    Forward migration:
      • If the value is already one of the new choices, leave it alone
        (but ensure 'Other' always has a specify_relationship value).
      • Otherwise, move the old value into specify_relationship and set
        relationship = "Other". Empty/None values become "Other" + "Unknown"
        so the record remains saveable from the admin form.
    """
    Beneficiary = apps.get_model("app", "Beneficiary")

    for b in Beneficiary.objects.all().iterator():
        old = (b.relationship or "").strip()

        if old in NEW_VALID:
            if old == "Other" and not (b.specify_relationship or "").strip():
                b.specify_relationship = "Unknown"
                b.save(update_fields=["specify_relationship"])
            continue

        b.specify_relationship = old or "Unknown"
        b.relationship         = "Other"
        b.save(update_fields=["relationship", "specify_relationship"])


def reverse_migrate(apps, schema_editor):
    """
    Reverse: push specify_relationship back into relationship for records
    that were migrated to 'Other'. Husband/Wife rows added after the
    migration stay put (no way to know what they were before).
    """
    Beneficiary = apps.get_model("app", "Beneficiary")

    for b in Beneficiary.objects.all().iterator():
        if b.relationship == "Other" and (b.specify_relationship or "").strip():
            b.relationship         = b.specify_relationship
            b.specify_relationship = ""
            b.save(update_fields=["relationship", "specify_relationship"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0047_add_specify_relationship"),
    ]

    operations = [
        migrations.RunPython(migrate_old_relationships, reverse_migrate),
    ]