"""Single source of truth for application version and revision metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_APP_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _APP_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_VERSION_FILE = _PROJECT_ROOT / "deploy" / "version-info.json"
_CHANGELOG_FILE = _PROJECT_ROOT / "deploy" / "CHANGELOG.server.md"


DEFAULT_VERSION_INFO: dict[str, Any] = {
    "product": "Database Manager",
    "channel": "production",
    "current": {
        "version": "1.5.0",
        "revision": 10,
        "release_date": "2026-04-07",
        "codename": "QR Scanner Hardening + Smart Import Rollback",
        "summary": "Guardas de carrera QR, sesion efimera Android, importador inteligente con comparacion de campos y rollback transaccional",
    },
    "history": [],
}


def load_version_info() -> dict[str, Any]:
    if not _VERSION_FILE.exists():
        return dict(DEFAULT_VERSION_INFO)
    try:
        data = json.loads(_VERSION_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return dict(DEFAULT_VERSION_INFO)


def current_version_string() -> str:
    current = load_version_info().get("current", {})
    version = str(current.get("version") or DEFAULT_VERSION_INFO["current"]["version"])
    revision = int(current.get("revision") or DEFAULT_VERSION_INFO["current"]["revision"])
    return f"{version}-rev{revision}"


def current_version_payload() -> dict[str, Any]:
    data = load_version_info()
    current = dict(data.get("current") or {})
    current.setdefault("version", DEFAULT_VERSION_INFO["current"]["version"])
    current.setdefault("revision", DEFAULT_VERSION_INFO["current"]["revision"])
    current.setdefault("release_date", DEFAULT_VERSION_INFO["current"]["release_date"])
    current["version_string"] = current_version_string()
    current["channel"] = data.get("channel") or DEFAULT_VERSION_INFO["channel"]
    current["product"] = data.get("product") or DEFAULT_VERSION_INFO["product"]
    return current


def read_server_changelog() -> str:
    if not _CHANGELOG_FILE.exists():
        return ""
    try:
        return _CHANGELOG_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""
