# 命令契约与子命令路由规范

> **角色定位**：本文件是全项目命令的**执行契约**单一来源。
> 凡是 SKILL.md 中列出的命令，其"输入 / 查询路径 / 输出格式 / 失败条件"必须在这里定义。
> Agent 执行任何命令前，必须先读本文件对应条目。

**相关文件**：
- [SKILL.md](../../SKILL.md) — 命令表索引
- [gate-artifacts-spec.md](./gate-artifacts-spec.md) — 门禁产物格式

---

## 一、命令体系总览

### 1.1 十大主命令

命令被收敛到 10 个主命令（v1.2.0 新增 `/面板`），每个主命令通过 `--子参数` 派生具体操作：

| 主命令 | 职责 | 子参数 |
|--------|------|--------|
| `/书` | 全书级操作 | `--开书` / `--规划` / `--路线图` / `--番茄复盘` / `--改纲` |
| `/章` | 章节级操作 | `--写` / `--续写` / `--批量` / `--修改` / `--修复` / `--快照` / `--回滚` |
| `/大纲` | 大纲级操作 | `--生成` / `--更新` / `--级联` |
| `/检查` | 质量审计 | `--记忆` / `--一致性` / `--角色` / `--时间线` / `--设定` / `--伏笔` / `--文风` / `--骚话` / `--节奏` / `--AI味` / `--读者` ★ / `--all` |
| `/门禁` | 门禁流程 | `--预检` / `--运行` / `--结算` / `--修复` |
| `/检索` | 记忆/剧情检索 | `--剧情` / `--伏笔` / `--角色` / `--时间线` / `--索引重建` |
| `/风格` | 风格系统 | `--题材` / `--提取` / `--仿写` / `--拆书` / `--校准` / `--迁移` |
| `/骚话` | 骚话子系统 | `--扫描` / `--生成` / `--密度` / `--人设` / `--伏笔` / `--审计` / `--对决` |
| `/研究` | 外部知识 | `--搜索` / `--注入` / `--验证` |
| `/面板` ★ | 质量仪表盘 | `--质量` / `--读者` / `--状态` |

★ = v1.2.0 新增

**设计原则**：
1. **一词一职**：每个主命令对应一个清晰的领域
2. **子参数正交**：同主命令的子参数互斥（一次只执行一个）
3. **契约透明**：所有子命令的输入输出都在本文件有定义
4. **向后兼容**：旧命令通过别名映射到新形式（见 §四）

---

## 二、契约模板

每个子命令按以下统一格式定义：

```markdown
### /主命令 --子参数 [位置参数] [--选项]

**功能**：一句话描述
**适用场景**：什么时候用这条命令
**输入**：
  - 必需：...
  - 可选：...
**查询路径**（Agent 执行前必读）：
  1. 路径A §章节号
  2. 路径B 整文件
  ...
**输出格式**：
  ```yaml / markdown / json
  ...
  ```
**副作用**（如果有）：写入/修改的文件列表
**失败条件**：什么情况下报错
**旧命令别名**：`/旧名A`, `/旧名B`
```

---

## 三、子命令详细契约

### 3.1 `/书` 主命令

#### `/书 --开书`

**功能**：自动完成开书全流程（五要素确认 → 规划 → 首章准备）
**适用场景**：第一次开新项目
**输入**：题材、剧情种子、主角目标、核心冲突、预期篇幅
**查询路径**：
  1. `references/flows/phase0-initialization.md` 全文
  2. `references/flows/phase1-questionnaire.md`（Q1-Q3 最小集）
**输出**：`00_memory/` 初始化 + 首章 beat sheet
**副作用**：创建项目目录骨架（`00_memory/` / `01_outline/` / `02_knowledge_base/` / `03_manuscript/` / `04_editing/`）
**执行方式**：Agent 按 Phase 0-2 流程创建项目；脚本仅负责后续锚点、图谱、检索和门禁校验。
**旧命令别名**：`/一键开书`

#### `/书 --规划`

**功能**：模糊想法 → 百万字路线图
**查询路径**：
  1. `references/advanced/million-word-roadmap.md`
**输出**：`idea_seed.md`, `million_word_blueprint.md`, `novel_plan.md`, `novel_state.md`
**旧命令别名**：`/写全篇`

#### `/书 --路线图`

