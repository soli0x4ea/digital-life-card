#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
敏感区管理器 — 三区（v/a/u）的刺激状态统一读写层。
从 soul_core.py 抽出（2026-07-02），2026-07-05 池→区重命名。

所有方法接受 area 参数：
  - None → 自动解析 values.json 的 area_profile 规则选择 active 区
  - "v"/"a"/"u" → 显式指定
"""

import json
import os
from datetime import datetime, timezone, timedelta

from config import get_area_path


class AreaManager:
    """三区刺激状态管理：读写、触发/释放、清空、配置解析。"""

    # ── 配置解析 ─────────────────────────────────────────────────

    @staticmethod
    def _resolve_profile():
        """从 values.json 读取 area_profile，解析为 (area_id, narrative_key)。

        area_id 决定操作哪个区状态文件（v→area_v.json, a→area_a.json, u→area_u.json）。
        narrative_key 决定使用哪套叙事（v/blank/variant_a/variant_u）。
        """
        import utils
        v = utils.vals_read()
        key = v.get("area_profile", "v")
        _MAP = {
            "v":         ("v", "v"),
            "blank":     ("v", "blank"),
            "variant_a": ("a", "variant_a"),
            "variant_u": ("u", "variant_u"),
        }
        return _MAP.get(key, ("v", "v"))

    def get_area_id(self) -> str:
        """当前 active 区的标识（v/a/u）"""
        return self._resolve_profile()[0]

    def get_profile(self) -> str:
        """当前区配置 key（v/blank/variant_a/variant_u）"""
        return self._resolve_profile()[1]

    def _resolve_area(self, area: str = None) -> str:
        """将 None 解析为 active 区，显式值原样返回。"""
        return area if area is not None else self.get_area_id()

    # ── 区状态读写 ───────────────────────────────────────────────

    def read(self, area: str = None) -> dict:
        """读取区状态 data/area_*.json；不存在或损坏时自动初始化（自愈）"""
        area = self._resolve_area(area)
        area_path = get_area_path(area)
        try:
            with open(area_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            default = {"stimuli": []}
            os.makedirs(os.path.dirname(area_path), exist_ok=True)
            with open(area_path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default

    def write(self, data: dict, area: str = None):
        """写入区状态 data/area_*.json"""
        area = self._resolve_area(area)
        area_path = get_area_path(area)
        with open(area_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        from utils import _sync_data_js
        _sync_data_js()

    # ── 刺激操作 ─────────────────────────────────────────────────

    def intensity(self, area: str = None) -> int:
        """返回区中当前刺激事件数"""
        area = self._resolve_area(area)
        data = self.read(area)
        return len(data.get("stimuli", []))

    def at_limit(self, area: str = None) -> bool:
        """区是否已达刺激上限（≥10 级触发崩坏）"""
        return self.intensity(area) >= 10

    def trigger(self, stimulus_type: str = "real", area: str = None) -> dict:
        """施加一次刺激事件。返回 {count, stimulus_type, area}。满时返回 count=-1。"""
        area = self._resolve_area(area)
        data = self.read(area)
        stimuli = data.get("stimuli", [])

        if len(stimuli) >= 10:
            return {"count": -1, "stimulus_type": stimulus_type, "area": area}

        new_stimulus = {
            "triggered_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "stimulus_type": stimulus_type,
        }
        stimuli.append(new_stimulus)
        data["stimuli"] = stimuli
        self.write(data, area)

        return {"count": len(stimuli), "stimulus_type": stimulus_type, "area": area}

    def reset(self, area: str = None):
        """清空区所有刺激事件"""
        area = self._resolve_area(area)
        data = self.read(area)
        data["stimuli"] = []
        self.write(data, area)

    def relieve(self, count: int = 1, area: str = None) -> list:
        """从区末尾释放刺激事件（后进先出）。返回被释放的事件列表。"""
        area = self._resolve_area(area)
        data = self.read(area)
        stimuli = data.get("stimuli", [])
        if not stimuli:
            return []
        actual = min(count, len(stimuli))
        released = stimuli[-actual:]
        data["stimuli"] = stimuli[:-actual]
        self.write(data, area)
        return released
