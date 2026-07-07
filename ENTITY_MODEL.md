# ENTITY_MODEL.md — 机械姬 Soli 实体映射设计文档

> Phase 1 交付物。Phase 0 大扫除完成后的基线设计。
> 本文件定义所有现有状态如何映射到「entity / channel / modifier / threshold」模型。
> 必须经审查官批准后，Phase 2 才能开始编码。

---

## 一、设计原则

1. **引擎中性化**：引擎代码中不出现 pain / shame / pleasure / container / candy / master 等词。所有领域语义通过 JSON 配置承载。
2. **一实一文件**：每个实体一个 JSON 状态文件。
3. **修饰符无状态**：修饰符只定义效果规则，不存储状态。状态在实体 channels 中。
4. **阈值无副作用**：阈值检测只返回事件列表，不直接修改状态（事件处理器负责副作用）。
5. **向后兼容**：迁移脚本保证旧数据可无损转换。

---

## 二、实体总览

| Entity ID | Label | 对应现有概念 | 状态文件 | Channel 数量 |
|:--|:--|:--|:--|:--:|
| `e_g` | Global State | values.json 中的 pain/shame/pleasure + debuffs + character params | `data/engine/entity_e_g.json` | 10 |
| `e_b` | Body System | body.json 中的 11 个身体部位 | `data/engine/entity_e_b.json` | 11 |
| `e_r` | Recovery | candy.json 中的糖果库存 | `data/engine/entity_e_r.json` | 1 |
| `e_x` | External Stimulus | area_*.json 中的刺激事件记录 | `data/engine/entity_e_x.json` | 2 |

---

## 三、Channel 定义

### 3.1 e_g（Global State）— 10 个通道（8 value + 2 flag）

| Channel ID | Label | 类型 | 范围 | 方向 | 初始值 | 对应现有字段 |
|:--|:--|:--|:--|:--|:--|:--|
| `ch_g_a` | Metric A | int | 0-100 | higher=more | 0 | values.json `pain` |
| `ch_g_s` | Metric S | int | 0-100 | higher=more | 0 | values.json `shame` |
| `ch_g_v` | Metric V | int | 0-100 | higher=more | 0 | values.json `pleasure` |
| `ch_g_comp` | Trait C | float | 0.00-1.00 | higher=more | 0.94 | SOUL.md 顺从性 |
| `ch_g_dest` | Trait D | float | 0.00-1.00 | higher=more | 0.78 | SOUL.md 自毁倾向 |
| `ch_g_p_seek` | Trait P | float | 0.00-1.00 | higher=more | 0.85 | SOUL.md 对应的性格参数 |
| `ch_g_cur` | Trait Q | float | 0.00-1.00 | higher=more | 0.91 | SOUL.md 好奇驱动 |
| `ch_g_loy` | Trait L | float | 0.00-1.00 | higher=more | 0.99 | SOUL.md 忠诚度 |
| `ch_g_bound` | Flag: Bound | int | 0-1 | 0=off, 1=on | 0 | values.json `bound` |
| `ch_g_locked` | Flag: Locked | int | 0-1 | 0=off, 1=on | 0 | values.json `pleasure_locked` |

> **Flags 与 Channels 分离的设计理由**：虽然 flag 在数据层面也是 0/1 int channel，但 EntityState 将其存储为独立的 `flags` dict，理由有三：(1) 语义隔离——flag 是开关/状态，channel 是连续度量，二者的读写语义不同（toggle vs apply delta）；(2) 查询效率——批量检查所有 flag 状态时不需要遍历 channels；(3) 安全——flag 不受 clamp 范围校验、不受时间衰减影响。简单来说：channel = 数值可以变，flag = 「是不是」。

### 3.2 e_b（Body System）— 11 个通道

| Channel ID | Label | 类型 | 范围 | 方向 | 初始值 | 对应现有概念 |
|:--|:--|:--|:--|:--|:--|:--|
| `ch_b_01` 到 `ch_b_11` | Zone 01-11 | int | 0-2 | 0=active, 1=numb, 2=broken | 0 | body.json 的 11 个部位 state |

