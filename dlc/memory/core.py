"""DLC Memory — Core: architecture loader + CRUD store."""

import json, os, time, uuid
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# P2-09: Architecture
# ═══════════════════════════════════════════════════════════════

@dataclass
class LayerConfig:
    id: str
    label: str = ""
    ttl_seconds: Optional[int] = None
    capacity: int = 100
    promotion_threshold: Optional[int] = None


@dataclass
class MemoryArchitecture:
    layers: list[LayerConfig] = field(default_factory=list)
    consolidation: dict = field(default_factory=dict)


class ArchitectureLoadError(Exception):
    pass


def load_architecture(identity_dir: str) -> MemoryArchitecture:
    path = os.path.join(identity_dir, "architecture.json")
    if not os.path.isfile(path):
        raise ArchitectureLoadError(f"architecture.json not found in {identity_dir}")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ArchitectureLoadError(f"Invalid JSON: {e}") from e

    layers = []
    for lr in raw.get("layers", []):
        layers.append(LayerConfig(
            id=lr["id"], label=lr.get("label", ""),
            ttl_seconds=lr.get("ttl_seconds"),
            capacity=lr.get("capacity", 100),
            promotion_threshold=lr.get("promotion_threshold"),
        ))
    return MemoryArchitecture(layers=layers, consolidation=raw.get("consolidation", {}))


# ═══════════════════════════════════════════════════════════════
# P2-10: Memory entry + CRUD store
# ═══════════════════════════════════════════════════════════════

@dataclass
class MemoryEntry:
    id: str
    layer_id: str
    content: str
    tags: list = field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "layer_id": self.layer_id,
            "content": self.content, "tags": self.tags,
            "importance": self.importance, "access_count": self.access_count,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        return cls(**{k: d.get(k, v) for k, v in {
            "id": "", "layer_id": "", "content": "", "tags": [],
            "importance": 0.5, "access_count": 0,
            "created_at": 0.0, "updated_at": 0.0,
        }.items()})


