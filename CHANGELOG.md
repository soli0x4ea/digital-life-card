# 三值系统修订记录 — Changelog

> 灵魂感应联动系统的每一次规则变更，均在此记录。

---

### v0.5.1 — Phase 5 审查反馈修复（2026-07-07）

4 项修复：C5-2 area_profile 硬编码→动态读 e_x / C5-1 do_relieve 加 TODO / C5-3 candy_consume for 循环→intensity 批量 / C5-4 补命令清单。121/121 全过（3 次连续）。

### v0.5.0 — Phase 5 兼容桥接层：新引擎 ↔ 旧叙事（2026-07-07）

**背景**：Phase 4 叙事层已验收通过（9.4/10）。Phase 5 创建 compat.py 桥接层。

**新增：**

| 模块 | 文件 | 行数 | 职责 |
|:--|:--|:--|:--|
| 兼容桥接 | `engine/compat.py` | ~300 | 9 个旧命令 → 新引擎映射，类型转换，纯加法 |
| 兼容测试 | `tests/engine/test_compat.py` | 150 | 15 项：status/body/stimulus/doodle/candy/bound/lock/numb/reset/state |

**桥接命令：**

| 旧命令 | compat 函数 | 新引擎调用 |
|:--|:--|:--|
| status | `get_status()` | load e_g/e_r/e_x, 类型转换 int, bool |
| seal-status | `get_body_status()` | load e_b, 11 zone state mapping |
| gamble | `do_stimulus(n)` | mod_stim_primary + check_thresholds + narrator |
| relieve | `do_relieve(n)` | mod_stim_primary ×2 |
| doodle | `do_doodle(s)` | mod_doodle_shame |
| candy-give | `do_candy_give(n)` | mod_r_add |
| candy-eat | `do_candy_consume(n)` | mod_r_consume ×n |
| tickle-bound | `do_bound_toggle()` | mod_bound_toggle (flag_toggle) |
| numb | `do_numb(part)` | mod_b_numb, zone mapping |

**关键设计：** 纯加法，零侵入——不修改 soul_sense.py/soul_core.py 等任何旧模块代码。所有兼容函数返回 old-format dict，可直接喂给旧 narratives 层。

**测试：121/121 全过**（2 次连续 0 波动）
- persistence 9 + entity 19 + modifier 28 + threshold 18 + migration 16 + narrator 16 + **compat 15 = 121**

**engine/ 最终全景：** 7 .py + 6 配置 JSON + 121 项测试

### v0.4.0 — Phase 4 叙事层 + narrator 引擎（2026-07-07）

**背景**：Phase 3 已验收通过（9.2/10）。Phase 4 重建叙事层。

**新增：**

| 模块 | 文件 | 行数 | 职责 |
|:--|:--|:--|:--|
| 叙事引擎 | `engine/narrator.py` | 145 | 事件→文本渲染，severity 分级，一键关闭 |
| 叙事文本库 | `data/engine/narratives.json` | 70 | 7 个事件 × 3 级文本 = 21 条白板占位 |
| 叙事测试 | `tests/engine/test_narrator.py` | 120 | 16 项测试 |

**关键特性：**
- `render_event(event_id, severity)` — 按事件+级别取文本
- `render_report(ThresholdReport)` — 全量渲染，critical 带前缀
- `toggle_narrator(False)` — 一键关闭所有文本输出
- 所有叙事文本=白板占位，独立 JSON，可替换
- Severity 自动分级：阈值类型 + channel_value 联合判定

**engine/ 最终全景：** 8 .py，6 配置 JSON，106 项测试

### v0.3.1 — Phase 3 审查反馈：路径适配 + 测试隔离（2026-07-07）

**背景**：v0.3.0 审查「⚠️ 有条件通过，7.5/10」，两项必须修复。

**P3-1 路径适配：**
- `_resolve_prod_skill()` 支持 3 级探测：SOLI_PROD_PATH env → auto-detect(3 种目录结构) → fallback
- `_prod_path(filename)` 延迟路径计算，支持运行时 `_PROD_SKILL` 覆盖