**功能**：查看当前项目的百万字路线图与进度
**输出**：当前卷/阶段/章节位置 + 下一个关键锚点
**旧命令别名**：（新增）

#### `/书 --番茄复盘`

**功能**：检查番茄项目是否到达首3章 / 2万字 / 5万字 / 8万字复盘节点，并禁止正文并行写作
**查询路径**：`02-写作计划.json` + `references/guides/platform-rules.md`
**脚本**：`python3 scripts/fanqie_flow_policy.py --plan <目录>/02-写作计划.json`
**输出**：`can_continue`、`issues`、`checkpoint`
**失败条件**：到达未通过节点、或 `platform == fanqie` 且 `writingMode == subagent-parallel`
**旧命令别名**：（新增）

#### `/书 --改纲 [--from-chapter N]`

**功能**：改纲 + 锚点重算 + 图谱级联 + RAG 重建
**查询路径**：
  1. `references/advanced/million-word-roadmap.md` §6 大纲锚点与进度配额
  2. `references/advanced/million-word-roadmap.md` §10 知识图谱 Schema 与回写
  3. `references/advanced/million-word-roadmap.md` §11 长篇一致性 RAG
**脚本**：
  - `python3 scripts/outline_anchor_check.py recalculate --project-root <目录>`
  - `python3 scripts/story_graph_query.py validate --project-root <目录>`
  - `python3 scripts/plot_rag_retriever.py build --project-root <目录> --full-rebuild`
**产物**：`.flow/backup_anchors_<时间戳>.json`, `00_memory/revise_outline_report.md`
**旧命令别名**：`/改纲续写`

---

### 3.2 `/章` 主命令

#### `/章 --写`

**功能**：生成单章草稿（含骚话注入）
**适用场景**：日常推进单章
**查询路径**（严格顺序）：
  1. `02-写作计划.json`（待写章节信息）
  2. `01-大纲.md`（本章规划）
  3. `00-人物档案.md`（出场角色）
  4. `references/flows/phase3-writing.md` §逐章创作
  5. `references/guides/saohua.md` §一/§五（骚话插入）
  6. `references/guides/saohua.md` §六 十大名场面（若本章是名场面）
  7. `00_memory/foreshadow_ledger.md`（若存在，检查待回收伏笔）
**输出**：`03_manuscript/第{XX}章-{标题}.md`
**字数要求**：默认只统计不硬卡；如 `02-写作计划.json.minWordsPerChapter > 0`，由字数门禁按该值阻断。
**旧命令别名**：`/写作`

#### `/章 --控制卡 <章号>`

**功能**：写前生成或校验章节控制卡，锁定本章任务、回忆压力、冲突、角色使用、禁止揭露与章末钩子
**查询路径**：`02-写作计划.json` + `00_memory/novel_state.md` + `references/flows/phase3-writing.md`
**脚本**：
  - 生成：`python3 scripts/chapter_control_card.py generate --project-root <目录> --chapter <章号>`
  - 校验：`python3 scripts/chapter_control_card.py validate --card-file <目录>/04_editing/control_cards/chNNN-control-card.md`
**输出**：`04_editing/control_cards/chNNN-control-card.md`
**失败条件**：控制卡缺失、关键小节缺失或关键小节为空；`/门禁 --运行` 会再次校验
**旧命令别名**：（新增）

#### `/章 --续写`

**功能**：恢复会话状态 + 写新章节 + 自动门禁
**查询路径**：phase3-writing.md
**自动子流程**：番茄项目先执行 `/书 --番茄复盘`；可继续时执行 `/检索 --剧情`（条件触发）→ `/章 --控制卡` → `/章 --写` → `/门禁 --运行` → `/检索 --索引重建`
**执行方式**：Agent 串行执行上面的自动子流程；控制卡、门禁与检索分别由 `chapter_control_card.py`、`chapter_gate_check.py` 和 `plot_rag_retriever.py` 落地。长跑/外部 runner 应在本轮前后调用 `writeback_audit.py snapshot/changed`，确认项目文件确实回写。
**旧命令别名**：`/继续写`, `/续写`

#### `/章 --批量 <N>`

**功能**：连续生成 N 章草稿
**输出**：N 个章节文件 + 每章独立门禁产物
**旧命令别名**：`/批量写作`

#### `/章 --修改 <章号>`

