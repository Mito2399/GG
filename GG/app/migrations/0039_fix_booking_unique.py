# app/migrations/0039_fix_booking_unique.py
from django.db import migrations, models


def drop_duplicate_active_bookings(apps, schema_editor):
    """
    Before adding the constraint, cancel any active bookings that would
    violate it (same date+time). Keep the earliest one, mark the rest
    as Cancelled so historical data is preserved.
    """
    Booking = apps.get_model("app", "Booking")

    seen = set()
    to_cancel = []
    for b in Booking.objects.filter(status="Active").order_by("created_at"):
        key = (b.booking_date, b.booking_time)
        if key in seen:
            to_cancel.append(b.pk)
        else:
            seen.add(key)

    if to_cancel:
        Booking.objects.filter(pk__in=to_cancel).update(
            status="Cancelled",
            cancellation_reason="Auto-cancelled by migration 0039 (duplicate active slot).",
        )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0038_add_total_price"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="booking",
            unique_together=set(),
        ),
        migrations.RunPython(drop_duplicate_active_bookings, reverse),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                fields=["booking_date", "booking_time"],
                condition=models.Q(status="Active"),
                name="unique_active_booking_slot",
            ),
        ),
    ]