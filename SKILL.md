---
name: novelist
description: |
  中文长篇小说全流程创作技能。覆盖从短中篇（10-50 章，每章 3000-5000 字）到百万字长篇（300 万字级）的完整创作链路。
  支持悬疑 / 言情 / 奇幻 / 科幻 / 武侠 / 历史 / 都市等题材。
  两档创作模式：**简易模式**（问答 → 规划 → 串行/并行创作 → 自动校验）、**专业模式**（Iron Law + 五步门禁 + RAG 剧情检索 + 知识图谱 + 大纲锚点 + 反向刹车 + 去 AI 味）。
  当用户要求：写小说、创作故事、续写章节、分章节写作、构思剧情、搭建世界观、仿写小说、去 AI 味润色时使用。
metadata:
  trigger: 创作中文小说、分章节故事、长篇小说创作、续写、仿写、去 AI 味
  source: 综合 chinese-novelist-skill 与 novel-creator-skill 的最佳实践
  version: 1.0.0
---

# Novelist: 中文小说创作技能

## 定位

一个面向 AI CLI 工具（Codex CLI / Gemini CLI / Claude Code / OpenCode / Antigravity 等遵循 Agent Skills 开放标准的工具）的中文小说创作技能。

- **简易模式**（默认）：适合 10–50 章、短中篇（单章 3000–5000 字）。通过三层递进式问答、自动规划、逐章串行/并行写作、字数校验完成整部作品。
- **专业模式**（可选 `/专业模式`）：适合 100 万字以上长篇。启用五步质量门禁、两级 RAG 剧情检索、知识图谱、大纲锚点、反向刹车与节奏配额、去 AI 味润色、跨 Agent 审核。

---

## 三大黄金法则（任何模式都适用）

1. **展示而非讲述** — 用动作和对话表现，不要直接陈述。
2. **冲突驱动剧情** — 每章必须有冲突或转折。
3. **悬念承上启下** — 每章结尾必须留下钩子（不允许空洞收尾）。

---

## Iron Law（专业模式强制铁律 — 不可违反）

以下约束在专业模式下无论用户如何要求都不得绕过：

- ⛔ **禁止跳过章节闭环**：每章必须依次执行"更新记忆 → 检查一致性 → 风格校准 → 校稿 → 门禁检查"。任何一步缺失即视为流程中断，门禁未通过禁止进入下一章。
- ⛔ **禁止绕过开书确认**：执行 `/一键开书` 前必须完成五要素确认（目标读者、写作风格、核心禁区、自动化等级、目标规模），并写入 `idea_seed.md`。
- ⛔ **禁止混淆正文与元信息**：正文中不得出现 `[说明]`、`（注：）`、`TODO`、写作分析段落、角色定位标记。出现立即触发 P0 重写。
- ⛔ **禁止门禁失败后继续写作**：`gate_result.json` 中 `passed != true` 时唯一合法操作是 `/修复本章`。
- ⛔ **禁止任意修改主线规划**：改纲必须显式执行 `/改纲续写` 并经用户确认。
- ⛔ **禁止剧情加速**：每章至多触发 A/B/C 配额中的 1 项（A 主线矛盾实质推进 / B 主要关系决定性升级 / C 核心秘密完整揭露）。同时触发 ≥2 项 = 越界。

> **简易模式**可以选择性套用这些铁律（推荐至少套用"章节闭环中的字数检查与去 AI 味润色"）。

---

## 简易模式：五阶段流程

进入每个阶段前，先阅读对应的流程文档以获取详细执行指令。

### 第 0 阶段：初始化与偏好加载

读取用户偏好（`user-preferences.json`），检测未完成项目（中断续写），展示个性化欢迎。
→ 详见 [references/flows/phase0-initialization.md](references/flows/phase0-initialization.md)

### 第 1 阶段：三层递进式问答

通过递进式问答收集创作需求，每个问题都支持"跳过"和"🎲随机生成"：

- **Layer 1 核心定位**（必答）：题材创意、主角设定、核心冲突 → [phase1-layer1-core.md](references/flows/phase1-layer1-core.md)
- **Layer 2 深度定制**（可选）：世界观、叙事视角、核心主题、读者定位、章节数量 → [phase1-layer2-customize.md](references/flows/phase1-layer2-customize.md)
- **Layer 3 标题生成**：AI 基于创意元素生成候选标题，用户确认 → [phase1-layer3-title.md](references/flows/phase1-layer3-title.md)

### 第 2 阶段：规划 + 二次确认

创建项目目录（`./novelist-projects/{timestamp}-{小说名称}/`），生成 `01-大纲.md`、`00-人物档案.md`、`02-写作计划.json`，展示规划摘要并请求用户确认。
→ 详见 [phase2-planning.md](references/flows/phase2-planning.md)