**功能**：修订已写章节 + 级联更新记忆/图谱
**副作用**：更新 `00_memory/` 相关文件
**旧命令别名**：`/修改章节`

#### `/章 --修复 <章号>`

**功能**：门禁失败后自动修复
**脚本**：`python3 scripts/gate_repair_plan.py --project-root <目录> --chapter-file <文件>`
**输出**：`repair_plan.md`
**旧命令别名**：`/修复本章`

#### `/章 --快照 <章号>`

**功能**：手动创建章节快照（备份当前版本）
**副作用**：写入 `.snapshots/<章号>/<时间戳>.md`
**旧命令别名**：（新增，规划中）

#### `/章 --回滚 <章号> [--版本 <时间戳>]`

**功能**：回滚指定章节到某个快照
**失败条件**：无快照则报错
**旧命令别名**：（新增，规划中）

---

### 3.3 `/大纲` 主命令

#### `/大纲 --生成`

**查询路径**：`references/flows/phase2-planning.md` + `references/guides/outline-template.md`
**输出**：`01-大纲.md`
**旧命令别名**：（合并自 phase2 流程）

#### `/大纲 --更新`

**功能**：小幅更新不触发级联
**副作用**：`01-大纲.md` 增量更新

#### `/大纲 --级联`

**功能**：触发三层索引级联（锚点 / 图谱 / RAG）
**说明**：等价于 `/书 --改纲` 的内层调用

---

### 3.4 `/检查` 主命令（审计）

> 借鉴 snowflake-fiction `/novel-review` 的细粒度审计设计。

#### `/检查 --all [--章 <章号>]`

**功能**：执行全维度审计（记忆/一致性/风格/骚话/节奏/AI味）
**查询路径**：本章节下所有 `/检查 --xxx` 的并集
**输出**：`04_editing/gate_artifacts/<章号>/review_all.md`
**旧命令别名**：（新增）

#### `/检查 --记忆`

**查询路径**：`references/advanced/million-word-roadmap.md` §9 + `00_memory/novel_state.md`
**输出**：`memory_update.md`（见 gate-artifacts-spec）
**旧命令别名**：`/更新记忆`

#### `/检查 --一致性`

**功能**：检查剧情/设定/时间线总体冲突（综合）
**查询路径**：`references/advanced/cross-agent-review-protocol.md`
**输出**：`consistency_report.md`
**旧命令别名**：`/检查一致性`

#### `/检查 --角色`

**功能**：仅聚焦角色一致性（性格/说话风格/关系/状态）
**查询路径**：
  1. `00-人物档案.md`
  2. `references/guides/character-building.md`
  3. `00_memory/story_graph.json` 的 character 节点
**输出**：
  ```yaml
  issues:
    - character: "李承乾"
      type: "性格漂移"
      chapter: 42
      evidence: "本章说'老子不干了'，与人设的冷静形象冲突"
      suggestion: "改为'此事容我再想'"
  ```
**旧命令别名**：（新增，细化自 /检查一致性）

#### `/检查 --时间线`

**查询路径**：`00_memory/story_graph.json` §timeline
**输出**：时间线冲突列表 + 建议修正
**旧命令别名**：`/时间线`（原命令职能合并）

#### `/检查 --设定`

**功能**：检查世界观规则 / 力量体系 / 地理一致性
**查询路径**：`00_memory/story_graph.json` 的 worldrule / power_system 节点
**旧命令别名**：（新增）

#### `/检查 --伏笔`

**功能**：扫描本章的伏笔埋设/回收/超期
**查询路径**：`00_memory/foreshadow_ledger.md`（若存在，P0 方向将落地）
**输出**：
  ```yaml
  planted_this_chapter: ["F-042"]
  redeemed_this_chapter: ["F-011"]
  overdue_alert: ["F-008: 已 55 章未提醒"]
  ```
**旧命令别名**：`/伏笔状态`

#### `/检查 --文风`

**查询路径**：`references/advanced/humanizer-guide.md` + `00_memory/style_anchor.md`
**输出**：`style_calibration.md`
**旧命令别名**：`/风格校准`

#### `/检查 --骚话`

**功能**：审计本章骚话的密度 / 类型分布 / 人设匹配度
**查询路径**：
  1. `references/guides/saohua.md` §二 密度控制, §四 质量红线
  2. `references/guides/saohua.md` §七 题材矩阵
  3. `references/guides/saohua.md` §八 节奏曲线（如已进入进阶阶段）
