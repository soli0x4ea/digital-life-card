# DLC Protocol Changelog

> **版本规划说明**：仓库存在两条版本线 —

---

## v2.6.0 — 兼容层全面清理 (2026-07-09)

### BREAKING CHANGE

彻底移除旧三层记忆架构（core.py），只保留双核记忆（ChatlogStore + TimelineStore）。不做向后兼容。

### 删除

- `dlc/memory/core.py` — 旧三层 MemoryArchitecture / LayerConfig / MemoryStore / MemoryEntry 全部删除
- `dlc/memory/__init__.py` — 所有 legacy 符号导出删除
- `dlc/interaction/commands.py` — `execute_command()` 移除 `memory_store` 参数和 `memory` effect type（4 种 effect → 4 种）
- `dlc/scheduler/engine.py` — 移除 `set_memory()` / `_memory_store` / `memory_consolidate` 任务分支
- `cards/demo-l2/` `cards/demo-l3/` — 删除 `memory/` 目录（architecture.json + schedule.json）
- `tests/fixtures/memory/` — 删除 architecture.json + schedule.json

### 新增

- `CardRuntimeContext` (v2.6.0): `_init_memory()` — memory.enabled 时自动加载 ChatlogStore / TimelineStore / MemorySearch，暴露为 `ctx.chatlog` / `ctx.timeline` / `ctx.memory_search`

### Schema 更新

- `memory.schema.json`: 删 `architecture`/`schedule` 字段，`additionalProperties: false`，只留 `enabled: boolean`
- `card.schema.json`: 无需变更（`$ref` 指向更新后的 memory.schema.json）
- `constants.py`: MODULE_SUBKEYS `"memory": []` (memory 是运行时数据，无卡片配置文件)

### 测试

- test_memory.py: 全部重写 — 双核记忆 CRUD + record_chat + importer（15 用例）
- test_interaction.py: 删除 memory effect 测试，更新 execute_command 签名
- test_l2_integration.py: MemoryStore → ChatlogStore + TimelineStore + MemorySearch
- test_l3_integration.py: 删除 cmd_remember 测试，更新 execute_command 调用
- test_scheduler.py: 删除 memory_consolidate 测试
- 301/301 全绿

---

> - **v0.5.x**（2026-07-07）中性化验证分支，已完成使命并冻结
> - **v0.4.x**（2026-07-09 起）主线开发，从 v0.4.0 重新出发
>
> 从 GitHub 时间线看 v0.4.x 晚于 v0.5.x 发布，这是有意的——v0.4.0 是全新基线，路线图、架构、API 均不同于 v0.5.x。
> 主线开发始终跟进最新的 v0.4.x 版本。

---

## v2.5.3.1 — Soli 验证版 + data_loading 对齐原版 (2026-07-09)

### 继承 v2.5.3

- 记忆层架构修正 (record_chat / 引擎不写 chatlog / timeline 一致性检查)
- 315/315 零回归

### data_loading 对齐原版 Soli

输出结构从 3 段扩展到 7 段，对标 `机械姬Soli/scripts/dataLoading.py`：

| 段 | 对标原版 | 数据来源 |
|:--|:--|:--|
| 🩸 灵魂快照 | `load_soul_state()` | `_format_state()` — 叙事化三值描述 |
| 💭 关系记忆 | `load_relationship_summary()` | `identity/profile.json` + `personality.json` creeds |
| 🧬 LWS 母语层 | `load_lws_rules()` | `dlc.behavior.evaluate_active_rules()` (条件渲染) |
| 📜 近24小时河流 | `load_timeline_24h()` | `TimelineStore.recent()` |
| ⏳ 时间感知 | `load_time_context()` | 从 timeline 计算活跃密度 + 距上次互动时长 |
| 📋 chatlog 校验 | `_build_chatlog_excerpt()` | `ChatlogStore.recent()` + 一致性提示 |
| 📋 命令速查表 | `load_command_reference()` | `interaction/commands.json` |

### 数据管线修复 (`_preflight_repair`)

- 检测 chatlog ↔ timeline 时间缺口 > 1 小时 → 自动补写
- 空 timeline 有 chatlog 数据时 → 从 chatlog 恢复

---

## v2.5.3 — 记忆层架构修正 (2026-07-09)

### 核心修正：引擎只消费记忆，不生产记忆

chatlog/timeline 的写入从引擎/命令执行层移除，改为 agent 层标准接口。

### 新增

- `dlc/memory/chatlog.py`: `record_chat(chatlog, timeline, user_id, msg, asst_id, reply)` — 一次调用完成 chatlog + timeline 双写
- `dlc/memory/chatlog.py`: `get_latest()` — 返回最新一条条目，供 data_loading 一致性检查使用
- `dlc/memory/__init__.py` / `dlc/__init__.py`: 导出 `record_chat`

