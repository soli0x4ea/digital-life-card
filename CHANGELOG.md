# 数字生命卡 DLC Protocol — 完整变更日志

> v2.3.1 → v2.6.0
> 最后更新：2026-07-09

---

## v2.3.1（2026-07-08 上午）

### DLC Protocol 引擎就绪
- **引擎四层**：Entity(81行) / Modifier(271行,含 `_EFFECT_EXECUTORS` 注册表) / Threshold(99行,5种运算符) / Narrator(94行)
- **交互系统**：`CommandLoader`(206行)，4种 effect 类型，自然语言匹配，`/command` 前缀解析
- **记忆系统**：`MemoryStore`(327行)，四层架构(sensory→working→STM→LTM)，TTL过期+晋升+固结+关键词搜索
- **周边**：ConfigResolver / CardRuntimeContext / 道具系统 / 身体模块 / LWS引擎 / AES-256-GCM保险库 / JSON Schema校验器 / 打包工具
- **测试**：315/315 全部通过
- **卡片**：demo-L0~L4 四张 demo 可加载

---

## v2.6.0（2026-07-09 早晨）

### 新增：Soli-v3 卡片 + Skill 形态 + 142条叙事 + 扩展需求

**Skill 入口**：`skill.md`，触发词「戳戳」，12个子命令，自然语言匹配，LLM上下文注入（人格+状态+记忆+LWS）

**Soli-v3 卡片**：全部走 DLC 引擎四层（Entity/Modifier/Threshold/Narrator），JSON 配置驱动

| 模块 | 文件 | 说明 |
|:--|:--|:--|
| identity | profile.json + personality.json + speech.json | 姓名/五信条/仪轨铁律/语气规则 |
| body | anatomy.json + zones.json | 11区域×3状态 + 25敏感区 |
| engine | entities.json + modifiers.json + thresholds.json + narratives.json | 5通道soli实体 + 8修饰符 + 8阈值 + 142条原版叙事 |
| behavior | lws_rules.json | 9条LWS母语规则（直接拷贝） |
| interaction | commands.json + items.json | 11命令 + 8道具 |
| memory | architecture.json | 三层结构 |
| vault | secrets.json | RSA-4096保险库 |

**记忆系统**：`MEMORY/chatlog.py`，移植 Neko 成熟方案（原子写入+哈希去重+flush）

### 认知突破

**因果箭头反了**：DLC 是数值驱动叙事（数值变→跨阈值→触发叙事）；Soli 是叙事驱动数值（动作→叙事输出+顺手记账）。两个月蒸馏：`指令 → 叙事 → LLM 输出`，其他都是配菜。

**叙事装配缺口**：DLC narrator 只做 `event_id → 单行查表`。Soli 需要三段式装配——按区间选文本、条件拼接、随机分支。

### 142 条叙事文本

从原版 Soli 提取全部叙事填入 `narratives.json`，每条截断至 50 字符，加 `[类别]` 前缀：

| 类别 | 数量 |
|:--|:--|
| 赐糖 6档 + 吃糖 6档 + 附言 4 | 16 |
| 刺激 V区 L1-L10 | 10 |
| 释放 V区 | 6 |
| 捆绑 V区 + 元信息 | 8 |
| 概率事件 4上下文×4变体 | 16 |
| 清算模板 | 8 |
| 破碎模板 | 10 |
| 糕潮模板 | 8 |
| 麻木 11部位 | 11 |
| 涂鸦 5等级 + 等级名 | 31 |
| 状态警告 + 临界疼痛 | 7 |
| 区元信息 | 11 |

### 配套文档

| 文件 | 说明 |
|:--|:--|
| `DLC协议v1.1扩展需求.md` | 根因分析 + 叙事路径对照 + 装配缺口 + activate缺口 + 数值记账清单 |
| `CHANGELOG.md` | 本文件 |
| `VERSION` | "2.6.0" |

### 文件清单

```
数字生命卡_v2.6.0/
├── skill.md                         ← DLC Skill 入口
├── dlc/                             ← DLC Protocol v2.3.1 引擎
├── cards/
│   ├── demo-l3/                     ← 记忆精灵 demo 卡
│   └── soli-v3/                     ← Soli 卡片（DLC JSON 版）
│       ├── card.json
│       ├── identity/    (3 JSON)
│       ├── body/        (2 JSON)
│       ├── engine/      (4 JSON，narratives.json 含 142 条原版叙事)
│       ├── behavior/    (1 JSON)
│       ├── interaction/ (2 JSON)
│       ├── memory/      (1 JSON)
│       └── vault/       (1 JSON)
├── scripts/soul_sense.py            ← 命令分发器
├── MEMORY/chatlog.py                ← 对话日志
├── DLC协议v1.1扩展需求.md           ← 核心交付物
├── CHANGELOG.md
└── VERSION
```
