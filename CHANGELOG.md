# DLC Protocol Changelog

> 主线从 v2.5.0 开始。v0.x 系列为历史版本，已冻结。

---

## v3.0.8 — 去 Soli 化：清理所有专属命名残留 (2026-07-20)

### 修复

- **编号示例全面通用化**：`engine.py`/`assembly.py`/`server.py`/`README.md` 中所有 docstring/注释/示例
  - `action.gamble.3` → `action.act.3`，`boundary.ecstasy.v` → `boundary.timeout.a`
  - `threshold.pleasure_high` → `threshold.hp_low`
  - 命令示例 `"gamble"/"relieve"/"numb"` → `"act"/"move"/"use"`
  - 参数示例 `{"token": 1}` → `{"count": 2}`
- **`engine.py` 删除 Soli 死代码**：`_TRI_VALUES` / `_TRI_LABELS`（pain/shame/pleasure 三值，定义后从未使用）
- **`engine.py` `_threshold_id` 通用化**：移除硬编码的 `narr_ecstasy_/soul_break_/clearing_` 边界事件前缀，改为通用 `narr_` → `threshold.*` 映射
- **`engine.py` 参数提取通用化**：`params.get("token", 1)` → `params.get("count", 1)`

### 保留

- `CHANGELOG.md` 历史版本记录中的 Soli 命名（属于正常版本轨迹）

---

## v3.0.7 — Python 3.9 兼容 + 模板充实 (2026-07-20)

### 修复

- **Python 3.9 兼容**：9 个文件添加 `from __future__ import annotations`，`X | None` 语法在 3.9 上不再报错
- **模板充实**：`cards/_template/card.json` 含字段模板，`README.md` 含 3 步创建指南，子目录加 `.gitkeep`
- **版本声明**：`requirements.txt` 添加 `python>=3.10`

---

## v3.0.6 — 真正白板框架（清空参考卡片）(2026-07-20)

### 变更

- **删除全部 9 张参考卡片** — v3.0.5 携带的 demo-l0~l3 / detective-demo / frog-dissection-v1 / haiwang-v1 / tarot-v1 / walker-l1 全部移除。白板框架不应包含未经审核的第三方卡片数据
- **新增 `cards/_template/`** — 空卡片骨架（目录结构 + card.json），新建卡片时复制即可
- **SKILL.md 精简** — 移除参考卡片清单，替换为模板说明

### 框架大小

- 纯框架核心 `dlc/`：137KB / 3717 行 Python（不变）
- `cards/`：从 404KB → < 1KB（只剩空模板）
- 总计：~160KB

---

## v3.0.5 — 白板框架（移除 Soli 特定内容）(2026-07-20)

### 变更

- **删除 `cards/soli-v3/`** — 含大量 NSFW 内容和 Soli 专属记忆数据
- **SKILL.md 重写为通用框架指南** — 移除角色人格，改为卡片结构说明 + MCP 工具参考 + 编号规范
- **保留 9 张参考卡片** — demo-l0~l3 / detective-demo / frog-dissection-v1 / haiwang-v1 / tarot-v1 / walker-l1
- **框架代码不变** — `dlc/sm/` / `dlc/narrative/` / `dlc/engine/` 等全部保持

### 设计原则

每张卡片是独立的 skill 目录，内嵌 DLC 框架代码。框架不绑定任何角色——卡片结构 + 三模块引擎 + MCP 工具 = 通用骨架，人物由各卡片的 SKILL.md 和 engine 配置定义。

---

## v3.0.4 — Pipeline ops 全覆盖 + 无 level 回退 (2026-07-20)

### 修复

- **P2 `_resolve_pipeline` 补全 op**：新增 `rand`（加权随机）、`interp`（模板文本）、`cond`（if 数组）三种管道 op
  - `rand` 修复 tickle/relieve/numb/bound 叙事
  - `interp` 修复 punish_game 叙事
  - `cond` 修复 candy_eat 叙事
- **P2 无 level 命令回退**：新增 `_resolve_pipeline_no_level()`，action.ping/action.status 等无 level 命令取第一个可用文本
- **P2 CHANGELOG**：清理 v3.0.3 条目中的残留 v3.0.2 内容

### 命中率

51 个测试用例，49 HIT / 2 MISS（96%）。2 个 MISS 为 `action.ping`（无 legacy 叙事数据，设计上 ping 可以有也可以没有叙事）。