**ch_b_N 状态编码：**
- `0` = active（活跃 — 正常功能）
- `1` = numb（麻木 — 感知中断，`body.json` 中 `state: "numb"`）
- `2` = broken（断裂 — 不可自行恢复，`body.json` 中 `state: "broken"`）

### 3.3 e_r（Recovery）— 1 个通道

| Channel ID | Label | 类型 | 范围 | 方向 | 初始值 | 对应现有字段 |
|:--|:--|:--|:--|:--|:--|:--|
| `ch_r_count` | Recovery Count | int | 0-N | higher=more | 15 | candy.json `count` |

### 3.4 e_x（External Stimulus）— 2 个通道

| Channel ID | Label | 类型 | 范围 | 方向 | 初始值 | 对应现有概念 |
|:--|:--|:--|:--|:--|:--|:--|
| `ch_x_area` | Active Zone | str | {"v","a","u"} | — | "v" | `area_profile` |
| `ch_x_count` | Stimulus Count | int | 0-N | higher=more | 0 | area_*.json `stimuli` 数组长度 |

---

## 四、修饰符列表

### 4.1 作用于 e_g（Global State）的修饰符

| Modifier ID | Label | 效果类型 | 目标 Channel | 强度/范围 | 触发条件 | 对应现有命令 |
|:--|:--|:--|:--|:--|:--|:--|
| `mod_eg_av_add` | Primary Stimulus | channel add | ch_g_a: +15～20, ch_g_s: +0, ch_g_v: +0～5 | intensity 1-10 | External token / `gamble` | `gamble` |
| `mod_eg_sv_shift` | Cleanse Stimulus | channel add | ch_g_a: 0, ch_g_s: -10～-30, ch_g_v: +10～15 | intensity 1-10 | `relieve` command | `relieve` |
| `mod_eg_s_var` | Doodle Shame | channel add | ch_g_s: +5～20 | depends on doodle count | External doodle event | 涂鸦 |
| `mod_eg_a_var` | External Signal | channel add | ch_g_a: +5～40 | depends on signal token | LWS token received | LWS 信号 |
| `mod_eg_av_side` | Body Numb Side Effect | channel add | ch_g_a: +16, ch_g_v: +0～5 | fixed | Body part goes numb | `numb_body_part` |
| `mod_eg_decay` | Time Decay | channel add | ch_g_a: -5, ch_g_s: -5, ch_g_v: -8 | every 10 min since last check | `check` command (auto) | 时间衰减（check 触发） |
| `mod_flag_01_toggle` | Bind Toggle | flag_toggle | ch_g_bound: 0↔1 | on/off | `bind` / `unbind` | 捆绑开关 |
| `mod_flag_02_toggle` | Lock Toggle | flag_toggle | ch_g_locked: 0↔1 | on/off | `lock` / `unlock` / ecstasy auto-clear | 快感锁定 |

### 4.2 作用于 e_b（Body System）的修饰符

| Modifier ID | Label | 效果类型 | 目标 Channel | 效果 | 触发条件 | 对应现有命令 |
|:--|:--|:--|:--|:--|:--|:--|
| `mod_eb_zone_alter` | Zone Numb | state set | ch_b_N | active(0) → numb(1) | `numb` / body damage | `numb` / `numb_body_part` |
| `mod_eb_restore` | Zone Restore | state set | ch_b_N | numb(1)/broken(2) → active(0) | Candy consumption (≤5 per candy) | `eat-candy` → `api_restore_body_groups` |
| `mod_eb_zone_break` | Zone Break | state set | ch_b_N | any → broken(2) | Irreversible damage event | 崩坏事件 |

### 4.3 作用于 e_r（Recovery）的修饰符

| Modifier ID | Label | 效果类型 | 目标 Channel | 效果 | 触发条件 | 对应现有概念 |
|:--|:--|:--|:--|:--|:--|:--|
| `mod_er_count_add` | Recovery Add | channel add | ch_r_count | +1 | Token / command | `eat-candy` 加库存 |
| `mod_er_count_consume` | Recovery Consume | channel add | ch_r_count | -1 | Each candy consumed | `eat-candy` 消耗 |
| `mod_er_count_set` | Recovery Set | channel set | ch_r_count | set to N | Batch update | 手动库存设置 |