### 第 2.5 阶段：写作模式选择

| 模式 | 说明 | 适用 |
|------|------|------|
| **逐章串行** `serial` | 主 Agent 逐章写，稳定可靠 | 默认推荐 |
| **子 Agent 并行** `subagent-parallel` | 将章节分批派生子 Agent 并行写作 | 追求速度的中长篇 |
| **Agent Teams** `agent-teams` | Claude Code 多 Agent 协作（Gemini/Codex 不支持，会自动回退到 serial） | 大型长篇 |

### 第 3 阶段：疯狂创作（无需用户确认）

> 一旦进入此阶段，禁止再向用户确认。必须把整本小说创作完成才能向用户报告。

逐章执行：**写前分析 → 撰写（3000-5000 字，开头即高潮，章末留悬念）→ 深度润色去 AI 味 → 字数检查 → 更新章节摘要**。
支持中断续写（检测 `02-写作计划.json` 中的 `status`）。
→ 详见 [phase3-writing.md](references/flows/phase3-writing.md)

### 第 4 阶段：自动校验与修复（无需用户确认）

扫描所有章节 → 字数检查 → 连贯性检查 → 不合格章节自动重写（最多 3 轮）→ 生成完成报告。
→ 详见 [phase4-validation.md](references/flows/phase4-validation.md)

---

## 专业模式：长篇强约束机制

执行 `/一键开书` 或在简易模式中回复 `/专业模式` 切换到专业模式。

### 五步质量门禁（每章不可跳过）

| 步骤 | 命令 | 产物 |
|------|------|------|
| 1 | `/更新记忆` | `memory_update.md` |
| 2 | `/检查一致性` | `consistency_report.md` |
| 3 | `/风格校准` | `style_calibration.md` |
| 4 | `/校稿` | `copyedit_report.md` + `publish_ready.md` |
| 5 | `/门禁检查` | `gate_result.json`（`passed: true` 才解锁下一章） |

门禁失败后唯一合法操作是 `/修复本章`，由系统自动生成最短修复路径。

### 长期记忆（五层协同）

| 层 | 机制 | 用途 |
|----|------|------|
| 1 | 五步门禁 | 每章强制闭环 |
| 2 | RAG 剧情检索 | 两级（BM25 粗筛 + 语义精排）写前回读 |
| 3 | 知识图谱 | 节点+边+版本，改纲级联 |
| 4 | 大纲锚点 | 全局进度条 + 配额约束 |
| 5 | 跨 Agent 审核 | 独立审稿官批处理体检 |

详细规范：
- [references/advanced/outline-anchor-quota-spec.md](references/advanced/outline-anchor-quota-spec.md)
- [references/advanced/beat-pipeline-spec.md](references/advanced/beat-pipeline-spec.md)
- [references/advanced/anti-resolution-cooldown-spec.md](references/advanced/anti-resolution-cooldown-spec.md)
- [references/advanced/story-graph-schema.md](references/advanced/story-graph-schema.md)
- [references/advanced/humanizer-guide.md](references/advanced/humanizer-guide.md)

### 节奏配额三档制

- **慢档**：铺垫/羁绊，每 3–4 章至少 1 章，主线零推进
- **中档**：次要矛盾升温未爆发，占 ≥60%
- **快档**：主线突破，每卷 ≤ 2-3 次；快档后必须有慢/中档缓冲

---

## 命令表

### 新手命令（建议入口）

| 命令 | 功能 | 何时使用 |
|------|------|---------|
| `/一键开书` | 自动完成开书全流程（五要素确认 → 规划 → 首章准备） | 第一次开项目 |
| `/继续写` | 引导剧情走向 → 自动串行完整章节流程 | 日常推进章节 |
| `/修复本章` | 门禁失败后自动修复 | 门禁返回失败后 |
| `/简易模式` | 切换到简易流程（默认） | 按需 |
| `/专业模式` | 切换到长篇强约束模式 | 百万字级项目 |

### 创作命令

| 命令 | 功能 |
|------|------|
| `/写全篇` | 模糊想法 → 百万字路线图 |
| `/写作` | 生成单章草稿 |
| `/续写` | 恢复会话状态并继续 |
| `/批量写作` | 连续生成多章 |
| `/修改章节` | 修订已写章节并级联更新 |
| `/改纲续写` | 改纲 + 锚点重算 + 图谱级联 + RAG 重建 |
| `/一键写书` | 全自动写作调度 |

### 质量命令（专业模式每章必经）