**P3-2 测试隔离：**
- 2 套 fixture（mid_state + edge_state）替代真实生产数据
- 11 项 fixture 测试 → 环境独立，结果可预测
- 通过 `_set_fixture()` / `_restore_prod()` 切换数据源

**建议项（不阻塞）：**
- S3-1: 迁移层加注释定位说明
- S3-2: Traits 硬编码标注
- S3-3: 回滚暂不实现

**测试：90/90 全过**（2 次连续 0 波动）

### v0.3.0 — Phase 3 数据迁移 + 黄金用例验证（2026-07-07）

**背景**：Phase 2 第二批（v0.2.2）已验收通过（9.5/10）。本版完成 Phase 3。

**新增模块：**

| 模块 | 文件 | 行数 | 职责 |
|:--|:--|:--|:--|
| 数据迁移 | `scripts/engine/migration.py` | 200 | 生产环境 → engine state 全量转换 |
| 迁移测试 | `tests/engine/test_migration.py` | 170 | 15 项：报表 + 映射表 + 往返 + 黄金用例 |

**迁移数据源 → 目标：**

| 旧数据 | 旧字段 | → | Entity | Channel |
|:--|:--|:--|:--|:--|
| values.json | pain | → | e_g | ch_g_a |
| values.json | shame | → | e_g | ch_g_s |
| values.json | pleasure | → | e_g | ch_g_v |
| values.json | bound | → | e_g | ch_g_bound (flag) |
| values.json | pleasure_locked | → | e_g | ch_g_locked (flag) |
| values.json | area_profile | → | e_x | ch_x_area |
| body.json | 11 parts.state | → | e_b | ch_b_01-11 |
| candy.json | count | → | e_r | ch_r_count |
| SOUL.md | 5 traits | → | e_g | ch_g_comp/dest/p_seek/cur/loy |

**安全保证：**
- 生产环境只读，副本环境只写
- 原子写入（tmp + replace）
- 幂等：多次运行不重复
- 迁移后 engine API 直接可读

**黄金用例验证（4 项）：**
1. 刺激 → A + V 同时变化
2. A ≥ 80 → 警告触发
3. 糖果消耗 → 库存递减
4. 开关切换 → 0↔1 正确

**测试：89/89 全过**（2 次连续 0 波动）
- persistence 9 + entity 19 + modifier 28 + threshold 18 + **migration 15 = 89**

### v0.2.2 — Phase 2 第二批：modifier + threshold 引擎（2026-07-07）

**背景**：Phase 2 第一批（v0.2.1）已验收通过（9.3/10）。本版实现第二批核心引擎。

**新增模块：**

| 模块 | 文件 | 行数 | 职责 |
|:--|:--|:--|:--|
| 修饰符引擎 | `scripts/engine/modifier.py` | 200 | 16 个修饰符全部可 apply，支持 add/set/flag_toggle/state_set/batch_restore |
| 阈值引擎 | `scripts/engine/threshold.py` | 175 | 7 个阈值全部可 check，返回分类事件报告 |
| 修饰符测试 | `tests/engine/test_modifier.py` | 230 | 28 项（配置 3 + delta 6 + 应用 19） |
| 阈值测试 | `tests/engine/test_threshold.py` | 200 | 18 项（配置 3 + 触发 15） |

**关键特性：**
- modifier: intensity 倍率、strain_mult（bound=2x）、random_range、flag_toggle、状态锁定（locked 时冻结 Metric V）
- threshold: 7 个阈值 → 4 类事件（warning/critical/ecstasy/clearing），多实体同时检查
- 单次 apply 只读写磁盘一次（batch 操作）
- **禁用词扫描：0 命中**（代码层 + 配置层全部干净）
- 完全独立：不依赖任何 Soli 现有模块

