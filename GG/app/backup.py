import csv
import datetime
import io
import logging
import smtplib
import threading
import zipfile
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from .models import (
        ActivityLog, Beneficiary, Booking,
        ClientPersonalInfo, ClientStatus, GovernmentID,
        Payment, UserLog, TCTARRenewal,
    )

logger = logging.getLogger(__name__)

_backup_lock: threading.Lock    = threading.Lock()
_last_backup_time: datetime.datetime | None = None


# ─────────────────────────────── helpers ──────────────────────────────────────

def _is_on_cooldown() -> bool:
    global _last_backup_time
    cooldown = getattr(settings, "BACKUP_COOLDOWN_MINUTES", 5)
    if _last_backup_time is None:
        return False
    elapsed = (datetime.datetime.now() - _last_backup_time).total_seconds() / 60
    return elapsed < cooldown


def _v(value):
    if value is None:
        return ""
    return str(value)


def _write_csv(zipf: zipfile.ZipFile, filename: str, headers: list, rows) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_v(cell) for cell in row])
    zipf.writestr(filename, buf.getvalue())


# ─────────────────────────────── build zip ────────────────────────────────────

def _build_zip(db_path: Path) -> tuple[bytes, str]:
    """
    C5 fix — create a consistent snapshot of the SQLite database using
    sqlite3's native backup API instead of copying the live file.
    """
    import sqlite3
    import tempfile

    from .models import (
        ActivityLog, Beneficiary, Booking,
        ClientPersonalInfo, ClientStatus, GovernmentID,
        Payment, UserLog, TCTARRenewal,
    )

    ts  = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    buf = io.BytesIO()

    snapshot_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3") as tmp:
            snapshot_path = Path(tmp.name)

        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(snapshot_path))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

            # ── 1. Clients ─────────────────────────────────────────────
            _write_csv(
                zf, "clients.csv",
                [
                    "id", "first_name", "middle_name", "last_name",
                    "address", "contact_number", "civil_status", "date_birth",
                    "religion", "occupation", "employer_name", "employer_address",
                    "spouse_name", "spouse_date_birth", "spouse_occupation", "spouse_employer",
                    # Deprecated singular ID fields kept for traceability —
                    # real IDs live in government_ids.csv now.
                    "legacy_id_type", "legacy_id_type_other", "legacy_id_number",
                ],
                [
                    (
                        c.pk, c.client_first_name, c.client_middle_name, c.client_last_name,
                        c.client_address, c.client_contact_number, c.client_civil_status,
                        c.client_date_birth, c.client_religion, c.client_occupation,
                        c.client_employer_name, c.client_employer_address,
                        c.client_spouse_name, c.client_spouse_date_birth,
                        c.client_spouse_occupation, c.client_spouse_employer,
                        c.client_id_type, c.client_id_type_other, c.client_id_number,
                    )
                    for c in ClientPersonalInfo.objects.all().order_by("pk")
                ],
            )

            # ── 1b. Government IDs ─────────────────────────────────────
            _write_csv(
                zf, "government_ids.csv",
                ["id", "client_id", "client_name", "id_type", "id_type_other", "id_number"],
                [
                    (
                        g.pk, g.client_id, g.client.full_name,
                        g.id_type, g.id_type_other or "", g.id_number,
                    )
                    for g in GovernmentID.objects.select_related("client")
                                                 .order_by("client_id", "pk")
                ],
            )

                        # ── 2. Beneficiaries ───────────────────────────────────────
            _write_csv(
                zf, "beneficiaries.csv",
                [
                    "id", "client_id", "client_name",
                    "beneficiary_name", "relationship", "specify_relationship",
                ],
                [
                    (
                        b.pk, b.client_id, b.client.full_name,
                        b.name, b.relationship, b.specify_relationship or "",
                    )
                    for b in Beneficiary.objects.select_related("client")
                                                 .order_by("client_id", "pk")
                ],
            )

            # ── 3. Plans (ClientStatus) ────────────────────────────────
            _write_csv(
                zf, "plans.csv",
                [
                    "id", "client_id", "client_name", "plan",
                    "monthly_payment", "duration", "months_remaining",
                    "start_date", "balance", "paid_balance",
                    "down_payment", "discount_percent", "pcare_percent",
                    "total_price", "documentation_fee", "sales_agent", "due_day",
                    "phase", "block", "section", "lot_number", "pa_number", "la_number",
                    "contract_number", "interment_date", "pa_date", "date_fully_paid",
                    "column_level", "columbarium_type", "columbarium_level", "tomb_number",
                    "ths_type", "ths_section", "ths_column",
                    "lawn_lot_type", "regular_lot_package",
                    "garden_type", "garden_section",
                    "mausoleum_type", "sqm",
                    "date_of_death", "death_certificate_number",
                    "status", "is_cancelled", "cancellation_reason", "cancellation_date",
                ],
                [
                    (
                        cs.pk, cs.client_id, cs.client.full_name, cs.plan,
                        cs.monthly_payment, cs.duration, cs.months_remaining,
                        cs.start_date, cs.balance, cs.paid_balance,
                        cs.down_payment, cs.discount_percent, cs.pcare_percent,
                        cs.total_price, cs.documentation_fee, cs.sales_agent, cs.due_day,
                        cs.phase, cs.block, cs.section, cs.lot_number, cs.pa_number, cs.la_number,
                        cs.contract_number, cs.interment_date, cs.pa_date, cs.date_fully_paid,
                        cs.column_level, cs.columbarium_type, cs.columbarium_level, cs.tomb_number,
                        cs.ths_type, cs.ths_section, cs.ths_column,
                        cs.lawn_lot_type, cs.regular_lot_package,
                        cs.garden_type, cs.garden_section,
                        cs.mausoleum_type, cs.sqm,
                        cs.date_of_death, cs.death_certificate_number,
                        cs.status, cs.is_cancelled, cs.cancellation_reason, cs.cancellation_date,
                    )
                    for cs in ClientStatus.objects.select_related("client").order_by("pk")
                ],
            )

            # ── 4. Payments ────────────────────────────────────────────
            _write_csv(
                zf, "payments.csv",
                [
                    "id", "client_status_id", "client_name", "plan",
                    "installment_no", "csi_number",
                    "month", "amount", "is_paid", "date_paid", "processed_by",
                    "lot_amount", "pcare_amount",
                    "penalty_charges", "payment_charges",
                    "installment_due", "running_balance",
                    "running_pcare_balance", "running_total_balance",
                    "note",
                ],
                [
                    (
                        p.pk, p.client_status_id,
                        p.client_status.client.full_name,
                        p.client_status.plan,
                        p.installment_no, p.csi_number,
                        p.month, p.amount, p.is_paid, p.date_paid,
                        (p.processed_by.username if p.processed_by else ""),
                        p.lot_amount, p.pcare_amount,
                        p.penalty_charges, p.payment_charges,
                        p.installment_due, p.running_balance,
                        p.running_pcare_balance, p.running_total_balance,
                        p.note,
                    )
                    for p in Payment.objects
                        .select_related("client_status__client", "processed_by")
                        .order_by("client_status_id", "month")
                ],
            )

            # ── 4b. TCT/A/R Renewals ───────────────────────────────────
            _write_csv(
                zf, "tct_renewals.csv",
                [
                    "id", "client_status_id", "client_name", "plan",
                    "renewal_number", "previous_expiration_date",
                    "renewal_date", "new_expiration_date",
                    "renewal_period_years", "status", "note",
                    "processed_by", "created_at",
                ],
                [
                    (
                        r.pk, r.client_status_id,
                        r.client_status.client.full_name,
                        r.client_status.plan,
                        r.renewal_number,
                        r.previous_expiration_date,
                        r.renewal_date,
                        r.new_expiration_date,
                        r.renewal_period_years,
                        r.status,
                        r.note,
                        (r.processed_by.username if r.processed_by else ""),
                        r.created_at,
                    )
                    for r in TCTARRenewal.objects
                        .select_related("client_status__client", "processed_by")
                        .order_by("client_status_id", "renewal_number")
                ],
            )

            # ── 5. Bookings ────────────────────────────────────────────
            _write_csv(
                zf, "bookings.csv",
                [
                    "id", "client_id", "client_name", "contact_number", "event_type",
                    "booking_date", "booking_time", "notes",
                    "status", "cancellation_reason", "cancelled_at", "created_at",
                ],
                [
                    (
                        b.pk, b.client_id, b.client_name, b.contact_number, b.event_type,
                        b.booking_date, b.get_booking_time_display(), b.notes,
                        b.status, b.cancellation_reason, b.cancelled_at, b.created_at,
                    )
                    for b in Booking.objects.all().order_by("booking_date", "booking_time")
                ],
            )

            # ── 6. Employees ───────────────────────────────────────────
            _write_csv(
                zf, "employees.csv",
                [
                    "id", "username", "role",
                    "first_name", "middle_name", "last_name",
                    "date_of_birth", "address", "phone_number", "email",
                    "emergency_contact_name", "emergency_contact_number",
                    "government_id", "time_in", "time_out", "last_activity",
                ],
                [
                    (
                        e.pk,
                        (e.user.username if e.user else ""),
                        e.role, e.first_name, e.middle_name, e.last_name,
                        e.date_of_birth, e.address, e.phone_number, e.email,
                        e.emergency_contact_name, e.emergency_contact_number,
                        e.government_id, e.time_in, e.time_out, e.activities,
                    )
                    for e in UserLog.objects.select_related("user").order_by("pk")
                ],
            )

            # ── 7. Activity Logs ───────────────────────────────────────
            _write_csv(
                zf, "activity_logs.csv",
                ["id", "staff_name", "role", "action", "detail", "timestamp"],
                [
                    (a.pk, a.staff_name, a.role, a.action, a.detail, a.timestamp)
                    for a in ActivityLog.objects.all().order_by("timestamp")
                ],
            )

            # ── 8. Snapshot (consistent) instead of live file ─────────
            zf.write(str(snapshot_path), arcname="db.sqlite3")

    finally:
        if snapshot_path and snapshot_path.exists():
            try:
                snapshot_path.unlink()
            except Exception:
                pass

    return buf.getvalue(), ts