**输出**：
  ```yaml
  density_actual: 5
  density_expected: "中 (2-3)"
  violation: "超标 67%"
  type_distribution: {A: 2, B: 1, D: 2}
  character_fit_issues: []
  ```
**旧命令别名**：（新增，合并自 /骚话密度）

#### `/检查 --节奏`

**查询路径**：`references/advanced/million-word-roadmap.md` §6 + §7
**输出**：节奏档位 / 配额违规 / 冷却窗违规
**旧命令别名**：`/节奏审查`

#### `/检查 --AI味`

**查询路径**：`references/advanced/humanizer-guide.md` 7 大 AI 写作模式 + 项目专项风险门禁
**脚本**：
  - 单章通用检测：`python3 scripts/text_humanizer.py detect --chapter-file <文件>`
  - 批量专项门禁：`python3 scripts/text_humanizer.py risk <章节文件或目录> --fail-on fail`
**输出**：`copyedit_report.md` 的 AI 味章节；批量扫描可额外输出 `04_editing/AI风险门禁报告.md`
**阻断规则**：critical 事故必阻断；同章高危模板重复命中或模板权重超过阈值才阻断。短段比例、字数偏低、解释性句子默认只作为 warning/info，避免误伤网文短段节奏。
**旧命令别名**：（细化自 /校稿）

#### `/检查 --读者`

**功能**（v1.2.0 引入，门禁第 6 维度）：模拟典型读者审稿，给出追读力 / 章末钩子 / 出戏检测 / 弃书风险点
**查询路径**：
  1. `references/advanced/reader-simulator-spec.md`（完整契约 + 6 子分项 + 读者画像）
  2. `02-写作计划.json` 的 `readerProfile` 字段
  3. `<项目>/03_manuscript/<本章及最近 5 章>` 用作上下文
  4. `<项目>/01-大纲.md` 用于回报感评估
**脚本**：`python3 scripts/reader_simulator.py --project-root <目录> --chapter <章号>`
**输出**：
  - `04_editing/gate_artifacts/<章号>/reader_report.md`（含总分 + 6 子分 + 弃书风险点 + 修复建议）
  - 同步回写 `02-写作计划.json` 的 `chapters[N].gateScores.reader`
**通过线**：`gateThresholds.reader`（默认 70 分）；番茄模式中该分数只作 advisory，节点复盘时人工读取，不作为单章硬阻断
**旧命令别名**：（新增）

---

### 3.5 `/门禁` 主命令

#### `/门禁 --预检`

**功能**：写前自检；专业模式以章节控制卡为主，不再依赖未落地的 YAML 预检
**脚本**：`python3 scripts/chapter_control_card.py generate --project-root <目录> --chapter <章号>`
**输出**：`04_editing/control_cards/chNNN-control-card.md`
**旧命令别名**：（新增）

#### `/门禁 --运行`

**功能**：执行门禁结算；番茄项目默认轻门禁，专业模式执行控制卡 + 六步门禁结算
**自动子流程**：校验章节控制卡 → `/检查 --记忆` → `/检查 --一致性` → `/检查 --文风` → `/门禁 --校稿` → `/检查 --读者` → `/门禁 --运行` 本身生成 `gate_result.json`
**脚本**：`python3 scripts/chapter_gate_check.py --project-root <目录> --chapter-file <文件>`
**番茄模式**：当 `02-写作计划.json.platform == "fanqie"` 时，脚本输出 `gate_mode: fanqie`，只硬卡控制卡、安全合规、首段钩子、章末追读点、正典回写与 AI 高危风险；读者分为 advisory
**旧命令别名**：`/门禁检查`

#### `/门禁 --结算`

**功能**：对比控制卡承诺 vs 章节实际；当前由 `/门禁 --运行` 的 `dimensions.control_card` 先做存在性/结构校验，人工结算可写入 `reconciliation.md`
**输出**：`reconciliation.md`（可选）或 `gate_result.json.dimensions.control_card`
**旧命令别名**：（新增）

#### `/门禁 --修复`

**功能**：门禁失败后生成最短修复路径
**脚本**：`python3 scripts/gate_repair_plan.py --project-root <目录> --chapter-file <文件>`
**输出**：`repair_plan.md`
**旧命令别名**：`/修复本章`（与 `/章 --修复` 同义）

---

