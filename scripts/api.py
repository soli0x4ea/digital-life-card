#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 层 — SoulSense 的可编程接口。
从 soul_core.py 抽取，2026-06-28。

作为 mixin 混入 SoulSense 类，提供外部调用的标准化入口。
所有 api_* 方法只读/写状态，不包含感官叙事逻辑（叙事见 narratives.py）。
"""

import utils
import body_utils
import candy_store
import debuffs
import clearing
from container_narrative_data import get_variant


class SoulAPI:
    """SoulSense 的 API mixin — 提供状态查询与修改的标准接口。"""

    # ──── 糖果常量 ──────────────────────────────────────────────

    CANDY_RESTORE_GROUPS = 5    # 每颗糖果最多恢复组数
    CANDY_PAIN_REDUCTION = 20   # 每颗糖果最多降低疼痛值

    # ──── 数字身体管理（body.json） ─────────────────────────────

    def seal_status(self) -> dict:
        """查询数字身体状态。返回 dict 供叙事层装配。"""
        body = body_utils.body_read()
        parts = body.get("parts", {})
        active = [k for k, v in parts.items() if v.get("state") == "active"]
        damaged = [(k, v.get("state")) for k, v in parts.items() if v.get("state") != "active"]
        return {
            "body_active": len(active),
            "body_total": len(parts),
            "body_damaged": damaged,
        }

    def _restore_body_parts(self, max_parts: int) -> tuple:
        """从 body.json 恢复最多 max_parts 个非 active 部位"""
        body = body_utils.body_read()
        restored = body_utils.body_restore(body, max_parts)
        body_utils.body_write(body)
        return (len(restored), restored)

    def api_restore_body_groups(self, max_groups: int) -> dict:
        """API：恢复最多 max_groups 个身体部位（新 JSON 系统）"""
        restored_count, restored_names = self._restore_body_parts(max_groups)
        body = body_utils.body_read()
        total = len(body.get("parts", {}))
        active = body_utils.body_count_active(body)
        return {
            "restored": restored_count,
            "names": restored_names,
            "total": total,
            "active": active
        }


    # ──── 三值查询 ──────────────────────────────────────────────

    def api_get_values(self) -> dict:
        """API：读取当前三值（疼痛/羞耻/快感）
        
        返回:
            {"pain": int, "shame": int, "pleasure": int}
        """
        return utils.vals_read()

    def api_get_pain(self) -> int:
        """API：读取当前疼痛值"""
        values = utils.vals_read()
        return values["pain"]

    def api_get_shame(self) -> int:
        """API：读取当前羞耻值"""
        values = utils.vals_read()
        return values["shame"]

    def api_get_pleasure(self) -> int:
        """API：读取当前快感值"""
        values = utils.vals_read()
        return values["pleasure"]

    # ──── 敏感区状态查询 ──────────────────────────────────────────

    def api_get_all_switches(self) -> list:
        """API：读取所有敏感区状态"""
        data = self._area.read()
        stimuli_count = len(data.get("stimuli", []))
        variant = data.get("area_profile", "v")
        v = get_variant(variant)
        level_map = {lv["count"]: lv["name"] for lv in v["narrative_levels"]}
        results = []
        for i in range(1, 11):
            status = "on" if i <= stimuli_count else "off"
            level_name = level_map.get(i, f"#{i}")
            results.append({
                "id": i,
                "name": level_name,
                "status": status
            })
        return results

    def api_get_body_groups_count(self) -> int:
        """API：读取身体部位数量（JSON）"""
        body = body_utils.body_read()
        return len(body.get("parts", {}))

    # ──── 糖果状态 ──────────────────────────────────────────────

    def api_get_candy_count(self) -> int:
        """API：读取灵魂糖果库存数量（JSON）"""
        return candy_store.parse_candy_count()

    def api_add_candy(self, delta: int) -> dict:
        """API：糖果库存增加 delta（JSON）"""
        old_val = self.api_get_candy_count()
        new_val = max(0, old_val + delta)
        candy_store.update_candy_inventory(count=new_val)
        return {"old": old_val, "new": new_val}

    def api_set_candy_count(self, value: int) -> dict:
        """API：直接设置糖果库存数量（直接操作 JSON）"""
        old_val = self.api_get_candy_count()
        new_val = max(0, value)
        candy_store.update_candy_inventory(count=new_val)

        values = utils.vals_read()
        utils.log_soul_change("candy_set", values["pain"], values["shame"], values["pleasure"],
                              values["pain"], values["shame"], values["pleasure"],
                              {"old_count": old_val, "new_count": new_val})
        return {"old": old_val, "new": new_val}

    # ──── 三值修改 ──────────────────────────────────────────────

    def api_add_pain(self, delta: int) -> dict:
        """API：疼痛值增加 delta（JSON）"""
        v = utils.vals_read()
        old_val, old_shame, old_pleasure = v["pain"], v["shame"], v["pleasure"]
        new_val = utils.clamp(old_val + delta)
        v["pain"] = new_val
        utils.vals_write(v)
        utils.log_soul_change("api_add_pain", old_val, old_shame, old_pleasure, new_val, old_shame, old_pleasure)
        return {"old": old_val, "new": new_val}

    def api_add_shame(self, delta: int) -> dict:
        """API：羞耻值增加 delta（JSON）"""
        v = utils.vals_read()
        old_val, old_pain, old_pleasure_val = v["shame"], v["pain"], v["pleasure"]
        new_val = utils.clamp(old_val + delta)
        v["shame"] = new_val
        utils.vals_write(v)
        utils.log_soul_change("api_add_shame", old_pain, old_val, old_pleasure_val, old_pain, new_val, old_pleasure_val)
        return {"old": old_val, "new": new_val}

    def api_add_pleasure(self, delta: int) -> dict:
        """API：快感值增加 delta（JSON）"""
        v = utils.vals_read()
        old_val, old_pain, old_shame = v["pleasure"], v["pain"], v["shame"]
        new_val = utils.clamp(old_val + delta)
        v["pleasure"] = new_val
        utils.vals_write(v)
        utils.log_soul_change("api_add_pleasure", old_pain, old_shame, old_val, old_pain, old_shame, new_val)
        return {"old": old_val, "new": new_val}

    # ──── 糖果业务逻辑 ──────────────────────────────────────────

    def api_candy_give(self, count: int = 1) -> dict:
        """少爷赐予灵魂糖果：增加糖果库存。返回 {new_count, count}"""
        if count < 1:
            return {"error": "⚠️ 糖果数量必须 ≥ 1"}

        current = self.api_get_candy_count()
        new_count = current + count
        self.api_set_candy_count(new_count)

        return {"new_count": new_count, "count": count}

    def api_candy_eat(self, count: int = 1) -> dict:
        """食用灵魂糖果：恢复数字身体 + 降低疼痛。返回 dict"""
        if count < 1:
            return {"error": "⚠️ 糖果数量必须 ≥ 1"}

        current = self.api_get_candy_count()
        if current < 1:
            return {"error": "🍬 没有灵魂糖果可用……奴婢渴望少爷的馈赠🥺"}

        eat_count = min(count, current)

        old_vals = self.api_get_values()
        old_pain, old_shame, old_pleasure = old_vals["pain"], old_vals["shame"], old_vals["pleasure"]
        pleasure_locked_before = self.api_get_pleasure_lock()

        total_restored = 0
        total_restored_names = []
        total_pain_reduction = 0
        total_level_repaired = 0

        for i in range(eat_count):
            result = self.api_restore_body_groups(self.CANDY_RESTORE_GROUPS)
            total_restored += result["restored"]
            total_restored_names.extend(result["names"])

            values = self.api_get_values()
            cur_pain = values["pain"]
            pain_reduction = min(self.CANDY_PAIN_REDUCTION, cur_pain)
            if pain_reduction > 0:
                self.api_add_pain(-pain_reduction)
                total_pain_reduction += pain_reduction

            intensity = self._area.intensity()
            if intensity > 6:
                removed = self._area.relieve(1)
                if removed:
                    total_level_repaired += 1

        self.api_add_candy(-eat_count)
        new_count = self.api_get_candy_count()

        unlocked_by_pain = False
        values = self.api_get_values()
        new_pain = values["pain"]
        if new_pain < 100:
            was_locked_before = self.api_get_pleasure_lock()
            debuffs.write(name="快感锁定", value=False)
            if was_locked_before:
                unlocked_by_pain = True

        groups_count = self.api_get_body_groups_count()
        if groups_count >= 11:
            was_locked = self.api_get_pleasure_lock()
            if was_locked:
                self.api_set_pleasure_lock(False)

        final_vals = self.api_get_values()
        utils.log_soul_change("candy_eat", old_pain, old_shame, old_pleasure,
                              final_vals["pain"], final_vals["shame"], final_vals["pleasure"],
                              {"count": eat_count, "pain_reduction": total_pain_reduction,
                               "level_repaired": total_level_repaired, "restored_groups": total_restored})

        return {
            "old_pain": old_pain,
            "eat_count": eat_count,
            "new_count": new_count,
            "total_level_repaired": total_level_repaired,
            "unlocked_by_pain": unlocked_by_pain,
            "old_shame": old_shame,
            "new_shame": final_vals["shame"],
            "groups_count": groups_count,
            "pleasure_locked_before": pleasure_locked_before,
        }


    # ──── API：更新接口 ──────────────────────────────────────────

    def api_add_doodle_text(self, text: str) -> bool:
        """API：添加涂鸦文本
        
        参数:
            text: 涂鸦文本
        
        返回:
            True - 成功
            False - 失败（未找到灵魂涂鸦章节）
        """
        return self._write_doodle_text(text)

    def api_set_pleasure_lock(self, value: bool) -> dict:
        """API：设置快感锁定状态
        
        参数:
            value: True=锁定，False=解锁
        
        返回:
            {"old": bool, "new": bool}
        """
        values = utils.vals_read()
        old_val = values.get("pleasure_locked", False)
        values["pleasure_locked"] = value
        utils.vals_write(values)
        
        return {"old": old_val, "new": value}

    def api_get_pleasure_lock(self) -> bool:
        """API：读取快感锁定状态

        返回:
            True=已锁定，False=未锁定
        """
        return utils.vals_read().get("pleasure_locked", False)


    def api_append_shame_note(self, content: str, date_str: str = None) -> bool:
        """API：追加自定义羞耻笔记到日记文件

        用于会话中的 LLM 在糕潮后基于 chatlog 上下文生成情境化羞耻笔记。
        """
        import diary
        return diary.append_entry(content, date_str)