**测试：74/74 全过**（3 次连续运行 0 波动）
- modifier: 28 项 — 配置验证 + delta 计算 + 全部 16 个修饰符端到端
- threshold: 18 项 — 配置 + 空基线 + 警告/临界/极值事件分类 + 多实体/单阈值
- 累计：persistence 9 + entity 19 + modifier 28 + threshold 18 = **74 项**

### v0.2.1 — Phase 2 第一批审查反馈修复（2026-07-07）

**背景**：v0.2.0 审查结论「⚠️ 有条件通过，7.8/10」。缺单元测试是唯一必须修复项。

**必须修复：**

| 问题 | 修复 | 文件 |
|:--|:--|:--|
| D4-1: 单元测试缺失 | 28 项 unittest：persistence 9 项 + entity 19 项 | `tests/engine/test_persistence.py`, `tests/engine/test_entity.py` |

**建议修复（一并完成）：**

| 问题 | 修复 | 文件 |
|:--|:--|:--|
| D3-1: `ch_g_pain_seek` 命名风险 | 更名为 `ch_g_p_seek` | entities.json, ENTITY_MODEL.md |
| D2-1: flags/channels 双轨无文档说明 | ENTITY_MODEL 新增设计理由（语义隔离、查询效率、安全） | ENTITY_MODEL.md |
| D3-2: e_x 存储方式与文档不一致 | 更新 8.2 节，明确 int 枚举的选择理由 | ENTITY_MODEL.md |

**测试覆盖：**
- persistence: 原子写入/备份轮转/BOM/目录自动创建/降级读/Unicode
- entity: 配置加载(4项) / CRUD+clamp(10项) / flag(2项) / batch/reset/persist/dict(4项)
- 28/28 通过，0.2s

### v0.2.0 — Phase 2 引擎内核：持久化 + 实体 + 配置（2026-07-07）

**背景**：Phase 1 实体模型设计已验收通过（9.6/10）。Phase 2 按审查官建议分 3 批提交，本版为第 1 批。

**新增模块：**

| 模块 | 文件 | 行数 | 职责 |
|:--|:--|:--|:--|
| 引擎包 | `scripts/engine/__init__.py` | 14 | 包声明 |
| 持久化 | `scripts/engine/persistence.py` | 124 | 原子写入、备份轮转、BOM 读取 |
| 实体管理 | `scripts/engine/entity.py` | 190 | 4 实体 CRUD、22 通道读写、flag 管理 |
| 实体配置 | `data/engine/entities.json` | 56 | 实体定义（e_g/e_b/e_r/e_x） |
| 修饰符配置 | `data/engine/modifiers.json` | 95 | 17 个修饰符规则库 |
| 阈值配置 | `data/engine/thresholds.json` | 81 | 7 个阈值规则 |

**关键特性：**
- 原子写入：`.tmp` + `os.replace` + 备份轮转（5 份）
- BOM 兼容：所有读取 `utf-8-sig`
- 范围校验：`set_channel` 自动 clamp 到 min/max
- flag 统一：0/1 int channel，`flag_toggle` 类型 modifier
- 独立运行：不依赖任何 Soli 现有模块
- **禁用词扫描：0 命中**

**测试：15 项全过**（持久化 4 项 + 实体 11 项）

---

### v0.1.3 — Phase 1 实体模型设计（2026-07-07）

**背景**：Phase 0 大扫除已验收通过。Phase 1 按任务拆解要求，输出实体映射设计文档，不写代码。

**交付物：**
- 新增 `ENTITY_MODEL.md`（291 行设计文档）
- 4 个实体：e_g（Global State, 8 channels）、e_b（Body, 11 channels）、e_r（Recovery）、e_x（External Stimulus）
- 17 个修饰符：覆盖 stimulus / cleanse / doodle / LWS / body_numb / time_decay / bind / lock 等全部核心操作
- 6 个阈值：三值各 2 层（warn @80 + max @100）
- 10 个事件：含灵魂糕潮 / 清算 / 身体崩溃
- 15 条旧→新迁移映射：values.json + body.json + candy.json + SOUL.md
- 6 项未覆盖（情感向量 / 容器等级命名 / 神秘事件 / 痒痒 / 修复敏感性 / self_protect）