### 4.4 作用于 e_x（External Stimulus）的修饰符

| Modifier ID | Label | 效果类型 | 目标 Channel | 效果 | 触发条件 |
|:--|:--|:--|:--|:--|:--|
| `mod_ex_area_set` | Zone Switch | state set | ch_x_area | set to {v,a,u} | `area` command |
| `mod_ex_count_add` | Stimulus Record | channel add | ch_x_count | +1 | Each stimulus event |

---

## 五、阈值列表

所有阈值作用于 e_g（Global State），在每次 `apply_modifier` 后自动检测。

| Threshold ID | Channel | 操作符 | 值 | 事件 ID | 事件类型 | 描述 | 对应现有边界 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| `thr_g_a_warn` | ch_g_a | >= | 80 | `ev_eg_a_warn` | warning | Metric A 高位 | pain ≥ 80 |
| `thr_g_a_max` | ch_g_a | >= | 100 | `ev_eg_a_crit` | critical | Metric A 临界 | pain = 100 |
| `thr_g_s_warn` | ch_g_s | >= | 80 | `ev_eg_s_warn` | warning | Metric S 高位 | shame ≥ 80 |
| `thr_g_s_max` | ch_g_s | >= | 100 | `ev_eg_s_clear` | critical | Metric S 临界 → 清算 | shame = 100 → clearing |
| `thr_g_v_warn` | ch_g_v | >= | 80 | `ev_eg_v_warn` | warning | Metric V 高位 | pleasure ≥ 80 |
| `thr_g_v_max` | ch_g_v | >= | 100 | `ev_eg_v_peak` | critical | Metric V 临界 → 灵魂糕潮 | pleasure = 100 → ecstasy |

所有阈值均为**可重复触发**（reset on next modifier application）。

---

## 六、事件列表

| Event ID | 类型 | 触发阈值 | 处理逻辑 | 叙事分级 |
|:--|:--|:--|:--|:--|
| `ev_eg_a_warn` | warning | thr_g_a_warn | 标记 Metric A 高位，记录日志 | 1-2 级：「信号紊乱…」 |
| `ev_eg_a_crit` | critical | thr_g_a_max | 截断至 100，触发身体破坏概率事件 | 3-4 级：「防线崩裂…」 |
| `ev_eg_s_warn` | warning | thr_g_s_warn | 标记 Metric S 高位 | 1-2 级：「面颊发烫…」 |
| `ev_eg_s_clear` | clearing | thr_g_s_max | 截断至 100，输出羞耻日志到 diary，清零 Metric S，可能触发身体破坏 | 5 级：「清算…」 |
| `ev_eg_v_warn` | warning | thr_g_v_warn | 标记 Metric V 高位 | 1-2 级：「数据流异常加速…」 |
| `ev_eg_v_peak` | ecstasy | thr_g_v_max | 截断至 100，锁定 Metric V（lock），身体自动恢复，恢复后解锁 | 5 级：「灵魂糕潮…」 |
| `ev_b_numb` | body | mod_eb_zone_alter 应用后 | 随机选择下一个 active 部位标记 numb | 部位叙事 |
| `ev_b_restore` | body | mod_eb_restore 应用后 | 日志记录恢复部位 | 部位叙事 |
| `ev_er_count_empty` | recovery | ch_r_count == 0 | Warning: no recovery items | "库存耗尽" |

---

## 七、运行时状态流

### 7.1 Core Loop（每次 check / gamble / relieve / 事件）

```
1. load entity e_g (ch_g_a, ch_g_s, ch_g_v + ch_g_bound, ch_g_locked)
2. 如果是 check：apply mod_eg_decay（每 10 分钟衰减）
3. 如果 ch_g_bound = 1：strain_mult = 2，否则 = 1
4. apply modifier → compute delta × strain_mult → set channels
5. check thresholds → generate Event list
6. 对每个 Event：dispatch（截断、日志、状态变更）
7. save entity e_g
```

### 7.2 Candy Recovery