### 3.6 `/检索` 主命令

#### `/检索 --剧情 <查询>`

**查询路径**：`references/advanced/million-word-roadmap.md` §11
**脚本**：`python3 scripts/plot_rag_retriever.py query --project-root <目录> --query "<描述>" --top-k 4 --candidate-k 12 --auto-build`
**输出**：`00_memory/retrieval/next_plot_context.md`
**旧命令别名**：`/剧情检索`

#### `/检索 --伏笔 [--状态 <planted|redeemed|expired>]`

**查询路径**：`00_memory/foreshadow_ledger.md`
**输出**：筛选后的伏笔列表
**旧命令别名**：`/伏笔状态`

#### `/检索 --角色 [<角色名>]`

**查询路径**：`00_memory/story_graph.json` §character 节点
**输出**：指定角色或全部角色的当前状态
**旧命令别名**：`/角色状态`

#### `/检索 --时间线 [<时间范围>]`

**查询路径**：`00_memory/story_graph.json` §timeline
**旧命令别名**：（与 `/检查 --时间线` 区分：检索是读，检查是审）

#### `/检索 --索引重建 [--full]`

**脚本**：`python3 scripts/plot_rag_retriever.py build --project-root <目录>`（默认增量，`--full-rebuild` 全量）
**旧命令别名**：`/更新剧情索引`

---

### 3.7 `/风格` 主命令

#### `/风格 --题材 <题材名>`

**查询路径**：`references/advanced/million-word-roadmap.md` §12
**旧命令别名**：`/题材选风格`

#### `/风格 --提取 <样章文件>`

**旧命令别名**：`/风格提取`

#### `/风格 --仿写 <样章文件...>`

**旧命令别名**：`/仿写`

#### `/风格 --拆书 <作品>`

**旧命令别名**：`/拆书`

#### `/风格 --校准`

**功能**：检测本章文风偏移（不修复，只报告）
**旧命令别名**：`/风格校准`（同时保留在 `/检查 --文风`）

#### `/风格 --迁移 <目标风格>`

**旧命令别名**：`/风格迁移`

---

### 3.8 `/骚话` 主命令

> 骚话子系统专属。详见 `references/guides/saohua.md`（单文件覆盖所有层级）。

#### `/骚话 --扫描`

**功能**：扫描当前章 beat sheet 或大纲片段，推荐骚话插入点
**查询路径**：
  1. `references/guides/saohua.md` §三 场景触发矩阵
  2. `references/guides/saohua.md` §七 题材矩阵
  3. `00-人物档案.md` 各角色骚话人设卡
  4. `00_memory/foreshadow_ledger.md` 筛选 `SH-` 前缀（若存在）
**输出**：
  ```yaml
  scan_result:
    - beat_id: 3
      triggers: ["装逼打脸", "毒舌吐槽"]
      priority: P0
      recommended_templates: [A7, B1]
      character_fit: "李承乾-冷面毒舌 ✓"
      foreshadow_hook: SH-002
  ```
**失败条件**：无触发点 → 返回空列表 + 建议改为低密度档
**旧命令别名**：`/骚话`

#### `/骚话 --生成 <类型编号>`

**功能**：按指定类型（如 A7、D4、H11）生成候选骚话台词
**输入**：
  - 必需：类型编号（A1-H12 共 86 项，见 saohua.md §一）
  - 可选：上下文段落、目标角色名
**查询路径**：
  1. `saohua.md` §一 对应分类（按字母 A-H 定位）
  2. `saohua.md` §六 十大名场面（若在名场面内）
**输出**：3-5 条候选台词 + 每条的"铺垫→引爆→回响"三层建议
**旧命令别名**：`/骚话生成`

#### `/骚话 --密度 [--设定 <高|中|低>]`

**功能**：查询或设定当前章节骚话密度档
**查询路径**：`saohua.md` §二 密度三档
**输出**：当前档位 + 推荐句数区间 + 密度自动判定建议
**副作用**（--设定时）：写入 `04_editing/pre_chapter/<章号>/self_check.yaml` 的 `8_saohua.density` 字段
**旧命令别名**：`/骚话密度`

#### `/骚话 --人设 <角色名> [--建立|--更新|--查询]`

