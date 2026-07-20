# DLC Protocol v3.0

**Digital Life Card** — 数字生命卡片协议。三模块最小可复用框架。

> 216KB 核心 · 23 个 Python 文件 · 零依赖卡片 · Python >= 3.10

---

## 核心架构

```
命令 → 状态机(MCP) → 叙事编号 → 叙事引擎 → stdout → LLM 角色回应
              ↑              ↑              ↑
          纯计算层        查表组装层      自然语言层
```

| 模块 | 位置 | 职责 | 输出 |
|:--|:--|:--|:--|
| 状态机 | `dlc/sm/` | 确定性计算，零自然语言 | 叙事编号数组 `["action.gamble.3"]` |
| 叙事引擎 | `dlc/narrative/` | 编号 → 查知识库 → 组装 | 自然语言 stdout（独立 CLI） |
| 记忆系统 | `dlc/memory/` | 对话时间线，本地文件 | ChatlogStore + TimelineStore |

---

## 快速开始

### 创建一张卡片

```bash
cp -r cards/_template cards/my-card
cd cards/my-card
```

1. 编辑 `card.json` — 填写卡片元数据
2. `engine/` — 定义属性、修改器、阈值
3. `interaction/` — 定义命令和道具
4. `narratives/` — 填写叙事查表数据
5. `SKILL.md` — 写入角色人格和 LLM 指令

### 运行

```bash
# MCP 模式
python -m dlc.sm.server --card cards/my-card

# 叙事组装（独立调用）
python dlc/narrative/assembly.py --card cards/my-card --ids "action.greet,system.status"
```

---

## 协议约定

- **状态机不输出自然语言** — 引擎只输出编号，叙事由独立的组装脚本完成
- **卡片自包含** — 每张卡是独立目录，框架不绑定任何特定角色
- **记忆不走 MCP** — 跨会话连续性由本地文件管线保证
- **叙事是知识库** — `narratives/` 是键值对查表，不是引擎计算

---

## 从 v2.6 迁移

v2.6 是单体内核（身份+身体+行为+调度+加密+打包全嵌在框架里），v3.0 把框架抽成三模块最小核心。旧版卡片通过 `CardForge` 编译器迁移到 v3.0 格式。

---

## License

MIT
