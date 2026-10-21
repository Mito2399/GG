from django.db import migrations


def migrate_government_ids(apps, schema_editor):
    """
    Copy each client's existing single Government ID into the new
    GovernmentID related model. The old fields remain on the model
    (deprecated, nullable) so no data is lost — new code paths use the
    GovernmentID model exclusively.
    """
    ClientPersonalInfo = apps.get_model("app", "ClientPersonalInfo")
    GovernmentID       = apps.get_model("app", "GovernmentID")

    for client in ClientPersonalInfo.objects.all().iterator():
        id_type   = (client.client_id_type or "").strip()
        id_number = (client.client_id_number or "").strip()
        if id_type and id_number:
            GovernmentID.objects.create(
                client=client,
                id_type=id_type,
                id_type_other=(client.client_id_type_other or "").strip() or None,
                id_number=id_number,
            )


def reverse_migrate(apps, schema_editor):
    """
    Reverse — restore the first GovernmentID back to the deprecated
    singular fields. Multiple IDs cannot be represented this way, so
    only the first one survives a rollback. Acceptable: the forward
    direction is a non-destructive copy.
    """
    ClientPersonalInfo = apps.get_model("app", "ClientPersonalInfo")
    GovernmentID       = apps.get_model("app", "GovernmentID")

    for client in ClientPersonalInfo.objects.all().iterator():
        first = GovernmentID.objects.filter(client=client).order_by("pk").first()
        if first:
            client.client_id_type       = first.id_type
            client.client_id_type_other = first.id_type_other or ""
            client.client_id_number     = first.id_number
            client.save(update_fields=[
                "client_id_type", "client_id_type_other", "client_id_number",
            ])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0045_add_government_id_model"),
    ]

    operations = [
        migrations.RunPython(migrate_government_ids, reverse_migrate),
    ]