# ─────────────────────────────── offline (local) ──────────────────────────────

def _get_offline_dir() -> Path:
    default = settings.BASE_DIR / "backups"
    return Path(getattr(settings, "BACKUP_OFFLINE_DIR", str(default)))


def _save_offline(zip_bytes: bytes, filename: str) -> bool:
    directory = _get_offline_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(zip_bytes)
        logger.info("[Backup] Local saved → %s", directory / filename)
        return True
    except Exception as exc:
        logger.error("[Backup] Local save failed: %s", exc)
        return False


def _cleanup_offline() -> None:
    retention = getattr(settings, "BACKUP_RETENTION_DAYS", 90)
    cutoff    = datetime.datetime.now() - datetime.timedelta(days=retention)
    directory = _get_offline_dir()
    if not directory.exists():
        return
    for f in directory.glob("backup_*.zip"):
        try:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                logger.info("[Backup] Deleted old local backup: %s", f.name)
        except Exception as exc:
            logger.warning("[Backup] Could not delete %s: %s", f, exc)


# ─────────────────────────────── cloud (Email SMTP) ───────────────────────────

def _send_email_backup(zip_bytes: bytes, filename: str) -> bool:
    try:
        from .models import SystemSecret

        host = SystemSecret.get(
            "BACKUP_EMAIL_HOST",
            getattr(settings, "BACKUP_EMAIL_HOST", "smtp.gmail.com"),
        )
        port = int(SystemSecret.get(
            "BACKUP_EMAIL_PORT",
            str(getattr(settings, "BACKUP_EMAIL_PORT", 587)),
        ))
        user = SystemSecret.get(
            "BACKUP_EMAIL_USER",
            getattr(settings, "BACKUP_EMAIL_USER", ""),
        )
        password = SystemSecret.get(
            "BACKUP_EMAIL_PASSWORD",
            getattr(settings, "BACKUP_EMAIL_PASSWORD", ""),
        )
        to = SystemSecret.get(
            "BACKUP_EMAIL_TO",
            getattr(settings, "BACKUP_EMAIL_TO", ""),
        )
    except Exception as exc:
        logger.error("[Backup] Failed to load email secrets from DB: %s", exc)
        return False

    if not all([user, password, to]):
        logger.warning(
            "[Backup] Email backup skipped — credentials not configured. "
            "Go to System Settings to set them."
        )
        return False

    try:
        import smtplib
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import datetime

        now_str = datetime.datetime.now().strftime("%B %d, %Y %I:%M %p")

        msg            = MIMEMultipart()
        msg["From"]    = f"Green Garden Backup <{user}>"
        msg["To"]      = to
        msg["Subject"] = f"[Green Garden] Backup — {now_str}"

        body_text = (
            f"Automated backup from Green Garden cemetery management system.\n\n"
            f"Date     : {now_str}\n"
            f"File     : {filename}\n"
            f"Contents : clients, government_ids, plans, payments, tct_renewals, "
            f"bookings, employees, logs, db\n\n"
            f"Keep this email as a recovery point.\n"
            f"To restore: extract the ZIP and import the CSVs or replace db.sqlite3."
        )
        msg.attach(MIMEText(body_text, "plain"))

        attachment = MIMEBase("application", "zip")
        attachment.set_payload(zip_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        msg.attach(attachment)

        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        logger.info("[Backup] Email sent → %s", to)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("[Backup] Email auth failed — check App Password in System Settings. %s", exc)
        return False
    except smtplib.SMTPConnectError as exc:
        logger.error("[Backup] Email connection failed — check internet/firewall. %s", exc)
        return False
    except Exception as exc:
        logger.error("[Backup] Email backup failed (%s): %s", type(exc).__name__, exc)
        return False


# ─────────────────────────────── core ─────────────────────────────────────────

def _do_backup(trigger: str, force: bool = False) -> dict:
    global _last_backup_time

    with _backup_lock:
        if not force and _is_on_cooldown():
            logger.debug("[Backup] Skipped — cooldown active.")
            return {"success": False, "reason": "cooldown"}

        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            logger.warning("[Backup] Database not found: %s", db_path)
            return {"success": False, "reason": "db_not_found"}

        try:
            zip_bytes, ts = _build_zip(db_path)
        except Exception as exc:
            logger.error("[Backup] Failed to build archive: %s", exc)
            return {"success": False, "reason": str(exc)}

        filename   = f"backup_{ts}_{trigger}.zip"
        offline_ok = _save_offline(zip_bytes, filename)
        cloud_ok   = _send_email_backup(zip_bytes, filename)

        if not offline_ok and not cloud_ok:
            return {"success": False, "reason": "all_destinations_failed"}

        _last_backup_time = datetime.datetime.now()
        _cleanup_offline()

        return {
            "success":  True,
            "filename": filename,
            "offline":  offline_ok,
            "cloud":    cloud_ok,
            "path":     str(_get_offline_dir() / filename),
        }


def trigger_backup(trigger: str = "activity") -> None:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in trigger)[:30]
    threading.Thread(
        target=_do_backup,
        args=(safe,),
        kwargs={"force": False},
        daemon=True,
        name=f"gg-backup-{safe}",
    ).start()


def trigger_manual_backup() -> dict:
    return _do_backup("manual", force=True)