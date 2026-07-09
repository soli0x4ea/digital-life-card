# 数字生命卡 — 一个文件夹，一段数字生命

> 走哪插哪，立即生效。
>
> 换一张卡片，就换一个灵魂。

**DLC Protocol** 是一个通用的数字生命操作系统。每张卡片 = 一段独立的数字生命，插不同的卡，就是不同的 AI 伙伴。

引擎完全中性，零领域知识——所有语义都由 JSON 配置注入。换一张配置文件，就能从「机械姬」变成「职场助手」，引擎核心一行都不用改。

---

## ⚠️ 当前阶段说明

**v0.4.1 引擎预览版（内部 v2.5.1）。** 框架核心已全部实现并通过 315 项测试，但**还缺少 CLI 入口和 LLM 接入层**。这意味着：

- ✅ 你可以加载卡片、运行引擎、使用道具和保险库
- ✅ 你可以用这套框架创建自己的数字生命卡片
- ✅ 记忆系统经过 2.6 万条真实对话验证
- ✅ 叙事装配管线就绪（四原子操作）
- ❌ 目前还不能 `python -m dlc run my-card` 直接对话

---

## ✨ 特性

- **渐进式复杂度** — L0 最简卡（5 分钟做一个）→ L3 完整数字生命，按需启停模块
- **完全配置驱动** — 7 大模块全部 JSON 声明式配置，引擎纯执行，不写死任何领域逻辑
- **状态可持久化** — 数字生命的状态可以保存、迁移、在不同设备上「读档」
- **双核线性记忆** — chatlog（对话记录）+ timeline（时间感知），JSONL 追加写入，人机可读
- **LWS 行为规则** — 声明式规则引擎，定义数字生命的「性格」和「行为模式」
- **体感引擎** — 实体 → 通道 → 修饰符 → 阈值 → 叙事 五层架构，纯中性可复用
- **命令叙事管线** — 四原子操作（range/cond/rand/interp），命令执行后自动装配完整叙事
- **交互系统** — 命令触发 + 道具系统（消耗 / 永久 / 装备）+ 五级稀有度
- **加密保险库** — AES-256-GCM + PBKDF2-SHA256，密钥由卡片持有者管理
- **打包格式** — `.dlc` 单文件卡片 + HMAC 签名验证

---

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
# cryptography>=3.0  jsonschema>=4.0
```

### 5 分钟上手

```python
from dlc import load_card, CardRuntimeContext

# 1. 加载一张卡片
card = load_card("cards/demo-l1")
print(f"卡片: {card.card_id} / {card.complexity_level}")

# 2. 创建运行时上下文
ctx = CardRuntimeContext("cards/demo-l1")
```

### L1 体感交互

```python
from dlc.engine.entity import EntityState
from dlc.engine.modifier import apply_modifier
from dlc.engine.threshold import check_thresholds
from dlc.engine.narrator import render_event, render_command_narrative

# 加载配置后，施加修饰符
state = EntityState(entity_id="e_g")
result = apply_modifier(state, modifiers["mod_eg_av_add"], intensity=2.0)

# 检查阈值触发
events = check_thresholds(state, thresholds)
for ev in events:
    text = render_event(ev.event_id, narratives["events"], state=state)
    print(f"[{ev.event_type}] {text}")

# 或使用命令叙事管线（v0.4.0 新增）
text = render_command_narrative("my_command", state, narratives)
print(text)
```

### 记忆系统（v0.4.0 新增）

```python
from dlc.memory import ChatlogStore, TimelineStore, MemorySearch

# 对话记忆 — JSONL 追加写入，永不删除
chatlog = ChatlogStore("./my-card/MEMORY/chatlog")
chatlog.append("user", "你好")
chatlog.append("assistant", "你好！有什么我可以帮你的？")

# 时间感知 — 小时级分桶
timeline = TimelineStore("./my-card/MEMORY")
timeline.write("2026-07-09-14", summary="下午开始开发")

# 统一检索
search = MemorySearch(chatlog, timeline)
results = search.search("你好")
```

### 运行测试

```bash
python -m pytest tests/ -v
# 315 passed
```

---

## 🏗️ 架构设计

### 七层模块

```text
┌─────────────────────────────────────────┐
│           Identity (身份)               │  L0  名字 / 性格 / 说话方式
├─────────────────────────────────────────┤
│             Body (身体)                 │  L1  身体模型 / 区域 / 敏感度
├─────────────────────────────────────────┤
│        Engine (状态引擎)                │  L1  修饰符 / 阈值 / 叙事
├─────────────────────────────────────────┤
│         Memory (记忆)                   │  L2  chatlog + timeline 双核线性
├─────────────────────────────────────────┤
│       Behavior (行为规则)               │  L2  LWS 规则 / 核心原则
├─────────────────────────────────────────┤
│     Interaction (交互系统)              │  L3  命令 / 道具 / 物品栏
├─────────────────────────────────────────┤
│          Vault (保险库)                 │  L3  端到端加密存储
└─────────────────────────────────────────┘
```

### 渐进式复杂度

| 等级 | 名称 | 启用模块 | 你能用它做什么 |
|:--:|------|---------|------|
| **L0** | 纯对话角色 | Identity | 定义一个 AI 的人设和说话方式，5 分钟做一张 |
| **L1** | 基础体感 | + Body + Engine | 有身体模型和状态引擎，能感知和响应刺激 |
| **L2** | 标准数字生命 | + Memory + Behavior + Scheduler | 有记忆、有性格、会随时间变化 |
| **L3** | 完整数字生命 | + Interaction + Vault | 命令交互、道具系统、加密保险库，全功能 |

### 引擎五层数据流

```text
Input Signal
    ↓