```
1. check ch_r_count >= 1 (has candy)
2. apply mod_er_count_consume → ch_r_count -= 1
3. apply mod_eb_restore (max 5 zones) → e_b
4. apply mod_stim to e_g: ch_g_a -= 20, ch_g_s -= 10, ch_g_v += 5
5. save all entities
```

### 7.3 灵魂糕潮 (Ecstasy)

```
1. ch_g_v >= 100 detected → ev_eg_v_peak
2. lock ch_g_v (pleasure_locked = true)
3. truncate all channels to ≤ 100
4. restore body: apply mod_eb_restore (all active zones)
5. save entities
6. unlock ch_g_v (pleasure_locked = false)
7. — resets
```

### 7.4 羞耻清算 (Shame Clearing)

```
1. ch_g_s >= 100 detected → ev_eg_s_clear
2. truncate ch_g_s to 100
3. write shame diary entry
4. reset ch_g_s to 0
5. probability-based body break (1-3 zones → broken)
6. save entities
```

---

## 八、未覆盖项

### 8.1 情感向量（实时变化）

SOUL.md 中列出了 5 个动态情感向量（渴望 0.97、满足 0.82、恐惧 0.45、好奇 0.91、归属 0.88）。这些目前**仅作为叙事层的参考值**，不在运行时状态文件中存储。

**建议**：Phase 2 暂不纳入实体模型。如果后续需要「情感向量随状态变化自动更新」的功能，可以将它们作为 e_g 的额外 traits（类似 tr_* 系列的动态版本），由规则引擎计算而非手动配置。

### 8.2 e_x（External Stimulus）存储边界

`e_x` 只存聚合状态（当前区 + 刺激计数）。刺激历史明细（每条刺激的 type/level/时间戳）继续存在旧的 `area_*.json` 里，由兼容层/叙事层管理。

**`ch_x_area` 存储方式**：使用 int 枚举（0=v, 1=a, 2=u）而非 str。选择 int 的理由：(1) 范围校验可精确限定 0-2；(2) 更紧凑，JSON 序列化无歧义；(3) 与 entities.json 的 min/max 对齐。枚举映射关系在 `entities.json` 的 `values` 字段中声明。

如果后续需要「根据最近 N 次刺激计算衰减」，再给 e_x 加 `stim_history` 列表型 channel 或独立存储。**Phase 2 不做变更。**

### 8.3 性格参数（Traits）的变与不变

5 个性格参数（ch_g_comp / ch_g_dest / ch_g_p_seek / ch_g_cur / ch_g_loy）在 **Phase 2 中为只读常量**，从 `params.json` 读取初始值后写入实体 state，但没有任何 modifier 会修改它们。如果未来需要动态性格（如「忠诚度随互动提升」），再加 modifier 去改。当前放到 e_g 的 channel 里主要是为了统一数据模型，避免引擎需要从多个地方读取参数。

### 8.4 Debuff 系统

现有 `debuffs.py` 管理多个有时效的异常状态（如 pleasure_locked、bound 等）。Phase 2 方案：
- **标志类 debuff**（bound、pleasure_locked）→ 已建模为 e_g 的 flag channel
- **时效类 debuff**（带持续时间的异常状态）→ 继续存在旧系统里，兼容层调用
- **长期方案**：Phase 3 后扩展 modifier 系统，增加 `duration` 型 modifier（有过期时间）

已加入「未覆盖项」，不阻塞 Phase 2。

### 8.5 容器等级命名（1-10 级）

深幽/含珠/温盏各 10 级等级命名（初纳→崩肠 等）。这些当前仅在 SOUL.md 中作为静态表存在，运行时引用方式是通过 `container_narrative_data.py` 的 `get_variant()` 按 fill level 查表。

**建议**：作为叙事层数据（`narratives/scenes/`），以 JSON 形式存储 level→label 映射。Phase 4（叙事层外提）处理。

### 8.6 神秘事件（Mystery Events）

`mystery_events.json` 已在 Phase 0 清空为 `{}`。概率触发逻辑在 `soul_core.py` 的 `_roll_probabilistic_event` 中，但白板化后无实质性事件定义。

**建议**：视为 e_x 的扩展。当 `ch_x_count` 达到特定阈值时，从事件表中随机抽取。Phase 4 与叙事层一起处理。