**功能**：管理角色骚话人设卡
**查询路径**：`saohua.md` §五 角色骚话人设卡
**输出**：角色骚话风格 / 常用句式 / 禁用句式 / 频率 / 成长弧线
**副作用**（建立/更新）：写入 `00-人物档案.md` 对应角色的 `骚话人设` 小节
**旧命令别名**：`/骚话人设`

#### `/骚话 --伏笔`

**功能**：查看所有 `SH-` 前缀的骚话伏笔状态
**查询路径**：`00_memory/foreshadow_ledger.md`（若存在）
**输出**：已埋/发酵/已回收/超期的骚话伏笔列表
**旧命令别名**：（新增，与 `/检索 --伏笔` 的 `SH-` 子集等价）

#### `/骚话 --审计 [--起始章 <N>] [--终止章 <M>]`

**功能**：跨章骚话审计（节奏曲线 / 类型分布 / 人设一致性 / 伏笔回收率）
**查询路径**：
  1. `references/guides/saohua.md` §十二 跨章检查清单
  2. 章节范围内所有 `/检查 --骚话` 的结果聚合
**输出**：
  ```yaml
  rhythm_curve: "波峰间距 4 章 ✓"
  type_coverage: {A: 12, B: 8, ..., H: 3}
  character_consistency: "李承乾 ✓ / 魏征 ⚠ 后期句式突变"
  foreshadow_redeem_rate: "3/4 (75%)"
  suggestions: ["SH-004 已 45 章未提醒，建议下章插入提醒"]
  ```
**旧命令别名**：（新增）

#### `/骚话 --对决 <角色A> <角色B>`

**功能**：为指定两角色生成骚话对决剧本（五阶段节奏）
**查询路径**：`saohua.md` §十 多人骚话对决
**输出**：按"开局试探→升温交锋→关键转折→压制反扑→终结"五阶段填充的对决 beat
**旧命令别名**：（新增）

---

### 3.10 `/面板` 主命令（v1.2.0 新增）

> 跨章质量趋势与项目状态可视化。详见 `references/advanced/quality-dashboard-spec.md`。

#### `/面板 --质量 [--范围 N-M] [--窗口 N] [--维度 <name>] [--格式 cli|json|md|csv]`

**功能**：输出全书质量趋势仪表盘，含五维度趋势 + 读者 6 子项 + 拐点告警 + 离群/高光章
**查询路径**：`02-写作计划.json` 的 `chapters[].gateScores`
**脚本**：`python3 scripts/quality_dashboard.py --project-root <目录> [参数]`
**输出**：CLI 表格 + ASCII 折线（默认）或指定格式文件
**适用**：每 5 章复盘 / 每卷收尾 / 改纲前决策
**旧命令别名**：（新增）

#### `/面板 --读者 [--范围 N-M]`

**功能**：仅输出读者维度的 6 子项趋势（章末钩子/追读力/意外感/沉浸度/回报感/传播性）
**脚本**：`python3 scripts/quality_dashboard.py --project-root <目录> --dimension reader`
**输出**：CLI 表格 + 6 子项折线图
**适用**：专项诊断读者体验趋势
**旧命令别名**：（新增）

#### `/面板 --状态`

**功能**：输出项目总体状态概览（进度 / 总字数 / 门禁通过率 / 最近 5 章质量）
**脚本**：`python3 scripts/quality_dashboard.py --project-root <目录> --summary`
**输出**：简要表格（仅顶层概览，不含详细趋势）
**适用**：快速查看项目健康度
**旧命令别名**：（新增）

---

### 3.11 `/研究` 主命令

#### `/研究 --搜索 <关键词>`

**查询路径**：`references/advanced/million-word-roadmap.md` + 外部可信来源 + 用户提供资料
**旧命令别名**：`/联网调研`

#### `/研究 --注入 <文件>`

**功能**：将外部检索结果注入知识库

#### `/研究 --验证 <陈述>`

**功能**：对书中某条陈述做事实核查

---

## 四、向后兼容别名表

旧命令在 3-6 个月过渡期内仍可使用。所有旧命令都自动路由到新形式。