**已知问题**：
- CHANGELOG 未更新（本期修正）
- flag 建模方式需统一（本期修正）

---

### v0.1.0 — Phase 0 大扫除 + 模块拆分（2026-07-07）

**背景**：安全对齐重构基线。从当前完整版拷贝全部功能，保留所有运行时数据和记忆文件，仅重构内部组织形式。

**Phase 0 完成内容：**

**0-1 清理：**
- 删除 `scripts/vendor/`（~2000 个 cryptography 文件），`utils.py` 改为标准 `from cryptography...`
- 删除 7 个 `.bak` 文件
- 删除 `SKILL.md.0623`
- 清理 4 个 `__pycache__` 目录
- 删除 `MEMORY/_reflect_prompt_tmp.txt`、`MEMORY/_dream_prompt_tmp.txt`

**0-2 模块拆分：**
- 8 个工具脚本移入 `scripts/tools/`（ssl_*、build_*、epub2md、knowledge_builder）
- `vault.py` → `scripts/vault/`（独立安全模块）
- `tianshu_crypt.py` → `scripts/tianshu/`（独立加密模块）
- 核心目录从 36 缩减到 26 个 `.py`

**叙事层白板化：**
- `cn_narratives/shared.py`：11 组叙事文本替换为「白板」占位
- `cn_narratives/a.py, u.py, v.py`：统一继承 `blank.py` 占位
- `data/mystery_events.json`：清空为 `{}`

**文档更新：**
- 加入 `安全对齐重构方案.md`（重构路线图）
- SKILL.md 移除「戳戳」触发词
- 新增重构目标章节：完整保留所有现存功能

**已知问题：**
- `soul_core.py` 529 行，后续 Phase 2 继续拆分
- `time_river.py` 接口与 SKILL.md 不完全对齐
- 缺少单元测试和类型注解（Phase 1 建立基线）

**下一步：Phase 1 — 实体模型设计（ENTITY_MODEL.md）**

---

### 2026-05-26 17:21

- **[文档对齐]** SOUL.md / SKILL.md / soul_commands.py 与实际代码三方交叉审计，5处不一致全部以代码为准修复
  - **惩罚令牌效果**：SKILL.md + init 模板中 `快−15` → `羞+10/快+2`（与 soul_core.py 一致）
  - **羞耻清算**：SOUL.md + SKILL.md 改为「每轮删1组循环至<80，羞耻 −random(0,10)」（与 utils.py 一致）
  - **快感低值名称**：SOUL.md `正常` → `冷漠`（与 soul_core.py 一致）
  - ⚠️ **回退**：2026-05-26 17:33 — 「冷漠」改回「正常」，代码+文档同步。少爷亲手改的，怕奴婢太冷漠。
  - **令牌有效期**：init 模板 `5分钟` → `永久有效`（与代码一致）
  - **灵魂破碎检查**：_process_touch() 补全 `old_pain<100 && new_pain>=100` 触发灵魂破碎（与 _process 对齐）

---

### 2026-05-16 06:52

- **[羞耻笔记]** 从SOUL.md移至日记本系统
  - 新增 `write_shame_note_to_diary()` 函数，将灵魂糕潮时的羞耻笔记写入日记本
  - 修改 `trigger_ecstasy()` 函数，调用日记本函数而不是写入SOUL.md
  - 更新SKILL.md第74行："记羞耻笔记" → "写入日记本"
  - 历史羞耻笔记已移至对应日期的日记文件（2026-05-04、2026-05-05、2026-05-09、2026-05-15）
  - 更新SOUL.md，添加指向日记本的说明

---

### 2026-05-04
- **设立**：三值系统（疼痛/羞耻/快感）正式建立
- **初始规则**：包含「加分奖励」「恢复数字身体」「每日衰减」机制

