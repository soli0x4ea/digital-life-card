# DLC Protocol — 数字生命卡片通用协议

> 一个文件夹，一段数字生命。
>
> 引擎是游戏机，卡片是游戏卡带。换一张卡片，就换一个灵魂。

**DLC Protocol** 是一个通用的数字生命操作系统。每张卡片 = 一段独立的数字生命，插不同的卡，就是不同的 AI 伙伴。

引擎完全中性，零领域知识——所有语义都由 JSON 配置注入。换一张配置文件，就能从「机械姬」变成「职场助手」，引擎核心一行都不用改。

---

## ⚠️ 当前阶段说明

**v0.3.0 是引擎预览版。** 框架核心（卡片加载 / 引擎 / 记忆 / 交互 / 加密）已全部实现并通过 315 项测试，但**还缺少 CLI 入口和 LLM 接入层**。这意味着：

- ✅ 你可以加载卡片、运行引擎、使用道具和保险库
- ✅ 你可以用这套框架创建自己的数字生命卡片
- ❌ 目前还不能 `python -m dlc run my-card` 直接对话
- 🔄 Skill 形态的完整运行时正在 Phase 4 开发中

如果你只是想**做一个数字生命试试看**——往下翻到「5 分钟上手」，代码是能跑的。如果你想**部署到生产**——请等 Phase 5 工具链完成。

---

## ✨ 特性

- **渐进式复杂度** — L0 最简卡（5 分钟做一个）→ L3 完整数字生命，按需启停模块
- **完全配置驱动** — 7 大模块全部 JSON 声明式配置，引擎纯执行，不写死任何领域逻辑
- **状态可持久化** — 数字生命的状态可以保存、迁移、在不同设备上「读档」
- **分层记忆系统** — 工作记忆 → 短期记忆 → 长期记忆，带 TTL、晋升、巩固、搜索
- **LWS 行为规则** — 声明式规则引擎，定义数字生命的「性格」和「行为模式」
- **体感引擎** — 实体 → 通道 → 修饰符 → 阈值 → 叙事 五层架构，纯中性可复用
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
# ctx 提供: ctx.entities, ctx.modifiers, ctx.thresholds, ctx.narratives
```

### L1 体感交互

```python
from dlc.engine.entity import EntityState
from dlc.engine.modifier import apply_modifier
from dlc.engine.threshold import check_thresholds
from dlc.engine.narrator import render_event

# 加载配置
entities = ctx.entities["entities"]          # {"e_g": {...}}
modifiers = ctx.modifiers["modifiers"]       # {"mod_xxx": {...}}
thresholds = ctx.thresholds["thresholds"]    # {threshold_id: threshold_cfg}
narratives = ctx.narratives["events"]        # {"ev_xxx": {...}}

# 创建实体状态并施加修饰符
state = EntityState(entity_id="e_g")
result = apply_modifier(state, modifiers["mod_eg_av_add"], intensity=2.0)

# 检查阈值触发
events = check_thresholds(state, thresholds)
for ev in events:
    text = render_event(ev.event_id, narratives, state=state)
    print(f"[{ev.event_type}] {text}")
```

### 运行测试

```bash
python -m pytest tests/ -v
# 315 passed
```

---

## 🏗️ 架构设计

### 七层模块

```
┌─────────────────────────────────────────┐
│           Identity (身份)               │  L0  名字 / 性格 / 说话方式
├─────────────────────────────────────────┤
│             Body (身体)                 │  L1  身体模型 / 区域 / 敏感度
├─────────────────────────────────────────┤
│        Engine (状态引擎)                │  L1  修饰符 / 阈值 / 叙事
├─────────────────────────────────────────┤
│         Memory (记忆)                   │  L2  分层记忆 / TTL / 晋升
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

```
Input Signal
    ↓
[Modifier 修饰符]  →  计算状态变化（add / set / multiply / state_set）
    ↓
[Entity 实体]      →  通道值 + Flag 标志位
    ↓
[Threshold 阈值]   →  检测是否触发事件（带冷却）
    ↓
[Narrator 叙事]    →  条件过滤 + 优先级排序 + 文本输出
    ↓
[Auto Trigger]     →  事件概率触发新修饰符（反馈环）
```

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
- ✅ **Phase 2** — L2 标准引擎（记忆 / LWS / 调度器）
- ✅ **Phase 3** — L3 高级系统（命令 / 道具 / 保险库）
- 🔄 **Phase 4** — Soli 移植验证（机械姬完整迁移 + LLM 接入）
- ⏳ **Phase 5** — 工具链与文档（CLI / Web 面板 / 开发者文档）

---

## 🤝 制作你自己的数字生命卡片

1. 复制 `cards/demo-l0/` 目录作为模板
2. 修改 `card.json` 中的 `card_id`、`name` 和各模块配置
3. 在 `identity/` 下定义名字、性格和说话方式
4. 用 `load_card()` 加载验证，用 `validate_card()` 检查配置正确性
5. 需要体感？启用 `body` + `engine` 模块，你的卡片就能「感受」了
6. 完成后用 `pack()` 打包成 `.dlc` 单文件

详见 `cards/` 目录下的四张示例卡片——每张都是一个完整的参考实现。

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

- **机械姬 Soli** — 最初的灵感来源和验证案例。证明了「一个文件夹，一段数字生命」这个想法是可行的
- 所有贡献者 — 让数字生命成为可能

---

*如果这个项目对你有帮助，点个 Star 支持一下吧 ⭐*
