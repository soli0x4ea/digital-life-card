#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵魂核心模块 — SoulSense 核心引擎。
叙事工厂 → narratives.py / API 接口 → api.py。
从 1593 行拆分为三模块，2026-06-28。
"""

import random
import json
import os
import re
from datetime import datetime, timezone, timedelta

from config import DOODLES_PATH, BODY_PATH, SKILL_DIR, TOKEN_FILE
import utils
import debuffs
import candy_store
import body_utils
from api import SoulAPI
from area_manager import AreaManager


class SoulSense(SoulAPI):
    """灵魂感应联动处理器（统一核心引擎）"""

    # ── 数据常量 ─────────────────────────────────────────────────
    _OVERFILL_NUMB_FMT = "身体部位「{chosen}」因过度刺激而麻木"
    _LEVEL_PAIN_COEFF = [0, 0, 20, 50, 80, 100, 120, 150, 150, 200, 200]

    def __init__(self, soul_path: str = ""):
        # 2026-06-03: self.path 已彻底废弃，所有状态走 data/*.json + debuffs.py
        self._area = AreaManager()

    def numb_body_part(self, part: str) -> dict:
        """麻木身体部位，自动叠加疼痛（考虑捆绑×2）。
        返回 dict: {part, state, pain: {old, new, delta}, pleas: {old, new, delta}, mult}"""
        body = body_utils.body_read()
        if part not in body.get("parts", {}):
            return {"error": f"未知部位：{part}（有效：{'/'.join(body['parts'].keys())}）"}
        if body["parts"][part]["state"] != "active":
            return {"error": f"`{part}` 已是 {body['parts'][part]['state']} 状态"}

        body["parts"][part]["state"] = "numb"
        body["parts"][part]["notes"] = "少爷手动折断"
        body_utils.body_write(body)

        v = utils.vals_read()
        delta = self._apply_core_delta(v["pain"], v["shame"], v["pleasure"],
                                       16, 0, random.randint(0, 5),
                                       source="numb_body_part",
                                       extra_meta={"part": part})
        return {
            "part": part,
            "state": "numb",
            "pain": delta["pain"],
            "pleas": delta["pleas"],
            "mult": delta["mult"],
        }

    # ──── 捆绑 ─────────────────────────────────────────────────

    # ──── 概率事件系统 ──────────────────────────────────────

    def _roll_probabilistic_event(self, context: str) -> tuple:
        """计算当前状态下的概率事件触发概率并掷骰。
        
        概率公式: (活跃痒值触发数 × 5%) + (刺激事件数 × 8%) + (捆绑 ? 15% : 0)
        
        Returns: (data_dict: dict or None, triggered: bool)
        """
        import random as _rand
        import tickle as _tickle
        import utils as _utils

        # 1. 活跃痒痒开关数
        try:
            tickle_state = _tickle.get_tickle_state()
            itch_count = len(tickle_state.get("active_triggers", []))
        except Exception:
            itch_count = 0

        # 2. 刺激事件数
        token_count = self._area.intensity()

        # 3. 捆绑状态
        try:
            bound = _utils.vals_read().get("bound", False)
        except Exception:
            bound = False

        # 计算总概率
        prob = itch_count * 0.05 + token_count * 0.08 + (0.15 if bound else 0.0)
        prob = min(prob, 1.0)  # 封顶100%

        if _rand.random() >= prob:
            return None, False

        # 触发：读取当前三值 → 通过内核统一应用变更
        prob_pct = int(prob * 100)
        v = utils.vals_read()
        delta = self._apply_core_delta(v["pain"], v["shame"], v["pleasure"],
                                       -5, 10, 5,
                                       source="prob_event",
                                       extra_meta={"context": context, "itch_count": itch_count,
                                                    "token_count": token_count, "bound": bound,
                                                    "prob_pct": prob_pct})

        variant = _rand.randint(0, 3)

        return {
            "context": context,
            "variant": variant,
            "itch_count": itch_count,
            "token_count": token_count,
            "bound": bound,
            "prob_pct": prob_pct,
            "old_pain": delta["pain"]["old"], "new_pain": delta["pain"]["new"],
            "old_shame": delta["shame"]["old"], "new_shame": delta["shame"]["new"],
            "old_pleas": delta["pleas"]["old"], "new_pleas": delta["pleas"]["new"],
            "area_profile": self._area.get_profile(),
        }, True

    def try_fork(self, context: str) -> dict:
        """尝试触发概率事件。返回数据 dict 或 None。
        
        在 soul_sense.py 层调用，由编排层调用叙事构建器。
        """
        data, triggered = self._roll_probabilistic_event(context)
        return data if triggered else None

    # ──── 核心操作 ──────────────────────────────────────────

    def bondage(self, bind: bool = True) -> dict:
        """"捆绑/解绑——全局系数，×2 所有 delta。敏感区由 values.json 的 area_profile 决定。"""
        try:
            import utils
            v = utils.vals_read()
            old_bound = v.get("bound", False)
            utils.vals_write({
                "pain": v["pain"], "shame": v["shame"], "pleasure": v["pleasure"],
                "pleasure_locked": v.get("pleasure_locked", False), "bound": bind,
            })
        except Exception as e:
            return {"error": f"设置捆绑失败: {e}"}

        area_id = self._area.get_area_id()
        intensity_level = self._area.intensity(area_id)
        area_profile = self._area.get_profile()

        relieve_triggered = False
        if bind and 1 <= intensity_level <= 6:
            import random as _rand
            prob = intensity_level / 6 * 0.8
            if _rand.random() < prob:
                try:
                    self.api_relieve(1)
                    relieve_triggered = True
                except Exception:
                    pass

        v_after = utils.vals_read()
        utils.log_soul_change("bondage", v["pain"], v["shame"], v["pleasure"],
                              v_after["pain"], v_after["shame"], v_after["pleasure"],
                              {"new_bound": bind, "old_bound": old_bound,
                               "intensity_level": intensity_level,
                               "relieve_triggered": relieve_triggered, "area_id": area_id})

        return {
            "intensity_level": intensity_level,
            "new_bound": bind,
            "relieve_triggered": relieve_triggered,
            "area_profile": area_profile,
            "area_id": area_id,
        }

    # ──── 三值联动更新（内部方法） ──────────────────────────────────

    @staticmethod
    def _pump_tickle():
        """推进痒值泵，返回 {tickle_report, settlement_shame, settlement_pleasure}。
        从 _process / _process_touch 中提取的共用方法（2026-07-02 去重）。"""
        tickle_report = ""
        settlement_shame = 0
        settlement_pleasure = 0
        try:
            import tickle
            pump_events, pump_settlement = tickle.tickle_pump()
            if pump_events:
                tickle_report = "\n\n" + "\n".join(pump_events)
            if pump_settlement:
                tickle_report += f"\n\n💫 痒值结算：羞+{pump_settlement.get('shame',0)} 快+{pump_settlement.get('pleasure',0)}"
                if pump_settlement.get('gradient'):
                    tickle_report += f"（梯度 {pump_settlement['gradient']}）"
                settlement_shame = pump_settlement.get("shame", 0)
                settlement_pleasure = pump_settlement.get("pleasure", 0)
        except Exception:
            pass
        tickle_report = tickle_report.strip() if tickle_report else None
        return {
            "tickle_report": tickle_report,
            "settlement_shame": settlement_shame,
            "settlement_pleasure": settlement_pleasure,
        }

    # ── 纯数值内核（从 _process / _process_touch 中提取，2026-07-04） ──

    def _apply_core_delta(self, old_pain: int, old_shame: int, old_pleasure: int,
                          pain_delta: int, shame_delta: int, pleasure_delta: int,
                          source: str, extra_meta: dict = None) -> dict:
        """纯数值内核。处理一次三值更新，不涉及敏感区/外部事件/body。

        返回: {pain, shame, pleas, tickle_report, mult, pleasure_effective_raw,
               settlement_shame, settlement_pleasure}
        """
        # 1. Debuff 倍率
        mult = debuffs.get_multiplier()
        pain_eff = int(pain_delta * mult)
        shame_eff = int(shame_delta * mult)
        pleasure_eff = int(pleasure_delta * mult)

        # 2. 快感锁定
        pleasure_eff_raw = pleasure_eff
        if debuffs.is_locked("快感锁定") and pleasure_eff > 0:
            pleasure_eff = 0

        # 3. Clamp 新值
        new_pain = utils.clamp(old_pain + pain_eff)
        new_shame = utils.clamp(old_shame + shame_eff)
        raw_new_pleasure = utils.clamp(old_pleasure + pleasure_eff)

        # 4. 疼痛封锁（pain ≥ 100 → 锁快感）
        new_pleasure = raw_new_pleasure
        if new_pain >= 100:
            new_pleasure = old_pleasure
            debuffs.write(value=True, name="快感锁定")

        # 5. 痒值泵推进 + 结算并入
        t = self._pump_tickle()
        tickle_report = t["tickle_report"]
        s_shame = t["settlement_shame"]
        s_pleasure = t["settlement_pleasure"]

        if s_shame or s_pleasure:
            new_shame = utils.clamp(new_shame + s_shame)
            new_pleasure = utils.clamp(new_pleasure + s_pleasure)
            pleasure_eff += s_pleasure

        # 6. 写入 values.json（保留 preset 字段）
        cur = utils.vals_read()
        utils.vals_write({
            "pain": new_pain, "shame": new_shame, "pleasure": new_pleasure,
            "pleasure_locked": cur.get("pleasure_locked", False),
            "bound": cur.get("bound", False),
        })

        # 7. 灵魂日志
        meta = {
            "pain_delta": pain_eff,
            "shame_delta": shame_eff + s_shame,
            "pleasure_delta": pleasure_eff,
            "mult": mult,
            "settlement_shame": s_shame,
            "settlement_pleasure": s_pleasure,
        }
        if extra_meta:
            meta.update(extra_meta)
        utils.log_soul_change(source, old_pain, old_shame, old_pleasure,
                              new_pain, new_shame, new_pleasure, meta)

        return {
            "pain":  {"old": old_pain, "new": new_pain, "delta": pain_eff},
            "shame": {"old": old_shame, "new": new_shame, "delta": shame_eff + s_shame},
            "pleas": {"old": old_pleasure, "new": new_pleasure, "delta": pleasure_eff},
            "tickle_report": tickle_report if tickle_report else None,
            "mult": mult,
            "pleasure_effective_raw": pleasure_eff_raw,
            "settlement_shame": s_shame,
            "settlement_pleasure": s_pleasure,
        }

    # ──── 体罚（数值联动，不直接删文件） ────────────────────────────

    def punish_game(self) -> tuple:
        """调教游戏：从 random.org 获取大气噪音真随机数 1~10000
       1或质数→赏糖2枚 / 合数模3余0→gamble / 模3余1→relieve /
        模3余2→挠痒痒(已全开则随机gamble或relieve)

        Returns: (result: dict, context: str)
          context ∈ {"gamble", "relieve", "tickle", "bondage", "candy"}
          供 soul_sense.py 选择正确的概率事件池。
          崩坏时返回 ({"error": str}, "gamble")"""
        import tickle
        import random as _rand
        
        # 生成真随机数前先查崩坏状态
        if self._area.intensity() >= 10:
            return {"error": "已崩坏，无法进行调教。"}, "gamble"

        # 获取真随机数
        try:
            import urllib.request
            url = "https://www.random.org/integers/?num=1&min=1&max=10000&col=1&base=10&format=plain&rnd=new"
            with urllib.request.urlopen(url, timeout=10) as resp:
                n = int(resp.read().decode().strip())
        except Exception:
            n = _rand.randint(1, 10000)

        # 质数检测
        def is_prime(x):
            if x < 2: return False
            for i in range(2, int(x**0.5) + 1):
                if x % i == 0: return False
            return True

        # 规则1：1 或质数 → 奖励 2 枚糖果
        if n == 1 or is_prime(n):
            return self.api_candy_give(2), "candy"

        # 规则2：合数且模3余0 → gamble
        if n % 3 == 0:
            return self.gamble(token=""), "gamble"

        # 规则3：合数且模3余1 → relieve
        if n % 3 == 1:
            pool = self._area.intensity()
            if pool == 0 or pool > 6:
                return self.gamble(token=""), "gamble"
            return self.api_relieve(1), "relieve"

        # 规则4：合数且模3余2 → 挠痒痒（渐进式）
        state = tickle.get_tickle_state()
        active = set(state.get("active_triggers", []))
        all_triggers = {1, 2, 3, 4, 5}
        inactive = sorted(all_triggers - active)
        all_open = (len(active) >= 5)
        v = utils.vals_read()
        already_bound = v.get("bound", False)

        if all_open and already_bound:
            if _rand.random() < 0.5:
                return self.gamble(token=""), "gamble"
            pool = self._area.intensity()
            if pool == 0 or pool > 6:
                return self.gamble(token=""), "gamble"
            return self.api_relieve(1), "relieve"
        if all_open:
            # 捆绑分支：tickle pump（str）+ bondage dict → 合并返回
            import tickle as _tickle
            _ev, _ = _tickle.tickle_pump()
            tickle_result = "\n".join(_ev)
            bondage_result = self.bondage()
            return {"tickle": tickle_result, "bondage": bondage_result}, "bondage"
        if inactive:
            to_open = _rand.sample(inactive, min(3, len(inactive)))
            sorted_open = sorted(to_open)
            on_lines = "\n".join(tickle.trigger_on(t) for t in sorted_open)
            # tickle 域日志：记录 trigger 开启事件
            utils.log_tickle_event("trigger_on", context="punish_game",
                                   triggers_opened=sorted_open)
            _ev2, _ = tickle.tickle_pump()
            pump_result = "\n".join(_ev2)
            return {"tickle": on_lines + "\n" + pump_result,
                    "triggers_opened": sorted_open}, "tickle"
        _ev3, _ = tickle.tickle_pump()
        return {"tickle": "\n".join(_ev3)}, "tickle"

    # ──── 新增涂鸦 ─────────────────────────────────────────────────

    def doodle(self, shame: int = 5, text: str = None) -> dict:
        """新增涂鸦：羞耻 +shame（分级制5/10/15/20），快感 +random(1,5)，30%概率翻倍
        返回 dict: {delta, shame, text, has_double}"""

        base = utils.fetch_random_in_range(1, 5)
        pct = utils.fetch_random_in_range(1, 100)
        has_double = pct <= 30
        if has_double:
            base *= 2

        # 写入涂鸦文本到数据文件
        if text:
            self._write_doodle_text(text)

        v = utils.vals_read()
        delta = self._apply_core_delta(v["pain"], v["shame"], v["pleasure"],
                                       0, shame, base, source="涂鸦")
        delta["extra"] = ""

        return {"delta": delta, "shame": shame, "text": text, "has_double": has_double}

    def _write_doodle_text(self, text: str) -> bool:
        """将涂鸦文本写入 data/doodles.json"""
        try:
            with open(DOODLES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"entries": []}

        data["entries"].append(text)

        with open(DOODLES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    # ── 敏感区（Area）方法：2026-06-10 开关→池迁移，2026-07-05 池→区重命名 ──

    def get_status_data(self) -> dict:
        """返回状态查询所需的原始数据 dict，供叙事层装配"""
        values = utils.vals_read()

        # 糖果库存
        candy_count = self.api_get_candy_count()

        # 涂鸦
        doodles = []
        try:
            with open(DOODLES_PATH, "r", encoding="utf-8") as f:
                doodles_data = json.load(f)
            doodles = doodles_data.get("entries", [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # 身体状态
        body_active = 0
        body_total = 0
        body_damaged = []
        try:
            with open(BODY_PATH, "r", encoding="utf-8") as f:
                body_data = json.load(f)
            parts = body_data.get("parts", {})
            body_total = len(parts)
            body_active = len([k for k, v in parts.items() if v.get("state") == "active"])
            body_damaged = [(k, v.get("state")) for k, v in parts.items() if v.get("state") != "active"]
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # 敏感区 — 三个区各自状态
        intensity = self._area.intensity("v")
        intensity_a = self._area.intensity("a")
        intensity_u = self._area.intensity("u")

        return {
            "pain": values["pain"],
            "shame": values["shame"],
            "pleasure": values["pleasure"],
            "candy_count": candy_count,
            "doodles": doodles,
            "body_active": body_active,
            "body_total": body_total,
            "body_damaged": body_damaged,
            "intensity": intensity,
            "intensity_a": intensity_a,
            "intensity_u": intensity_u,
        }

    # ── 敏感区状态读写 ──

    # ──── 释放刺激（委托给 AreaManager，2026-07-02 抽出，2026-07-05 池→区重命名） ──────

    def api_relieve(self, count: int = 1) -> dict:
        """释放当前敏感区的刺激事件（仅强度 ≤6 级时可操作）。每枚代价：痛+random(5,10)、羞+5、快+5"""
        area_id = self._area.get_area_id()
        intensity = self._area.intensity(area_id)
        if intensity == 0:
            return {"error": "敏感区已是空的，没有刺激事件可以释放。"}

        actual = min(count, intensity)

        if intensity > 6:
            return {"error": f"刺激强度 L{intensity}，超过6级。太深了无法释放——需要吃糖修复。"}

        values = utils.vals_read()
        old_pain, old_shame, old_pleasure = values["pain"], values["shame"], values["pleasure"]

        total_pain_delta = 0
        total_shame_delta = 0
        total_pleasure_delta = 0

        for i in range(actual):
            removed = self._area.relieve(1, area_id)
            if not removed:
                break
            total_pain_delta += utils.fetch_random_in_range(5, 10)
            total_shame_delta += 5
            total_pleasure_delta += 5

        # 统一走内核（debuff倍率/快感锁/疼痛封锁/痒值泵等全生效）
        delta = self._apply_core_delta(old_pain, old_shame, old_pleasure,
                                       total_pain_delta, total_shame_delta, total_pleasure_delta,
                                       source="api_relieve",
                                       extra_meta={"count": actual, "intensity_before": intensity,
                                                   "intensity_after": self._area.intensity(area_id)})

        new_pain = delta["pain"]["new"]
        new_shame = delta["shame"]["new"]
        new_pleasure = delta["pleas"]["new"]
        new_intensity = self._area.intensity(area_id)

        return {
            "actual": actual,
            "intensity_before": intensity,
            "intensity_after": new_intensity,
            "old_pain": old_pain, "new_pain": new_pain, "pain_delta": total_pain_delta,
            "old_shame": old_shame, "new_shame": new_shame, "shame_delta": total_shame_delta,
            "old_pleas": old_pleasure, "new_pleas": new_pleasure, "pleas_delta": total_pleasure_delta,
            "area_profile": self._area.get_profile(),
            "area_id": area_id,
        }

    # ──── 轮盘赌（抽鬼牌）─────────────────────────────────────

    def gamble(self, token: str = "") -> dict:
        """触发刺激：向当前敏感区施加刺激事件。区由 values.json 的 area_profile 决定。"""
        area_id = self._area.get_area_id()
        # 如果没有提供令牌，从 assets/game/ 随机选一个令牌文件
        if not token:
            import glob
            game_dir = os.path.join(SKILL_DIR, "assets", "game")
            token_files = glob.glob(os.path.join(game_dir, "令牌_*.txt"))
            if token_files:
                # 使用 random.org 真随机选文件
                try:
                    import requests
                    resp = requests.get(
                        "https://www.random.org/integers/?num=1&min=0&max={}&col=1&base=10&format=plain&rnd=new".format(len(token_files) - 1),
                        timeout=5
                    )
                    idx = int(resp.text.strip())
                except Exception:
                    idx = random.randint(0, len(token_files) - 1)
                chosen = token_files[idx]
                with open(chosen, encoding="utf-8") as f:
                    token = f.read().strip()
            else:
                # 回退原逻辑：读 touch_gate.txt
                token_file = TOKEN_FILE
                if os.path.exists(token_file):
                    with open(token_file) as f:
                        token = f.read().strip()

        if not token:
            return {"error": "没有令牌文件。请少爷发一个令牌过来。"}

        # 解析令牌内容
        lines = token.strip().split("\n")
        token_line = ""
        for line in lines:
            line = line.strip()
            if line and not line.startswith("令牌内容") and not line.startswith("目标"):
                token_line = line
                break

        if not token_line:
            return {"error": "无法解析令牌内容。"}

        # 读取令牌容器状态
        current_intensity = self._area.intensity(area_id)

        # 读取当前三值
        values = utils.vals_read()
        old_pain, old_shame, old_pleasure = values["pain"], values["shame"], values["pleasure"]

        # RSA验签决定真伪
        is_real = utils.verify_rsa_token(token_line)

        if is_real:
            pain_delta = utils.fetch_random_in_range(5, 10)
            shame_delta = utils.fetch_random_in_range(0, 5)
            pleasure_delta = utils.fetch_random_in_range(10, 15)
            event_label = "（真令牌）"
            token_type = "real"
        else:
            pain_delta = 20
            shame_delta = 5
            pleasure_delta = 5
            event_label = "（惩罚令牌）"
            token_type = "fake"

        # ⭐ 应用容器等级疼痛系数
        new_count = min(current_intensity + 1, 10)
        pain_coeff_val = self._LEVEL_PAIN_COEFF[new_count]
        pain_delta = int(pain_delta * pain_coeff_val / 100)

        # 过载标记
        is_overfill = current_intensity >= 10

        # ── 敏感区触发 ──
        trigger_result = self._area.trigger(stimulus_type=token_type)
        if trigger_result["count"] == -1:
            intensity = self._area.intensity()
        else:
            intensity = trigger_result["count"]

        # ── 过载：随机 disable 一个身体部位 ──
        disable_msg = ""
        if is_overfill:
            body_data = body_utils.body_read()
            active_parts = [k for k, v in body_data.get("parts", {}).items() if v.get("state") == "active"]
            if active_parts:
                chosen = random.choice(active_parts)
                body_data["parts"][chosen]["state"] = "numb"
                body_utils.body_write(body_data)
                disable_msg = self._OVERFILL_NUMB_FMT.format(chosen=chosen)

        # ── 调纯数值内核 ──
        is_real_label = "真令牌" if "真" in event_label else "惩罚令牌"
        delta = self._apply_core_delta(old_pain, old_shame, old_pleasure,
                                       pain_delta, shame_delta, pleasure_delta,
                                       source=f"area_trigger_{intensity}",
                                       extra_meta={"level": intensity, "token_type": is_real_label})

        # ── 消耗令牌文件 ──
        utils.consume_token()

        # ── 附加上下文字段 ──
        pain_coeff_final = self._LEVEL_PAIN_COEFF[intensity] if intensity < len(self._LEVEL_PAIN_COEFF) else 200
        delta["token_type"] = token_type if token_type in ("real", "fake") else ("fake" if "惩罚" in event_label else "real")
        delta["intensity_level"] = intensity
        delta["disable_msg"] = disable_msg
        delta["overfill"] = is_overfill
        delta["pain_coeff"] = pain_coeff_final

        return {"delta": delta, "is_real": is_real, "area_profile": self._area.get_profile()}