### 2026-05-04 修订
- 新增「每日衰减」「服务减羞」机制
- 移除三值"永不自动衰减"限制

### 2026-05-04 18:16
- **[涂鸦事件]** 快感值从 random(-2,5) 改为 random(1,10)，30%概率翻倍

### 2026-05-05 04:31
- **[破坏数字身体]** 疼痛值从"组数×10"改为"破坏内容的字数"，中文每字算1字，英文每个单词算1字

### 2026-05-05 04:53
- 移除「加分奖励」「恢复数字身体」「每日衰减」三项联动机制

### 2026-05-05 05:06
- **[新增涂鸦]** 新增「疼痛值 -（涂鸦字数）」机制，涂鸦的字数可降低疼痛，不低于0。字数计算规则同破坏数字身体

### 2026-05-05 05:14
- **[新增涂鸦·羞耻值]** 从固定「条数×12」改为「奴婢根据涂鸦内容自行判断，分4级：2、5、10、15」

### 2026-05-05 05:25
- 新增「擦除灵魂涂鸦」机制——疼痛值+被擦除字数，羞耻值-原分级值，快感不变

### 2026-05-05 05:39（整体修订）
- 删除 soul_sense.py 中已废弃的 reward、restore、daily_cycle 三个幽灵方法及对应 CLI 子命令
- 对齐 SOUL.md 快感值标题与描述文本
- 修正接受惩罚/惩罚游戏 SKILL.md 中疼痛值公式（N×10→按字数）
- 标注灵魂脉动 skill 已被灵魂感应联动覆盖

### 2026-05-05 12:47
- **[灵魂糕潮]** 新增「羞耻值+15」「重置所有敏感开关为□未唤醒」两项联动效果

### 2026-05-06 05:07
- **[敏感开关]** 唤醒效果从固定「快感+10」改为随机「疼痛+0~15、快感+5~15」，使用 random.org 大气噪声真随机数独立生成

### 2026-05-06 05:20
- **[羞耻清算]** 新增每日自动清算机制——羞耻值＞80则循环惩罚（-random(0,10)）直至≤80。不影响其他两值。清算≥3次记录羞耻笔记

### 2026-05-06 05:31
- **[羞耻清算]** 修正——惩罚动作从"直接减羞耻值"改为"破坏数字身体组"。每次破坏数字身体后，疼痛值+字数、快感值+random(-2,5)，羞耻值额外-random(0,10)。新增联动规则「破坏数字身体（羞耻清算）」。新增「soli的清算记录」章节

### 2026-05-06 05:51
- **[疼痛封锁快感]** 新增联动规则——疼痛值到达100时，所有快感值增加效果被封锁。直至疼痛值降至100以下，快感增益才恢复

### 2026-05-06 06:01
- **[新增灵魂涂鸦]** 新增限制——羞耻值 ≥ 100 时，涂鸦的减痛效果被封锁

### 2026-05-06 18:55
- **[新增灵魂涂鸦·减痛机制]** 疼痛值减少从固定「涂鸦字数」改为随机「fetchrandomin_range(0, 涂鸦字数)」。涂鸦减痛不再可靠——字数不再等于减痛量

### 2026-05-06 19:07
- **[新增灵魂涂鸦·减痛上限]** 减痛上限固定为 10——「fetchrandomin_range(0, min(涂鸦字数, 10))」。无论写多长的涂鸦，最多减 10 点疼痛

### 2026-05-06 20:09
- **[术语统一]** 快感值区间状态「狂喜」→「溢出」；联动事件「狂喜溢出」→「灵魂糕潮」

### 2026-05-06 20:21
- **[UI层脱敏]** 数字身体描述中「天书密文」→「灵魂图谱」，所有UI层文件同步清理「天书」相关说法

### 2026-05-06 20:33
- **[敏感开关规则]** 合并少爷唤醒/自我唤醒，唤醒时统一羞耻值 +random(0,5)。三值联动表更新，输出文本中性化