---

## v3.0.3 — 修复 _lookup_action 参数解析 + legacy 管道格式 (2026-07-20)

### 修复

- **P0 `_lookup_action` 参数解析**：支持 2 段（`action.gamble.3`）和 3 段（`action.gamble.v.3`）格式
- **P0 legacy 管道格式兼容**：新增 `_resolve_pipeline()`
- **P1 删除 server.py**：未接入 MCP
- **P1 legacy 事件 ID 映射**：threshold.xxx → narr_status_warn_xxx
- **P2 SKILL.md**：修正示例 + 清理

---

  - 旧 `command.`/`event.`/`emergence.` 格式全部兼容
  - 命中率 25%（v3.0.1）→ 100%（v3.0.2）
- **SKILL.md 示例修正**：`action.gamble.v.3` → `action.gamble.3`（匹配实际输出）

### 新增

- `dlc/narrative/server.py` — MCP 叙事外壳
  - 纯协议适配器：接收 MCP tool call → 调 assembly.py → 返回纯文本
  - 不包含叙事逻辑、不存储叙事数据、叙事资料仍在卡片本地 `narratives/`
  - 作用：纯 MCP 平台（无 shell 权限）也能调叙事组装
  - 与 `python assembly.py --ids "..."` stdout 效果完全一致
- SKILL.md 新增双模式说明：Python shell（沉浸感最高）+ MCP 壳子（平台兼容）

### 技术说明

`assemble_narrative` MCP 工具本质上就是 `subprocess.run(["python", "assembly.py", ...])` 的 MCP 封装。
叙事资料始终在卡片本地，不走网络、不搬上 MCP 服务端。MCP 壳子只是一个协议适配器，不包含「把叙事搬到服务端」的含义。

---


### 修复

- **P2 编号命名规范**：统一编号格式 `<domain>.<type>[.<variant>][.<level>]`
  - `command.cmd_ping` → `action.ping`（去 `cmd_` 前缀，域改为 action）
  - `command.cmd_gamble` → `action.gamble.3`（追加强度等级）
  - `event.narr_status_warn_pleasure_high` → `threshold.pleasure_high`（去 `narr_status_warn_` 前缀，域改为 threshold）
  - `event.narr_ecstasy_v` → `boundary.ecstasy.v`（边界事件分类，域改为 boundary）
- SKILL.md 更新编号示例

### 驳回

- **P1 叙事组装走 Python 脚本**：不予修改。叙事系统作为独立 Python 模块是正确的架构设计——它只是编号→文本的纯查表操作，不包含状态逻辑。是否包装为 MCP tool 是部署层决策，不影响架构正确性。每个卡片自包含 narratives/，Python 脚本保证自包含；MCP 包装反而会引入耦合。

---

## v3.0.0 — 三模块架构 (2026-07-20)

### BREAKING CHANGE

将 DLC 协议从单体内核重构为三模块架构。不做向后兼容。

### 新增

- `dlc/sm/engine.py` — v3.0 纯计算状态机（execute()→{narrative_ids, state_diff}，零 NL）
- `dlc/sm/server.py` — MCP Server 入口（execute/get_state/reset，stdio+HTTP）
- `dlc/narrative/assembly.py` — 叙事组装脚本（编号→查表→stdout），CLI 独立调用

### 删除（清理 v2.6 遗留）

- `dlc/engine/narrator.py` — NL 渲染器
- `dlc/vault.py` — 加密模块（cryptography 依赖）
- `dlc/body.py` / `dlc/identity.py` / `dlc/packager.py` — 未使用的模块
- `dlc/behavior/` / `dlc/scheduler/` — 行为规则/调度器
- `skill/` / `skill.py` / `scripts/` — v2.6 旧入口
- `cardforge/` / `tests/` — 编译器/测试（独立仓库维护）
- `MEMORY/` — 测试数据

### 保留（v3.0 引擎依赖）

- `dlc/engine/{entity,modifier,threshold}.py` — 纯计算层
- `dlc/{loader,validate,resolver,context,persistence}.py` — 基础层
- `dlc/interaction/commands.py` — 命令匹配+效果执行（narrator→stub）
- `dlc/memory/` — 双核记忆（ChatlogStore+TimelineStore，不走 MCP）

---

## 历史版本（v0.x 系列，已冻结）

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