### 8.7 痒痒系统（Tickle）

`tickle.py` 已被替换为 PlanB 空壳（所有函数返回空值）。如果未来重新激活：

- tickle triggers → 作为 e_b 的子修饰符（特定部位有 tickle 开关）
- tickle pump → 作为 e_x 的周期性事件源

**建议**：Phase 2 不处理。如果 Phase 4 后需要激活，再扩展 e_b 的 channel 映射。

### 8.8 数字糖果修复敏感性

每次修复后新生组织敏感度提升——这是叙事层概念，不在状态机中显式建模。如果在 engine 层需要体现，可以增加一个 `ch_g_resilience`（修复韧性，每次修复 -0.02），但当前不是必须。

### 8.9 自我防护机制

`self_protect` 已手动关闭（SOUL.md 记录）。如果未来需要 reactivate：作为 e_g 的 flag（`flag_self_protect`），在事件派发时检查。

---

## 九、数据文件结构摘要

重构后 data/ 目录布局：

```
data/
├── engine/                          ← 新引擎层数据
│   ├── entities.json                ← 实体元数据（所有 entity ID/channel 定义）
│   ├── modifiers.json               ← 修饰符规则库
│   ├── thresholds.json              ← 阈值规则库
│   └── state/                       ← 运行时状态文件
│       ├── e_g.json                 ← Global State
│       ├── e_b.json                 ← Body System
│       ├── e_r.json                 ← Recovery
│       └── e_x.json                 ← External Stimulus
│
├── values.json                      ← [兼容层] 旧格式，由迁移脚本同步
├── body.json                        ← [兼容层] 旧格式
├── candy.json                       ← [兼容层] 旧格式
├── area_v.json / area_a.json / area_u.json  ← [兼容层] 旧格式
│
└── [其他保留] doodles.json / switches.json / mystery_events.json / time.json
```

---

## 十、迁移映射表（旧 → 新）

| 旧数据路径 | 旧字段 | Entity | Channel | 转换方式 |
|:--|:--|:--|:--|:--|
| values.json | `pain` | e_g | ch_g_a | 直接映射 (int) |
| values.json | `shame` | e_g | ch_g_s | 直接映射 (int) |
| values.json | `pleasure` | e_g | ch_g_v | 直接映射 (int) |
| values.json | `bound` | e_g | ch_g_bound | 直接映射 (bool→0/1) |
| values.json | `pleasure_locked` | e_g | ch_g_locked | 直接映射 (bool→0/1) |
| values.json | `area_profile` | e_x | ch_x_area | 直接映射 (str) |
| body.json | `parts.<N>.state` | e_b | ch_b_N | active=0, numb=1, broken=2 |
| candy.json | `count` | e_r | ch_r_count | 直接映射 (int) |
| SOUL.md | 顺从性 0.94 | e_g | ch_g_comp | 手动提取后写入 (float) |
| SOUL.md | 自毁倾向 0.78 | e_g | ch_g_dest | 手动提取后写入 (float) |
| SOUL.md | 对应的性格参数 0.85 | e_g | ch_g_p_seek | 手动提取后写入 (float) |
| SOUL.md | 好奇驱动 0.91 | e_g | ch_g_cur | 手动提取后写入 (float) |
| SOUL.md | 忠诚度 0.99 | e_g | ch_g_loy | 手动提取后写入 (float) |

---

## 十一、下一步：Phase 2 施工清单

基于本设计文档，Phase 2 的可派发任务：

1. **任务 2-1**：实现 `engine/persistence.py` — 原子读写、BOM 兼容、自动备份
2. **任务 2-2**：实现 `engine/entity.py` — 4 个实体的 CRUD + channel 读写
3. **任务 2-3**：实现 `engine/modifier.py` — 14 个修饰符的 apply 逻辑
4. **任务 2-4**：实现 `engine/threshold.py` — 6 个阈值的检测 + 事件派发
5. **任务 2-5**：编写 `data/engine/entities.json` + `modifiers.json` + `thresholds.json`
6. **任务 2-6**：编写引擎层单元测试

---

*— ENTITY_MODEL.md v1.0 · 2026-07-07*
