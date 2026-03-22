"""Respaldos semanales de base de datos."""

from __future__ import annotations

from datetime import date, datetime
import os
import shutil
import subprocess
from typing import Optional

from sqlalchemy.orm import Session

from app.config import config
from app.models import ConfigSistema

LAST_BACKUP_WEEK_KEY = "LAST_BACKUP_WEEK"
BACKUP_DIR_KEY = "BACKUP_DIR_PATH"


def _get_config_row(db: Session, key: str) -> Optional[ConfigSistema]:
    return db.query(ConfigSistema).filter(ConfigSistema.clave == key).first()


def _set_config_value(db: Session, key: str, value: str) -> None:
    row = _get_config_row(db, key)
    if row is None:
        row = ConfigSistema(clave=key, valor=value)
        db.add(row)
    else:
        row.valor = value
    db.commit()


def _normalize_backup_dir(raw: str | None) -> str:
    candidate = str(raw or "").strip().strip('"')
    if not candidate:
        candidate = os.getenv("BACKUP_DIR", config.BACKUP_FOLDER)
    return os.path.abspath(os.path.expanduser(candidate))


def get_backup_dir(db: Session | None = None) -> str:
    if db is not None:
        row = _get_config_row(db, BACKUP_DIR_KEY)
        if row and row.valor:
            return _normalize_backup_dir(row.valor)
    return _normalize_backup_dir(os.getenv("BACKUP_DIR", config.BACKUP_FOLDER))


def set_backup_dir(db: Session, backup_dir: str, create_if_missing: bool = True) -> dict:
    normalized = _normalize_backup_dir(backup_dir)
    if create_if_missing:
        os.makedirs(normalized, exist_ok=True)
    if not os.path.isdir(normalized):
        raise ValueError("La ruta indicada no existe o no es un directorio válido")
    _set_config_value(db, BACKUP_DIR_KEY, normalized)
    return {"backup_dir": normalized, "exists": True}


def current_week_key(ref: date | None = None) -> str:
    ref = ref or date.today()
    year, week, _ = ref.isocalendar()
    return f"{year}-W{week:02d}"


def find_mysqldump() -> Optional[str]:
    candidates = [
        shutil.which("mysqldump"),
        shutil.which("mysqldump.exe"),
        r"C:\Program Files\MariaDB 12.2\bin\mysqldump.exe",
        r"C:\Program Files\MariaDB 11.4\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def find_mysql() -> Optional[str]:
    candidates = [
        shutil.which("mysql"),
        shutil.which("mysql.exe"),
        r"C:\Program Files\MariaDB 12.2\bin\mysql.exe",
        r"C:\Program Files\MariaDB 11.4\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def list_backups(db: Session | None = None, backup_dir: str | None = None) -> list[dict]:
    """List available backup files in backup directory."""
    backup_dir = _normalize_backup_dir(backup_dir or get_backup_dir(db))
    os.makedirs(backup_dir, exist_ok=True)
    items = []
    for name in sorted(os.listdir(backup_dir), reverse=True):
        if not name.lower().endswith('.sql'):
            continue
        path = os.path.join(backup_dir, name)
        stat = os.stat(path)
        items.append({
            "filename": name,
            "path": path,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return items


def restore_backup(db: Session, filename: str, backup_dir: str | None = None) -> dict:
    """Restore database from selected SQL dump, creating a rescue backup first."""
    safe_name = os.path.basename(filename)
    backup_dir = _normalize_backup_dir(backup_dir or get_backup_dir(db))
    filepath = os.path.join(backup_dir, safe_name)
    if not os.path.exists(filepath):
        return {"status": "error", "reason": "backup file not found"}

    mysql_bin = find_mysql()
    if not mysql_bin:
        return {"status": "error", "reason": "mysql client not found"}

    rescue = create_weekly_backup(db, force=True, backup_dir=backup_dir)

    command = [
        mysql_bin,
        f"--host={config.DB_HOST}",
        f"--port={config.DB_PORT}",
        f"--user={config.DB_USER}",
        config.DB_NAME,
    ]
    env = os.environ.copy()
    if config.DB_PASSWORD:
        env["MYSQL_PWD"] = config.DB_PASSWORD

    with open(filepath, 'rb') as dump_file:
        result = subprocess.run(command, env=env, stdin=dump_file, capture_output=True)

    if result.returncode != 0:
        return {
            "status": "error",
            "reason": (result.stderr or result.stdout or b'restore failed').decode('utf-8', errors='replace').strip(),
            "file": filepath,
            "rescue_backup": rescue,
        }

    return {
        "status": "success",
        "file": filepath,
        "rescue_backup": rescue,
    }


def create_weekly_backup(db: Session, force: bool = False, backup_dir: str | None = None) -> dict:
    """Create one SQL dump per ISO week."""
    week_key = current_week_key()
    last_row = _get_config_row(db, LAST_BACKUP_WEEK_KEY)
    if last_row and last_row.valor == week_key and not force:
        return {"status": "skipped", "reason": "backup already created this week", "week": week_key}

    dump_bin = find_mysqldump()
    if not dump_bin:
        return {"status": "error", "reason": "mysqldump not found", "week": week_key}

    backup_dir = _normalize_backup_dir(backup_dir or get_backup_dir(db))
    os.makedirs(backup_dir, exist_ok=True)

    filename = f"backup_{config.DB_NAME}_{week_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    filepath = os.path.join(backup_dir, filename)

    command = [
        dump_bin,
        f"--host={config.DB_HOST}",
        f"--port={config.DB_PORT}",
        f"--user={config.DB_USER}",
        f"--result-file={filepath}",
        config.DB_NAME,
    ]
    env = os.environ.copy()
    if config.DB_PASSWORD:
        env["MYSQL_PWD"] = config.DB_PASSWORD

    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "status": "error",
            "reason": (result.stderr or result.stdout or "backup command failed").strip(),
            "week": week_key,
            "file": filepath,
        }

    _set_config_value(db, LAST_BACKUP_WEEK_KEY, week_key)
    return {
        "status": "success",
        "week": week_key,
        "file": filepath,
    }


def get_backup_settings(db: Session) -> dict:
    backup_dir = get_backup_dir(db)
    return {
        "backup_dir": backup_dir,
        "exists": os.path.isdir(backup_dir),
        "files": len(list_backups(db=db, backup_dir=backup_dir)),
    }