| 旧命令 | 新形式 |
|--------|--------|
| `/一键开书` | `/书 --开书` |
| `/写全篇` | `/书 --规划` |
| `/改纲续写` | `/书 --改纲` |
| `/继续写` | `/章 --续写` |
| `/写作` | `/章 --写` |
| `/续写` | `/章 --续写` |
| `/批量写作` | `/章 --批量` |
| `/修改章节` | `/章 --修改` |
| `/修复本章` | `/章 --修复` 或 `/门禁 --修复` |
| `/更新记忆` | `/检查 --记忆` |
| `/检查一致性` | `/检查 --一致性` |
| `/风格校准` | `/检查 --文风` 或 `/风格 --校准` |
| `/校稿` | `/检查 --AI味` + `/门禁 --运行` |
| `/门禁检查` | `/门禁 --运行` |
| `/节奏审查` | `/检查 --节奏` |
| `/剧情检索` | `/检索 --剧情` |
| `/更新剧情索引` | `/检索 --索引重建` |
| `/伏笔状态` | `/检索 --伏笔` |
| `/角色状态` | `/检索 --角色` |
| `/时间线` | `/检索 --时间线` |
| `/联网调研` | `/研究 --搜索` |
| `/题材选风格` | `/风格 --题材` |
| `/风格提取` | `/风格 --提取` |
| `/仿写` | `/风格 --仿写` |
| `/拆书` | `/风格 --拆书` |
| `/风格迁移` | `/风格 --迁移` |
| `/骚话` | `/骚话 --扫描` |
| `/骚话生成` | `/骚话 --生成` |
| `/骚话密度` | `/骚话 --密度` |
| `/骚话人设` | `/骚话 --人设` |

---

## 五、Agent 执行协议

### 5.1 命令解析顺序

Agent 接收到命令后，按以下顺序处理：

1. **识别命令形态**：
   - 新形式（`/主 --子 参数`）→ 直接查 §三
   - 旧形式（`/XXX`）→ 查 §四别名表转换 → 再查 §三
2. **加载契约**：定位到 §三 对应子命令条目
3. **顺序读取"查询路径"中的所有文件/章节**（**这是强制步骤**，禁止跳过）
4. **按"输出格式"准备结构化输出**
5. **若有"副作用"**：写入指定文件前，确认用户授权（或自动模式下直接写）
6. **若命中"失败条件"**：按 §六 失败处理

### 5.2 查询路径强制性

> **⚠️ 关键规则**：Agent 禁止仅凭记忆或训练知识执行命令。必须先读取契约中指定的查询路径，再产出输出。

理由：
- 项目文档随版本演进，Agent 记忆可能过时
- 跨 Agent 审核需要一致的事实源
- 用户自定义修改（如路线图中的题材矩阵）必须被尊重

### 5.3 输出格式规范

所有结构化输出优先使用 YAML（便于人类阅读和机器解析）。文本输出使用 Markdown。

YAML 字段命名规则：
- 蛇形命名（snake_case）
- 英文字段名（避免跨语言歧义）
- 中文仅用于字段值

---

## 六、失败处理

### 6.1 命令未知

- Agent 应返回：`未知命令 "/XXX"。已查别名表无匹配。建议命令：...（模糊匹配结果）`

### 6.2 查询路径缺失

- 某个 `references/*.md` 文件不存在：`命令依赖文件 {path} 不存在，可能项目未完成 {相关功能} 的初始化。建议先执行：...`

### 6.3 副作用前置条件缺失

- 如 `/门禁 --结算` 要求 `self_check.yaml` 存在：`需要先执行 /门禁 --预检 生成承诺书。`

### 6.4 子参数冲突

- 同主命令的子参数互斥。如 `/骚话 --扫描 --生成 A7` → 报错：`/骚话 的子参数互斥，一次只能选择一个。`

---

## 七、演进约束

### 7.1 新增子命令必须做的

1. 在本文件 §三 添加契约条目
2. 在 SKILL.md 命令表添加一行
3. 如有别名，在 §四 添加映射
4. 如依赖脚本，在本文件对应命令条目补充脚本参数与输出
5. 更新 phase*-*.md 中相关流程引用

### 7.2 弃用旧命令

- 先标记"弃用"（在本文件 §四 加 `(deprecated)` 标签）
- 保留别名 ≥ 3 个版本
- 发布 CHANGELOG 公告
- 最终从 §四 移除

### 7.3 版本标记

本文件顶部应维护 `contracts_version`，变更需递增：
- 新增子命令：patch (+0.0.1)
- 修改查询路径或输出格式：minor (+0.1.0)
- 重命名主命令或删除子命令：major (+1.0.0)

当前版本：`contracts_version: 1.0.0`
