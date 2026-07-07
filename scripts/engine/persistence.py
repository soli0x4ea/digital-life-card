"""Atomically persist entity state to disk with automatic backup rotation.

All read/write operations use this module. No direct file access elsewhere
in the engine.

Features:
    - Atomic write: write to .tmp, then os.replace (no partial writes)
    - Backup rotation: keep last 5 versions before overwrite
    - BOM-compatible reads: use utf-8-sig for all reads
    - Clean JSON serialization with indent
    - Directory auto-creation
    - Corrupt state recovery
"""

import json
import os
import glob
from datetime import datetime, timezone, timedelta
from typing import Any

CST = timezone(timedelta(hours=8))
BACKUP_KEEP = 5  # Number of backup versions to retain


# ── Path utilities ────────────────────────────────────────────

def _ensure_dir(path: str) -> None:
    """Create parent directories if they don't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _backup_dir(data_dir: str) -> str:
    """Return path to backups directory under data_dir."""
    return os.path.join(data_dir, ".backups")


# ── Atomic write ──────────────────────────────────────────────

def atomic_write(path: str, data: Any) -> None:
    """Write data to path atomically, with automatic backup rotation.

    Process:
        1. If target exists, rename it to a timestamped backup
        2. Write new data to .tmp file with flush+fsync
        3. os.replace tmp -> target (atomic on same filesystem)
        4. Clean up old backups (keep last BACKUP_KEEP)

    Args:
        path: Absolute path to the target file.
        data: Any JSON-serializable object.

    Raises:
        OSError: On filesystem write failure.
    """
    _ensure_dir(path)
    tmp_path = path + ".tmp"
    data_dir = os.path.dirname(path)
    bak_dir = _backup_dir(data_dir)

    # Step 1: backup current version
    if os.path.exists(path):
        try:
            os.makedirs(bak_dir, exist_ok=True)
            ts = datetime.now(CST).strftime("%Y%m%d_%H%M%S")
            bak_name = f"{os.path.basename(path)}.{ts}.bak"
            bak_path = os.path.join(bak_dir, bak_name)
            os.replace(path, bak_path)
        except OSError:
            pass  # backup failure is non-fatal

    # Step 2: write to tmp
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Step 3: atomically replace
        os.replace(tmp_path, path)

    except Exception:
        # Clean up tmp on failure
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    # Step 4: rotate old backups
    _rotate_backups(data_dir, os.path.basename(path))


def _rotate_backups(data_dir: str, basename: str) -> None:
    """Remove old backup files, keeping only the most recent BACKUP_KEEP."""
    bak_dir = _backup_dir(data_dir)
    pattern = os.path.join(bak_dir, f"{basename}.*.bak")
    backups = sorted(glob.glob(pattern))
    for old in backups[:-BACKUP_KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass


# ── JSON read ─────────────────────────────────────────────────

def read_json(path: str) -> Any:
    """Read a JSON file with BOM-compatible encoding.

    Args:
        path: Absolute path to the JSON file.

    Returns:
        Parsed JSON data (dict, list, etc.).

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def try_read_json(path: str, default: Any = None) -> Any:
    """Read a JSON file, returning default if the file is missing or corrupt.

    Args:
        path: Absolute path to the JSON file.
        default: Value to return on failure.

    Returns:
        Parsed JSON data, or default on error.
    """
    try:
        return read_json(path)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


# ── JSON write (convenience) ──────────────────────────────────

def write_json(path: str, data: Any) -> None:
    """Convenience wrapper: atomic_write for JSON data."""
    atomic_write(path, data)