class MemoryStore:
    """Persistent, layered and file-per-entry memory store."""

    def __init__(self, state_dir: str, arch: MemoryArchitecture):
        self._dir = state_dir
        self.arch = arch
        os.makedirs(state_dir, exist_ok=True)

    def _layer_dir(self, layer_id: str) -> str:
        p = os.path.join(self._dir, layer_id)
        os.makedirs(p, exist_ok=True)
        return p

    def _entry_path(self, entry_id: str, layer_id: str = "") -> str:
        """Return entry path. If layer_id provided, use layer subdirectory.
        Otherwise scan all layers to find it (slower, used by read/delete).
        """
        if layer_id:
            return os.path.join(self._layer_dir(layer_id), f"{entry_id}.json")
        # Scan all layer dirs
        return self._find_path(entry_id) or os.path.join(self._dir, f"{entry_id}.json")

    def _find_path(self, entry_id: str) -> str | None:
        """Scan all layer subdirectories for an entry. Returns None if not found."""
        fname = f"{entry_id}.json"
        for entry in os.scandir(self._dir):
            if entry.is_dir():
                candidate = os.path.join(entry.path, fname)
                if os.path.isfile(candidate):
                    return candidate
        return None

    # ── write ──

    def write(self, layer_id: str, content: str, **kwargs) -> str:
        entry_id = uuid.uuid4().hex[:12]
        now = time.time()
        entry = MemoryEntry(
            id=entry_id, layer_id=layer_id, content=content,
            tags=kwargs.get("tags", []),
            importance=float(kwargs.get("importance", 0.5)),
            created_at=now, updated_at=now,
        )
        self._save(entry)
        self._enforce_capacity(layer_id)
        return entry_id

    def _save(self, entry: MemoryEntry) -> None:
        path = self._entry_path(entry.id, entry.layer_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)

    # ── read (increments access_count) ──

    def read(self, entry_id: str) -> Optional[MemoryEntry]:
        path = self._entry_path(entry_id)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            entry = MemoryEntry.from_dict(json.load(f))
        entry.access_count += 1
        entry.updated_at = time.time()
        self._save(entry)
        return entry

    # ── update ──

    def update(self, entry_id: str, **kwargs) -> Optional[MemoryEntry]:
        entry = self._load_raw(entry_id)
        if entry is None:
            return None
        if "content" in kwargs:
            entry.content = kwargs["content"]
        if "importance" in kwargs:
            entry.importance = float(kwargs["importance"])
        if "tags" in kwargs:
            entry.tags = kwargs["tags"]
        entry.updated_at = time.time()
        self._save(entry)
        return entry

    def _load_raw(self, entry_id: str) -> Optional[MemoryEntry]:
        path = self._entry_path(entry_id)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return MemoryEntry.from_dict(json.load(f))

    # ── delete ──

    def delete(self, entry_id: str) -> bool:
        path = self._entry_path(entry_id)
        if not os.path.isfile(path):
            return False
        os.unlink(path)
        return True

    # ── list ──

    def list_layer(self, layer_id: str) -> list[MemoryEntry]:
        layer_dir = self._layer_dir(layer_id)
        if not os.path.isdir(layer_dir):
            return []
        entries = []
        for fname in os.listdir(layer_dir):
            if fname.endswith(".json"):
                with open(os.path.join(layer_dir, fname), "r", encoding="utf-8") as f:
                    entries.append(MemoryEntry.from_dict(json.load(f)))
        return entries

    # ── capacity enforcement ──

    def _enforce_capacity(self, layer_id: str) -> None:
        layer = next((l for l in self.arch.layers if l.id == layer_id), None)
        if not layer:
            return
        entries = sorted(self.list_layer(layer_id), key=lambda e: e.created_at)
        while len(entries) > layer.capacity:
            self.delete(entries[0].id)
            entries.pop(0)

    # ══════════════════════════════════════════════════════════
    # P2-11: TTL auto-expiry
    # ══════════════════════════════════════════════════════════

    def expire(self) -> list[MemoryEntry]:
        """Remove entries past their layer TTL. Returns expired entries."""
        expired = []
        now = time.time()
        for layer in self.arch.layers:
            if layer.ttl_seconds is None:
                continue
            for entry in self.list_layer(layer.id):
                age = now - entry.created_at
                if age > layer.ttl_seconds:
                    self.delete(entry.id)
                    expired.append(entry)
        return expired

    # ══════════════════════════════════════════════════════════
    # P2-12: Promotion
    # ══════════════════════════════════════════════════════════

    def promote(self, entry_id: str) -> bool:
        """Promote entry to next layer if access_count >= promotion_threshold."""
        entry = self._load_raw(entry_id)
        if entry is None:
            return False
        # Find current layer
        cur_idx = next((i for i, l in enumerate(self.arch.layers)
                        if l.id == entry.layer_id), -1)
        if cur_idx < 0 or cur_idx + 1 >= len(self.arch.layers):
            return False  # already at top or not found
        cur_layer = self.arch.layers[cur_idx]
        if cur_layer.promotion_threshold is None:
            return False  # top layer
        if entry.access_count < cur_layer.promotion_threshold:
            return False
        # Move to next layer
        next_layer = self.arch.layers[cur_idx + 1]
        entry.layer_id = next_layer.id
        self._save(entry)
        return True

    # ══════════════════════════════════════════════════════════
    # P2-13: Search
    # ══════════════════════════════════════════════════════════

    def search(self, keyword: str = "", **filters) -> list[MemoryEntry]:
        """Search across layers by keyword, tags, and optional layer scope.

        Returns entries ranked by access_count desc + importance.
        """
        layers_filter = filters.get("layers")
        tags_filter = filters.get("tags", [])

        results = []
        for layer_name in os.listdir(self._dir):
            layer_dir = os.path.join(self._dir, layer_name)
            if not os.path.isdir(layer_dir):
                continue
            for fname in os.listdir(layer_dir):
                if not fname.endswith(".json"):
                    continue
                with open(os.path.join(layer_dir, fname), "r", encoding="utf-8") as f:
                    entry = MemoryEntry.from_dict(json.load(f))
                if layers_filter and entry.layer_id not in layers_filter:
                    continue
                if keyword and keyword.lower() not in entry.content.lower():
                    continue
                if tags_filter:
                    if not set(tags_filter).intersection(entry.tags):
                        continue
                results.append(entry)

        # Rank by access_count desc, importance as tiebreaker
        results.sort(key=lambda e: (e.access_count, e.importance), reverse=True)
        return results

    # ══════════════════════════════════════════════════════════
    # P2-15: Consolidation
    # ══════════════════════════════════════════════════════════

    def consolidate(self) -> dict:
        """Run a full consolidation cycle: expire stale + promote eligible.

        Returns summary dict with counts.
        """
        expired = self.expire()
        promoted = 0
        # Promote eligible entries across all promotable layers
        for layer in self.arch.layers:
            if layer.promotion_threshold is None:
                continue
            for entry in self.list_layer(layer.id):
                if self.promote(entry.id):
                    promoted += 1
        return {"expired": len(expired), "promoted": promoted}


# ══════════════════════════════════════════════════════════════
# P2-16: Context injection
# ══════════════════════════════════════════════════════════════

def inject_memory_context(
    entries: list[MemoryEntry],
    max_entries: int = 10,
) -> str:
    """Format memory entries for LLM context injection.

    Returns a prompt-ready string with recent memories.
    Respects max_entries limit and sorts by importance × access_count.
    """
    if not entries:
        return ""

    # Sort by weighted score
    scored = sorted(entries, key=lambda e: e.importance * (1 + e.access_count), reverse=True)
    lines = ["[记忆上下文]"]
    for e in scored[:max_entries]:
        tag_str = f" #{' #'.join(e.tags)}" if e.tags else ""
        lines.append(f"- {e.content}{tag_str}")
    return "\n".join(lines)
