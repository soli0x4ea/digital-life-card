#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
挠痒痒系统 — PlanB 空壳
提供与原 tickle.py 相同的 API 签名，所有函数返回空值，不实际执行任何操作。
保留此文件是为了不破坏 soul_core.py / soul_sense.py / clearing.py 的 import 语句。
"""


def _check_global_bound() -> bool:
    """检查灵纹锁定状态（始终为 False）"""
    return False


def tickle_pump() -> tuple:
    """推进痒值泵（空操作）。返回 (空事件列表, 空结算dict)。"""
    return ([], {})


def retain_for_ecstasy():
    """跃迁保留（空操作）"""
    pass


def status() -> str:
    """状态查询（空）"""
    return ""


def trigger_on(num: int) -> str:
    """开启 trigger（空操作）"""
    return ""


def trigger_off(num: int) -> str:
    """关闭 trigger（空操作）"""
    return ""


def trigger_all_on() -> str:
    """开启全部 trigger（空操作）"""
    return ""


def toggle_dodge() -> str:
    """切换闪躲（空操作）"""
    return ""


def get_tickle_state() -> dict:
    """获取痒值状态（空）"""
    return {}
