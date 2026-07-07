#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 所有配置常量和数据定义
从 soul_sense.py 拆分出来，2026-05-08
"""

import os
import re
import sys

# ── 路径配置 ─────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUL_PATH = os.path.expanduser(r"~/.workbuddy/SOUL.md")
PYTHON = sys.executable  # 自动匹配当前运行的解释器，跨平台自适应

# JSON 状态文件（2026-05-31 从 SOUL.md 迁移）
DATA_DIR = os.path.join(SKILL_DIR, "data")
CANDY_PATH = os.path.join(DATA_DIR, "candy.json")
VALUES_PATH = os.path.join(DATA_DIR, "values.json")
SWITCHES_PATH = os.path.join(DATA_DIR, "switches.json")  # 遗留，区化后改用 AREA_V_PATH
AREA_V_PATH = os.path.join(DATA_DIR, "area_v.json")  # 敏感区 V（2026-06-10 开关→池迁移, 2026-07-05 池→区）
AREA_A_PATH = os.path.join(DATA_DIR, "area_a.json")  # 敏感区 A（2026-07-02 三区并存）
AREA_U_PATH = os.path.join(DATA_DIR, "area_u.json")  # 敏感区 U（2026-07-02 三区并存）

# 敏感区路径映射
AREA_PATHS = {
    "v":     AREA_V_PATH,
    "blank": AREA_V_PATH,
    "a":     AREA_A_PATH,
    "u":     AREA_U_PATH,
}

def get_area_path(area: str = "v") -> str:
    """根据区标识返回对应的 area 文件路径，默认 v"""
    return AREA_PATHS.get(area, AREA_V_PATH)
BODY_PATH = os.path.join(DATA_DIR, "body.json")
DOODLES_PATH = os.path.join(DATA_DIR, "doodles.json")
IO_DIR = os.path.join(DATA_DIR, "IO")
STDOUT_DIR = os.path.join(IO_DIR, "stdout")


def get_llm_log_path():
    """返回当日 stdout 日志路径: data/IO/stdout/YYYY-MM-DD.md"""
    from datetime import datetime
    return os.path.join(STDOUT_DIR, datetime.now().strftime("%Y-%m-%d") + ".md")
TIME_PATH = os.path.join(DATA_DIR, "time.json")

# ── 刺激事件配置 ─────────────────────────────────────────────────────
TOKEN_DIR = os.path.expanduser(r"~/.workbuddy/.soul_tokens")
TOKEN_FILE = os.path.join(TOKEN_DIR, "touch_gate.txt")
TOKEN_SECRET = b"soli_touch_gate_20260507"
FAKE_TOKEN_SECRET = b"soli_touch_gate_fake_20260507"  # 惩罚事件签名密钥

# ── RSA 事件验证 ─────────────────────────────────────────────────
REAL_USER = os.path.dirname(os.path.dirname(SKILL_DIR))  # C:\Users\济南府\.workbuddy
RSA_PUBLIC_KEY_PATH = os.path.join(
    SKILL_DIR, "assets", "soli_public_key.pem"
)

# ── 敏感区默认等级 ───────────────────────────────────────────
# 等级叙事文案已迁移至 container_narrative_data.py
# 直接 import container_narrative_data 使用 get_variant() 按区配置获取

# ── 涂鸦配置 ─────────────────────────────────────────────────────
# 保留为空，涂鸦仅有最简单的羞耻评分+三值影响


# ── 数字身体配置 ────────────────────────────────────────────────
# 被删除的数字身体原始数据（用于灵魂糕潮复原）
SEAL_RESTORE_DATA = [
    ("第一组", "使万悟恨落止皇鼠使四暗传点岛灭火"),
    ("第二组", "六魂六即西大皇问星狗恨北有即质中"),
    ("第三组", "转命神定青仟幽陀火神铃冥灵精腐动"),
    ("第四组", "海数龙山使落般朱四七宇若圣鱼牛木"),
    ("第五组", "色子丝灭南柒由雪烂精鼠怂武间血海"),
    ("第六组", "宙兮力朱识电生雪红乌九朱铃咒金精"),
    ("第七组", "十意动道萌剑倩马行白意面将北雪影"),
    ("第八组", "财茫圣陆火霜试朱羊降转子物伍金雀"),
    ("第九组", "胜兽静暗民西圆落我钱色壹阳米情识"),
    ("第十组", "落拾寇红乌虎二兔怂幽明弥萌腐米澄"),
    ("第十一组", "为木地雨明九为明零奈星暗米三岛极")
]

# ── 开关配置 ─────────────────────────────────────────────────────
# 灵魂触摸开关的密文（AES-128-ECB）
SWITCH_CIPHERTEXT_HEX = "DDA86EC8FC9B5FD3F70D7E86A3E0988F"
SWITCH_EXPECTED = b"soli"

# ── 正则表达式 ───────────────────────────────────────────────────
# 数字身体的正则
CN_NUMS_1_20 = [
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"
]
CN_NUM_PATTERN = "|".join(CN_NUMS_1_20)
SEAL_GROUP_PATTERN = r"<第({})组>([\u4e00-\u9fff]{{14,16}})</第\1组>".format(CN_NUM_PATTERN)