| 命令 | 功能 |
|------|------|
| `/更新记忆` | 同步状态追踪器 |
| `/检查一致性` | 检查剧情/设定/时间线冲突 |
| `/节奏审查` | 语义级节奏审查（AI 自身执行，无需外部 API） |
| `/风格校准` | 检测文风偏移 |
| `/校稿` | 两遍式去 AI 味润色 |
| `/门禁检查` | 校验发布标准 |

### 检索与记忆命令

| 命令 | 功能 |
|------|------|
| `/剧情检索` | RAG 检索相关片段 |
| `/更新剧情索引` | 扫描章节建立索引 |
| `/伏笔状态` | 查看伏笔埋设/回收/超期 |
| `/角色状态` | 汇总角色当前状态 |
| `/时间线` | 查看事件时间顺序 |
| `/联网调研` | 联网搜索补充知识库 |

### 风格命令

| 命令 | 功能 |
|------|------|
| `/题材选风格` | 按题材矩阵选择基线风格 |
| `/风格提取` | 从样章提取风格到库 |
| `/仿写` | 提取写法模板与风格特征 |
| `/拆书` | 拆解作品结构，提炼爽点钩子 |

---

## 写作指南（references/guides/）

简易模式与专业模式共用的创作技巧：

- [hook-techniques.md](references/guides/hook-techniques.md) — 悬念钩子十三式 / 章首引子七式
- [chapter-guide.md](references/guides/chapter-guide.md) — 章节结构 / 十种开头技巧 / 打破读者预期
- [dialogue-writing.md](references/guides/dialogue-writing.md) — 对话潜台词 / 人物声线
- [character-building.md](references/guides/character-building.md) — 人物塑造（性格核心 / 致命缺陷 / 说话风格）
- [plot-structures.md](references/guides/plot-structures.md) — 情节结构（三幕式 / 英雄之旅 / 七点结构）
- [content-expansion.md](references/guides/content-expansion.md) — 字数不足时的扩充技巧
- [character-template.md](references/guides/character-template.md) / [outline-template.md](references/guides/outline-template.md) / [chapter-template.md](references/guides/chapter-template.md) / [title-guide.md](references/guides/title-guide.md)

---

## 共享机制

- 用户偏好系统（`user-preferences.json`，跨项目学习用户习惯）
- 写作计划 JSON（`02-写作计划.json`，进度跟踪 + 中断续写）
- 字数检查脚本（`scripts/check_chapter_wordcount.py`）
- 去 AI 味润色清单（专业模式必用，简易模式强烈推荐）

→ 详见 [shared-infrastructure.md](references/flows/shared-infrastructure.md)

---

## 典型输出目录

```
./novelist-projects/
├── user-preferences.json              # 跨项目偏好
└── 20260425-143000-午夜列车/          # 项目目录（简易模式）
    ├── 01-大纲.md                     # 故事概述 + 章节规划（7 列模板）
    ├── 00-人物档案.md                 # 主角/反派/配角档案
    ├── 02-写作计划.json               # 机器可读的章节状态
    ├── 第01章-最后一班列车.md
    ├── 第02章-消失的乘客.md
    └── ...
└── 20260425-190000-大唐逆子/          # 项目目录（专业模式，支持百万字）
    ├── 00_memory/                     # 长期记忆层
    │   ├── novel_plan.md              # 主线计划
    │   ├── novel_state.md             # 当前状态
    │   ├── idea_seed.md               # 五要素确认结果
    │   ├── outline_anchors.json       # 大纲锚点
    │   ├── story_graph.json           # 知识图谱
    │   └── retrieval/                 # RAG 索引
    ├── 02_knowledge_base/             # 设定与知识库
    ├── 03_manuscript/                 # 章节正文
    └── 04_editing/gate_artifacts/     # 门禁产物
```

---

## 使用提示

1. **没想好怎么开始？** 直接说「帮我写一部悬疑小说」就行，SKILL 会引导三层问答。
2. **已有完整想法？** 在第一句话里说清楚"题材 + 主角 + 冲突"，SKILL 会跳过重复问答直接进入规划。
3. **想写百万字长篇？** 开头加上 `/专业模式` 或 `/一键开书`，启用 Iron Law + 五步门禁 + 长期记忆。
4. **中断了？** 重新触发 SKILL 时会自动检测并提示"继续上次的《XXX》？"。
5. **写完发现不满意？** 用 `/修改章节` 或 `/改纲续写`，不要手动改 `novel_plan.md` 以免破坏级联索引。

---

> 本技能综合了 [chinese-novelist-skill](https://github.com/PenglongHuang/chinese-novelist-skill) 与 [novel-creator-skill](https://github.com/leenbj/novel-creator-skill) 的最佳实践，面向 Codex CLI 与 Gemini CLI 进行整合优化。