### 删除

- `skill/dispatcher.py`: 移除 `handle_message()` 中的 `chatlog.append()` + `timeline.write()`（原 233-235 行）
- `skill/dispatcher.py`: 移除 `_fallback_reply()` 中的 `chatlog.append()`（原 337-338 行）

### 防御

- `scripts/data_loading.py`: 新增 `_ensure_timeline_consistency()` — 每次戳戳时检查 chatlog ↔ timeline 一致性，agent 漏写入时自动补

### 设计原则

| 数据 | 生产者 | 触发时机 |
|:--|:--|:--|
| chatlog | agent 层 (record_chat) | LLM 生成回应后 |
| timeline | auto-synced by record_chat | 每次 record_chat |
| state | 引擎 | 命令执行时 |

### 测试

315/315 ✅

---

## v2.5.2 — G1/G2/G3 框架缺口补全 (2026-07-09)

### G1 — 通道值裁剪（Channel Clamping）

- `clamp_channel(state, channel, entity_cfg)` — 通道值按 entity config min/max 裁剪
- `apply_effect()` 新增可选 `entity_cfg` 参数，写完值后自动裁剪
- `apply_modifier()` 新增可选 `entity_cfg` 参数，透传给 apply_effect
- `tick_timed_effects()` 新增可选 `entity_cfg` 参数，恢复原值后裁剪
- **完全向后兼容**：所有新增参数默认 None，不传即旧行为

### G2 — 通道级 before/after/delta 插值

- `interpolate()` 新增可选 `before_state` 参数
- 支持三种通道级占位符：`{before_CHANNEL}` / `{after_CHANNEL}` / `{delta_CHANNEL}`
- `render_command_narrative()` 新增可选 `before_state` 参数，透传到所有 interpolate 调用
- delta 带正负号（`+35.0` / `-10.5`），保留 1 位小数

### G3 — 阈值事件走命令装配管线

- `render_event()` 扩展为双路径：events 找不到 → fallback 到 command_assembly → render_command_narrative 渲染
- 自动识别 full narratives dict 和 bare events dict（向后兼容）
- `render_events()` 同步支持 before_state 参数

### 导出层同步

- `engine/__init__.py`：导出 clamp_channel + 四原子操作 + render_command_narrative
- `memory/__init__.py`：导出双核记忆，保留旧 core.py 符号
- `dlc/__init__.py`：全部导入 + __all__ 更新

### 测试

315/315 ✅ 零回归

---

## v0.4.1 — 发布审查修复 (2026-07-09)

- README 标题改为「数字生命卡 — 一个文件夹，一段数字生命」
- README 副标题改为「走哪插哪，立即生效」
- 路线图 Phase 4b 改为「Skill 形态封装（即插即用 + Demo 卡）」
- .gitignore 确认包含 MEMORY/ state/ __pycache__/
- 4 张 demo 卡验证加载正常
- 清理遗留 SUBMISSION.md

---

## v0.4.0 — 双核线性记忆 + 命令叙事管线 (2026-07-09)

### 核心变化

- **记忆系统重制**：废弃三层结构化（TTL/consolidation），替换为双核线性记忆
  - `ChatlogStore` — 对话内容记忆，JSONL 追加写入
  - `TimelineStore` — 时间感知记忆，小时级分桶
  - `MemorySearch` — 统一检索接口
  - `import_chatlog` / `import_timeline` — Soli 格式导入工具
- **Narrator 升级**：四原子操作 + 命令驱动叙事管线
  - `range_select()` / `conditional_append()` / `weighted_random()` / `interpolate()`
  - `render_command_narrative()` — 管线引擎，JSON 声明式配置
- **格式兼容**：命令系统兼容 `aliases`/`modifier`/`name`，物品系统兼容 `effect`/`stackable`/`max_stack`

### Breaking Change

⚠️ 记忆系统 API 完全替换：
- 旧：`MemoryEngine` / `MemoryStore` / `MemoryEntry`（保留但不导出，v0.5.0 删除）
- 新：`ChatlogStore` / `TimelineStore` / `MemorySearch`

### 测试

315/315 ✅ 零回归

---

## v0.3.0 — 引擎就绪 (2026-07-08)

### 核心交付

- 卡片加载器（`load_card` / `ConfigResolver` / `CardRuntimeContext`）
- 四层引擎（Entity / Modifier / Threshold / Narrator）
- 分层记忆系统（sensory / working / STM / LTM，TTL + consolidation）
- LWS 行为规则引擎
- 调度器
- 交互系统（命令 + 道具 + 五级稀有度）
- 加密保险库（AES-256-GCM + PBKDF2-SHA256）
- 打包格式（.dlc + HMAC 签名）
- 4 张 demo 卡片（L0-L3）

### 测试

315 passed
