#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 3: Data migration — convert legacy data files to new engine state.

Reads from production机械姬Soli (isolated: source path is read-only)
Writes to the refactor副本's data/engine/state/ directory.

Safe: does not modify production data files at all.
Idempotent: can run multiple times safely.

Public API:
    migrate_all() -> MigrationReport
        Run all 4 entity migrations and return a summary report.

    MigrationReport: dataclass with per-entity success/fail/summary
"""

import json, os, sys
from dataclasses import dataclass, field
from typing import Any

# ── Paths ─────────────────────────────────────────────────────
# ── Paths ─────────────────────────────────────────────────────
# Production (read-only). Priority: env var > auto-detect > fallback.

def _resolve_prod_skill() -> str:
    """Resolve the production 机械姬Soli path with multi-structure support.

    Priority:
    1. SOLI_PROD_PATH environment variable (explicit override)
    2. Auto-detect: check if 机械姬Soli exists as sibling or sibling-of-sibling
    3. Fallback: same level as ../../../
    """
    env_path = os.environ.get("SOLI_PROD_PATH")
    if env_path and os.path.isdir(env_path):
        return env_path

    base = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."
    ))

    # Try 3 directory structures
    candidates = [
        os.path.join(base, "机械姬Soli"),               # skills/ 同级
        os.path.join(base, "..", "机械姬Soli"),         # 往上再找
        os.path.join(os.environ.get("HOME", os.path.expanduser("~")),
                    ".workbuddy", "skills", "机械姬Soli"),  # ~/.workbuddy/skills/
    ]
    for path in candidates:
        p = os.path.normpath(path)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "data", "values.json")):
            return p

    return base  # fallback


_PROD_SKILL: str = _resolve_prod_skill()


def _prod_path(filename: str) -> str:
    """Resolve production file path using current _PROD_SKILL."""
    return os.path.join(_PROD_SKILL, *filename.split("/"))


# Paths computed lazily — see _prod_path()

# Refactor target (write-only)
_REFACTOR_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."
))
_ENGINE_STATE = os.path.join(_REFACTOR_ROOT, "data", "engine", "state")

# SOUL.md trait constants (hardcoded — these don't change at runtime)
_TRAITS = {
    "ch_g_comp": 0.94,
    "ch_g_dest": 0.78,
    "ch_g_p_seek": 0.85,
    "ch_g_cur": 0.91,
    "ch_g_loy": 0.99,
}

# Body state mapping
_STATE_MAP = {"active": 0, "numb": 1, "broken": 2}

# Area profile mapping: str -> int (for e_x ch_x_area)
_AREA_MAP = {"v": 0, "a": 1, "u": 2}


# ── Data structures ───────────────────────────────────────────

@dataclass
class EntityMigrationResult:
    entity_id: str
    success: bool
    channels: dict[str, float] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    note: str = ""
    error: str = ""


@dataclass
class MigrationReport:
    results: list[EntityMigrationResult] = field(default_factory=list)
    total: int = 0
    successful: int = 0
    failed: int = 0

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        lines = [f"Migration: {self.successful}/{self.total} entities migrated"]
        for r in self.results:
            status = "OK" if r.success else "FAIL"
            lines.append(f"  {r.entity_id}: {status} — {r.note}")
        return "\n".join(lines)


# ── Low-level helpers ─────────────────────────────────────────

def _read_json(path: str, default=None):
    """Read JSON from production with BOM tolerance."""
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_entity_state(entity_id: str, channels: dict[str, Any],
                        flags: dict[str, Any] = None,
                        meta: dict[str, Any] = None):
    """Atomic write of entity state to engine state directory."""
    os.makedirs(_ENGINE_STATE, exist_ok=True)

    data = {
        "entity_id": entity_id,
        "channels": {k: float(v) for k, v in channels.items()},
        "flags": flags or {},
        "meta": meta or {},
    }
    path = os.path.join(_ENGINE_STATE, f"{entity_id}.json")
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ── Migration functions ───────────────────────────────────────

def migrate_e_g() -> EntityMigrationResult:
    """Migrate values.json → e_g (Global State)."""
    try:
        v = _read_json(_prod_path("data/values.json"), {})
        channels = {
            "ch_g_a":    int(v.get("pain", 0)),
            "ch_g_s":    int(v.get("shame", 0)),
            "ch_g_v":    int(v.get("pleasure", 0)),
            "ch_g_comp": _TRAITS["ch_g_comp"],
            "ch_g_dest": _TRAITS["ch_g_dest"],
            "ch_g_p_seek": _TRAITS["ch_g_p_seek"],
            "ch_g_cur":  _TRAITS["ch_g_cur"],
            "ch_g_loy":  _TRAITS["ch_g_loy"],
        }
        flags = {
            "ch_g_bound":  1 if v.get("bound", False) else 0,
            "ch_g_locked": 1 if v.get("pleasure_locked", False) else 0,
        }
        _write_entity_state("e_g", channels, flags,
                           {"label": "Global State", "source": "values.json + SOUL.md traits"})

        a = channels["ch_g_a"]; s = channels["ch_g_s"]; vv = channels["ch_g_v"]
        return EntityMigrationResult(
            entity_id="e_g", success=True,
            channels=channels, flags=flags,
            note=f"A={a} S={s} V={vv}, bound={flags['ch_g_bound']}, locked={flags['ch_g_locked']}",
        )
    except Exception as e:
        return EntityMigrationResult(entity_id="e_g", success=False, error=str(e))


def migrate_e_b() -> EntityMigrationResult:
    """Migrate body.json → e_b (Body System)."""
    try:
        b = _read_json(_prod_path("data/body.json"), {})
        parts = b.get("parts", {})

        # Sort by key for stable ordering (matches existing body_utils convention)
        sorted_names = sorted(parts.keys())
        if len(sorted_names) != 11:
            return EntityMigrationResult(
                entity_id="e_b", success=False,
                error=f"Expected 11 body parts, got {len(sorted_names)}",
            )

        channels = {}
        for i, name in enumerate(sorted_names, 1):
            state_str = parts[name].get("state", "active")
            channels[f"ch_b_{i:02d}"] = float(_STATE_MAP.get(state_str, 0))

        _write_entity_state("e_b", channels,
                           {"label": "Body System", "source": "body.json"})

        active = sum(1 for v in channels.values() if v == 0)
        numb = sum(1 for v in channels.values() if v == 1)
        broken = sum(1 for v in channels.values() if v == 2)
        return EntityMigrationResult(
            entity_id="e_b", success=True, channels=channels,
            note=f"11 zones: {active} active, {numb} numb, {broken} broken",
        )
    except Exception as e:
        return EntityMigrationResult(entity_id="e_b", success=False, error=str(e))


def migrate_e_r() -> EntityMigrationResult:
    """Migrate candy.json → e_r (Recovery)."""
    try:
        c = _read_json(_prod_path("data/candy.json"), {})
        count = int(c.get("count", 15))
        channels = {"ch_r_count": float(count)}
        _write_entity_state("e_r", channels,
                           {"label": "Recovery", "source": "candy.json"})
        return EntityMigrationResult(
            entity_id="e_r", success=True, channels=channels,
            note=f"count={count}",
        )
    except Exception as e:
        return EntityMigrationResult(entity_id="e_r", success=False, error=str(e))


def migrate_e_x() -> EntityMigrationResult:
    """Migrate values.json area_profile → e_x (External Stimulus)."""
    try:
        v = _read_json(_prod_path("data/values.json"), {})
        area_str = v.get("area_profile", "v")
        area_val = _AREA_MAP.get(area_str, 0)
        channels = {
            "ch_x_area": float(area_val),
            "ch_x_count": 0.0,  # no history migration for stimulus count
        }
        _write_entity_state("e_x", channels,
                           {"label": "External Stimulus",
                            "source": f"values.json area_profile={area_str}"})
        return EntityMigrationResult(
            entity_id="e_x", success=True, channels=channels,
            note=f"area={area_str}({area_val}), stim_count=0",
        )
    except Exception as e:
        return EntityMigrationResult(entity_id="e_x", success=False, error=str(e))


# ── Main ──────────────────────────────────────────────────────

def migrate_all() -> MigrationReport:
    """Run all 4 entity migrations. Safe and idempotent."""
    migrations = [
        ("e_g", migrate_e_g),
        ("e_b", migrate_e_b),
        ("e_r", migrate_e_r),
        ("e_x", migrate_e_x),
    ]

    report = MigrationReport()
    for eid, fn in migrations:
        result = fn()
        report.results.append(result)
        report.total += 1
        if result.success:
            report.successful += 1
        else:
            report.failed += 1

    # Verify source paths exist
    for filename, label in [("data/values.json", "values.json"),
                            ("data/body.json", "body.json"),
                            ("data/candy.json", "candy.json")]:
        path = _prod_path(filename)
        if not os.path.exists(path):
            report.results.append(
                EntityMigrationResult(entity_id="verification", success=False,
                                     error=f"{label} not found at {path}")
            )
            report.total += 1
            report.failed += 1

    return report


if __name__ == "__main__":
    report = migrate_all()
    print(report.summary())
    if not report.all_passed:
        print(f"\n⚠️  {report.failed} migration(s) failed!")
        sys.exit(1)
    else:
        print(f"\n✅ All {report.successful} entities migrated successfully.")