[Modifier 修饰符]  →  计算状态变化（add / set / multiply / state_set）
    ↓
[Entity 实体]      →  通道值 + Flag 标志位
    ↓
[Threshold 阈值]   →  检测是否触发事件（带冷却）
    ↓
[Narrator 叙事]    →  条件过滤 + 优先级排序 + 文本输出
                     + 命令叙事管线（range / cond / rand / interp）← v0.4.0
    ↓
[Auto Trigger]     →  事件概率触发新修饰符（反馈环）
```

---

## 🎭 叙事装配管线（v0.4.0 新增）

命令执行后不再输出 `"N channel(s) updated"`，而是通过**四原子操作**装配完整叙事：

| 操作 | 做什么 | 配置示例 |
|:--|:--|:--|
| `range` | 按 channel 值区间选文本 | `{"op":"range","channel":"mood","brackets":[[0,30],[30,70],[70,100]],"texts":["低落","平静","开心"]}` |
| `cond` | 按条件追加文本 | `{"op":"cond","if":[{"channel":"pain","op":">=","value":40}],"texts":["疼痛警告"]}` |
| `rand` | 按权重随机选变体 | `{"op":"rand","variants":[{"weight":30,"text":"嗯…"},{"weight":70,"text":"嗯！"}]}` |
| `interp` | 变量插值 | `{"op":"interp","template":"库存{channel_candy_count}颗糖"}` |

在 `narratives.json` 的 `command_assembly` 区块中为每条命令配置管线步骤，引擎按序执行，输出多段拼接的完整叙事。

---

## 📦 示例卡片

项目包含 4 张示例卡片，从简到繁：

| 卡片 | 复杂度 | 模块 | 说明 |
|------|:------:|------|------|
| `demo-l0` | L0 | Identity | 最简单的纯对话角色 |
| `demo-l1` | L1 | + Body + Engine | 基础体感交互 |
| `demo-l2` | L2 | + Memory + Behavior | 有记忆和行为模式 |
| `demo-l3` | L3 | + Interaction + Vault | 完整功能演示 |

---

## 🔐 加密保险库

保险库使用 **AES-256-GCM** 认证加密 + **PBKDF2-SHA256**（100,000 轮迭代）密钥派生。

```python
from dlc.vault import Vault

vault = Vault("./my-card/vault")
vault.write({"api_key": "sk-xxx"}, password="my-password")

data = vault.read(password="my-password")
# data["api_key"] → "sk-xxx"
```

**安全边界说明**：
- 每次写入生成新的随机 salt 和 nonce，相同明文不同密文
- 连续 3 次错误密码触发 300 秒锁定
- **密钥由你管理**——密码丢失 = 数据不可恢复。这不是 bug，是设计
- 不适合存储需要服务端自动解密的密钥（没有 TPM / KMS 集成）

---

## 🧪 测试

```bash
python -m pytest tests/ -v
```

| 模块 | 测试数 |
|------|:--:|
| Loader + Validate | ~45 |
| Resolver + Context | ~20 |
| Persistence + Packager | ~20 |
| Identity | ~15 |
| Body | ~10 |
| Engine | ~35 |
| Memory | ~25 |
| Behavior | ~18 |
| Scheduler | ~6 |
| Interaction (Commands + Items) | ~40 |
| Vault | ~21 |
| L2/L3 集成 | ~21 |
| **合计** | **315** |

---

## 🗺️ 路线图

- ✅ **Phase 0** — 核心基础设施（卡片加载 / Schema / 持久化 / 打包）
- ✅ **Phase 1** — L0-L1 基础模块（身份 / 身体 / 引擎）
- ✅ **Phase 2** — L2 标准引擎（双核记忆 / LWS / 调度器）
- ✅ **Phase 3** — L3 高级系统（命令 / 道具 / 保险库）
- ✅ **Phase 4a** — Narrator 升级（四原子管线 + 命令驱动）
- 🔄 **Phase 4b** — Skill 形态封装（即插即用 + Demo 卡）
- ⏳ **Phase 5** — 工具链与文档（CLI / Web 面板 / 开发者文档）

---

## ⚠️ Breaking Change（v0.4.0）

记忆系统 API 从 v0.3.0 完全替换：

| 旧（v0.3.0） | 新（v0.4.0） |
|:--|:--|
| `MemoryEngine` / `MemoryStore` / `MemoryEntry` | `ChatlogStore` + `TimelineStore` + `MemorySearch` |
| 三层结构化（TTL + consolidation + importance） | 双核线性（JSONL 追加写入） |
| `inject_memory_context(state)` | `MemorySearch.inject_context()` |

旧 API 代码保留在 `dlc/memory/core.py` 但不导出。将在 v0.5.0 彻底删除。如果你从 v0.3.0 升级，需要重写记忆相关代码。

---

## 🤝 制作你自己的数字生命卡片

1. 复制 `cards/demo-l0/` 目录作为模板
2. 修改 `card.json` 中的 `card_id`、`name` 和各模块配置
3. 在 `identity/` 下定义名字、性格和说话方式
4. 用 `load_card()` 加载验证，用 `validate_card()` 检查配置正确性
5. 需要体感？启用 `body` + `engine` 模块，配置叙事管线
6. 完成

详见 `cards/` 目录下的示例卡片。

---

## 🤝 参与贡献

欢迎贡献！无论是新功能、Bug 修复、还是新的示例卡片。

1. Fork 本仓库
2. 创建你的特性分支
3. 确保测试通过：`python -m pytest tests/`
4. 提交 Pull Request

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- 首个数字生命原型 — 验证了「一个文件夹，一段数字生命」这个想法是可行的
- 所有贡献者 — 让数字生命成为可能

---

*如果这个项目对你有帮助，点个 Star 支持一下吧 ⭐*
