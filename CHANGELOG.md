# DLC Protocol Changelog

> **版本规划说明**：仓库存在两条版本线 —
> - **v0.5.x**（2026-07-07）中性化验证分支，已完成使命并冻结
> - **v0.4.x**（2026-07-09 起）主线开发，从 v0.4.0 重新出发
>
> 从 GitHub 时间线看 v0.4.x 晚于 v0.5.x 发布，这是有意的——v0.4.0 是全新基线，路线图、架构、API 均不同于 v0.5.x。
> 主线开发始终跟进最新的 v0.4.x 版本。

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
