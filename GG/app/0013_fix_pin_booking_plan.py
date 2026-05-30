# Generated migration — fix PIN hashing, Booking uniqueness, ClientStatus plan/duration fields

from django.db import migrations, models


def hash_existing_pins(apps, schema_editor):
    """
    Convert existing plaintext integer PINs to Django password hashes.
    Both fields exist simultaneously during this RunPython step:
      - `pin`     = old IntegerField value (still readable)
      - `pin_new` = new CharField that we populate here
    """
    from django.contrib.auth.hashers import make_password
    UserLog = apps.get_model("app", "UserLog")
    for log in UserLog.objects.all():
        raw = str(log.pin).zfill(4)   # restore leading zeros lost by IntegerField
        log.pin_new = make_password(raw)
        log.save(update_fields=["pin_new"])


def noop_reverse(apps, schema_editor):
    # Irreversible: hashed PINs cannot be recovered as integers.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0012_clientstatus_block_booking"),
    ]

    operations = [
        # ── 1. Fix ClientStatus.plan choices to include "No Plan" ─────────────
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
                ],
            ),
        ),

        # ── 2. Fix ClientStatus.duration (remove invalid max_length kwarg) ───
        migrations.AlterField(
            model_name="clientstatus",
            name="duration",
            field=models.IntegerField(
                choices=[
                    (6,  "6 Months"),
                    (12, "12 Months"),
                    (24, "24 Months"),
                    (36, "36 Months"),
                    (60, "60 Months"),
                ]
            ),
        ),

        # ── 3. PIN: add temporary hashed CharField alongside old IntegerField ─
        migrations.AddField(
            model_name="userlog",
            name="pin_new",
            field=models.CharField(max_length=128, default=""),
            preserve_default=False,
        ),

        # ── 4. Populate pin_new with hashed values from old pin ───────────────
        migrations.RunPython(hash_existing_pins, noop_reverse),

        # ── 5. Remove the old plaintext integer PIN ───────────────────────────
        migrations.RemoveField(
            model_name="userlog",
            name="pin",
        ),

        # ── 6. Rename pin_new → pin ───────────────────────────────────────────
        migrations.RenameField(
            model_name="userlog",
            old_name="pin_new",
            new_name="pin",
        ),

        # ── 7. Booking: enforce unique (date, time) at the database level ─────
        migrations.AlterUniqueTogether(
            name="booking",
            unique_together={("booking_date", "booking_time")},
        ),
    ]
