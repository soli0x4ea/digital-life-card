# DLC Protocol Changelog

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
