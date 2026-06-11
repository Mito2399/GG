"""
app/backup.py

Automatic backup system for Green Garden.

  Offline → copies db.sqlite3 to a local / external-drive folder.
  Cloud   → uploads db.sqlite3 to Dropbox via API (free 2 GB plan is enough).
            No desktop app required — just a token in settings.py.

Setup
-----
1. pip install dropbox            (add to Pipfile under [packages])

2. Create a free Dropbox account → https://www.dropbox.com/developers/apps
      • Click "Create app"
      • Choose "Scoped access" → "Full Dropbox" (or App folder)
      • Go to the "Permissions" tab → tick:
            files.content.write
            files.content.read
      • Go to the "Settings" tab → under "OAuth 2" click
        "Generate access token" and copy it.

3. Add to GG/GG/settings.py:

    BACKUP_OFFLINE_DIR       = "D:/Backups/GreenGarden"   # external drive / USB
    DROPBOX_ACCESS_TOKEN     = "sl.XXXXXXXXXXXXXXXXXXXX"  # token from step 2
    DROPBOX_BACKUP_FOLDER    = "/GreenGardenBackups"      # folder inside Dropbox
    BACKUP_COOLDOWN_MINUTES  = 15
    BACKUP_RETENTION_DAYS    = 90
"""

import datetime
import logging
import shutil
import threading
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_backup_lock = threading.Lock()
_last_backup_time: datetime.datetime | None = None


# ─────────────────────────────── helpers ──────────────────────────────────────

def _is_on_cooldown() -> bool:
    global _last_backup_time
    cooldown = getattr(settings, "BACKUP_COOLDOWN_MINUTES", 15)
    if _last_backup_time is None:
        return False
    elapsed = (datetime.datetime.now() - _last_backup_time).total_seconds() / 60
    return elapsed < cooldown


# ─────────────────────────────── offline ──────────────────────────────────────

def _save_offline(db_path: Path, filename: str) -> bool:
    offline_dir = getattr(settings, "BACKUP_OFFLINE_DIR", None)
    if not offline_dir:
        return False
    directory = Path(offline_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, directory / filename)
        logger.info("[Backup] Offline saved → %s", directory / filename)
        return True
    except Exception as exc:
        logger.error("[Backup] Offline save failed: %s", exc)
        return False


def _cleanup_offline() -> None:
    offline_dir = getattr(settings, "BACKUP_OFFLINE_DIR", None)
    if not offline_dir:
        return
    retention = getattr(settings, "BACKUP_RETENTION_DAYS", 90)
    cutoff    = datetime.datetime.now() - datetime.timedelta(days=retention)
    directory = Path(offline_dir)
    if not directory.exists():
        return
    for f in directory.glob("db_backup_*.sqlite3"):
        try:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                logger.info("[Backup] Deleted old offline backup: %s", f.name)
        except Exception as exc:
            logger.warning("[Backup] Could not delete %s: %s", f, exc)


# ─────────────────────────────── cloud (Dropbox) ──────────────────────────────

def _upload_to_dropbox(db_path: Path, filename: str) -> bool:
    token = getattr(settings, "DROPBOX_ACCESS_TOKEN", None)
    if not token:
        return False
    try:
        import dropbox
        from dropbox.files import WriteMode

        folder      = getattr(settings, "DROPBOX_BACKUP_FOLDER", "/GreenGardenBackups")
        remote_path = f"{folder.rstrip('/')}/{filename}"

        with dropbox.Dropbox(token) as dbx:
            with open(db_path, "rb") as f:
                dbx.files_upload(f.read(), remote_path, mode=WriteMode.overwrite)

        logger.info("[Backup] Cloud (Dropbox) uploaded → %s", remote_path)
        return True
    except ImportError:
        logger.error("[Backup] Dropbox SDK not installed. Run: pip install dropbox")
        return False
    except Exception as exc:
        logger.error("[Backup] Dropbox upload failed: %s", exc)
        return False


def _cleanup_dropbox() -> None:
    token = getattr(settings, "DROPBOX_ACCESS_TOKEN", None)
    if not token:
        return
    try:
        import dropbox
        from dropbox.files import FileMetadata

        retention = getattr(settings, "BACKUP_RETENTION_DAYS", 90)
        cutoff    = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention)
        folder    = getattr(settings, "DROPBOX_BACKUP_FOLDER", "/GreenGardenBackups")

        with dropbox.Dropbox(token) as dbx:
            try:
                result = dbx.files_list_folder(folder)
            except dropbox.exceptions.ApiError:
                return  # folder doesn't exist yet

            for entry in result.entries:
                if isinstance(entry, FileMetadata):
                    if entry.client_modified < cutoff:
                        dbx.files_delete_v2(entry.path_lower)
                        logger.info("[Backup] Deleted old Dropbox backup: %s", entry.name)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("[Backup] Dropbox cleanup failed: %s", exc)


# ─────────────────────────────── main ─────────────────────────────────────────

def _do_backup(trigger: str) -> None:
    global _last_backup_time

    with _backup_lock:
        if _is_on_cooldown():
            return

        db_path = Path(settings.DATABASES["default"]["NAME"])
        if not db_path.exists():
            logger.warning("[Backup] Database file not found: %s", db_path)
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"db_backup_{timestamp}_{trigger}.sqlite3"

        offline_ok = _save_offline(db_path, filename)
        cloud_ok   = _upload_to_dropbox(db_path, filename)

        if not offline_ok and not cloud_ok:
            logger.warning(
                "[Backup] No destinations configured. "
                "Set BACKUP_OFFLINE_DIR and/or DROPBOX_ACCESS_TOKEN in settings.py"
            )
            return

        _last_backup_time = datetime.datetime.now()
        _cleanup_offline()
        _cleanup_dropbox()


def trigger_backup(trigger: str = "activity") -> None:
    """
    Public entry point. Spawns a daemon thread so the request is never blocked.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in trigger)[:30]
    threading.Thread(
        target=_do_backup,
        args=(safe,),
        daemon=True,
        name=f"backup-{safe}",
    ).start()
