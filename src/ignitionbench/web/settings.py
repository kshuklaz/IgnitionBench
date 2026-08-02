"""Local app settings under ~/.ignitionbench/settings.json.

Right now this holds only the user's Anthropic API key, for people who add it
through the app instead of exporting an environment variable. The file lives in
the user's home data dir (never in the repo) and is written 0600 because it
holds a secret. Override the location with IGNITIONBENCH_DATA_DIR (tests use it).
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

_KEY = "anthropic_api_key"


def _path() -> Path:
    root = os.environ.get("IGNITIONBENCH_DATA_DIR") or Path.home() / ".ignitionbench"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


def _read() -> dict:
    try:
        return json.loads(_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    path = _path()
    path.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 — the file holds a secret
    except OSError:
        pass  # best effort; some filesystems (e.g. Windows) don't honour chmod


def get_api_key() -> str:
    return str(_read().get(_KEY, "")).strip()


def set_api_key(key: str) -> None:
    data = _read()
    data[_KEY] = str(key).strip()
    _write(data)


def clear_api_key() -> None:
    data = _read()
    data.pop(_KEY, None)
    _write(data)


def masked_key() -> str:
    """A safe-to-display hint of the stored key, e.g. '…AB12'. Never the key."""
    key = get_api_key()
    if not key:
        return ""
    return "…" + (key[-4:] if len(key) >= 4 else key)
