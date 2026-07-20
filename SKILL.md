---
name: DLC Protocol
description: "DLC Protocol v3.0 — 通用数字生命卡片框架。三模块架构：状态机（MCP）+ 叙事系统（知识库）+ 记忆系统（可选）。"
agent_created: true
---

## 概述

DLC（Digital Life Card）Protocol 是一套数字生命卡片框架。每张卡片是一个独立的人物/角色/互动系统，通过三模块架构驱动：

- **状态机** — 确定性计算，输入命令输出叙事编号
- **叙事系统** — 编号 → 知识库查表 → stdout 自然语言
- **记忆系统** — 可选，记录对话上下文（卡片按需配置厚度）

## 三模块架构

```
命令 ──→ 状态机 (MCP) ──→ 叙事编号 ──→ 叙事系统 (Python) ──→ stdout ──→ LLM ──→ 回应
                             [纯ID]          (知识库查表)      (自然语言)
```

| 模块 | 定位 | 何时调用 |
|:--|:--|:--|
| **状态机** | 确定性计算，输出叙事编号 | 每次命令时 |
| **叙事系统** | 编号 → 查表 → stdout 组装 | 拿到编号后 |
| **记忆系统** | 记录 + 注入上下文（可选） | 启动/恢复会话时 |

## MCP 工具

框架暴露 3 个标准 MCP 工具：

| 工具 | 输入 | 输出 | 说明 |
|:--|:--|:--|:--|
| `execute` | `command: string, params?: object` | `{narrative_ids, state_diff, flags}` | 执行命令 |
| `get_state` | 无 | `{card_id, entities}` | 状态快照 |
| `reset` | 无 | `{status}` | 重置状态 |

**关键规则**：
1. `execute` 返回的是叙事编号（如 `["action.move.2", "threshold.health_low"]`），不是自然语言
2. 拿到编号后调用叙事组装：
   ```bash
   python dlc/narrative/assembly.py --card cards/<card-id> --ids "action.move.2,threshold.health_low"
   ```
3. 组装后的 stdout 是自然语言剧本，LLM 以角色身份演绎

## 卡片结构

每张卡片是一个自包含目录：

```
cards/<card-id>/
├── card.json              ← 卡片元数据（id/name/version/level）
├── engine/                ← 状态机配置
│   ├── entities.json      ←   实体 & 通道定义
│   ├── modifiers.json     ←   修饰符 & 效果
│   ├── thresholds.json    ←   阈值 & 触发规则
│   └── narratives.json    ←   叙事数据（兼容 v2.6 格式）
├── interaction/           ← 交互定义
│   ├── commands.json      ←   命令列表（id/triggers/effects）
│   └── items.json         ←   道具定义
├── identity/              ← 人格（可选）
│   ├── profile.json
│   └── personality.json
├── body/                  ← 身体模型（可选）
│   └── anatomy.json
├── behavior/              ← 行为规则（可选）
│   └── lws_rules.json
├── narratives/            ← v3.0 叙事模板（可选，不提供则回退 engine/narratives.json）
│   └── templates/
├── state/                 ← 运行时状态（持久化）
└── MEMORY/                ← 记忆系统（可选，卡片按需配置厚度）
```

## 叙事编号规范

v3.0 使用分层点分编号：

| 域 | 格式 | 示例 |
|:--|:--|:--|
| `action` | `{cmd_id}.{level}` | `action.move.2` |
| `threshold` | `{event_id}` | `threshold.health_low` |
| `boundary` | `{event_id}.{variant}` | `boundary.death.v` |
| `emergence` | `{type}` | `emergence.default` |
| `system` | `{subtype}` | `system.status` |

## 卡片模板

`cards/_template/` 提供了一个空卡片骨架，新建卡片时复制即可。框架本身不包含任何实际卡片数据。
