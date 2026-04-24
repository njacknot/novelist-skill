<div align="center">

# ✍️ novelist skill

**面向 Codex CLI / Gemini CLI 的中文小说全流程创作技能**

*一个 skill 覆盖短篇到百万字长篇：简易模式 + 专业模式双档切换*

[![Skill](https://img.shields.io/badge/Agent_Skills-Standard-blue)](https://github.com/obra/Skills)
[![Codex CLI](https://img.shields.io/badge/Codex_CLI-supported-success)](https://github.com/openai/codex)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-supported-success)](https://geminicli.com/docs/cli/skills/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## 📖 这是什么？

`novelist` 是一个遵循 [Agent Skills 开放标准](https://github.com/obra/Skills) 的中文小说创作技能，综合了 [`chinese-novelist-skill`](https://github.com/PenglongHuang/chinese-novelist-skill) 的清晰创作流程与 [`novel-creator-skill`](https://github.com/leenbj/novel-creator-skill) 的长篇强约束机制。

一份 SKILL、两档模式：

| 模式 | 适用规模 | 核心机制 |
|------|---------|----------|
| **简易模式**（默认） | 10–50 章 / 单章 3000-5000 字 | 三层问答 → 自动规划 → 串行/并行写作 → 字数校验 |
| **专业模式** `/专业模式` | 100 万字以上 | Iron Law + 五步门禁 + RAG 检索 + 知识图谱 + 大纲锚点 + 反向刹车 + 去 AI 味 |

---

## 🚀 快速开始

### 1. 安装

**Codex CLI**

```bash
git clone https://github.com/njacknot/novelist-skill.git ~/.codex/skills/novelist
```

**Gemini CLI**

```bash
git clone https://github.com/njacknot/novelist-skill.git ~/.gemini/skills/novelist
```

**项目级安装**（只在当前项目生效）

```bash
# 将 skill 克隆到项目的 .codex/skills/ 或 .gemini/skills/（也支持别名 .agents/skills/）
mkdir -p .agents/skills
git clone https://github.com/njacknot/novelist-skill.git .agents/skills/novelist
```

**一键跨工具安装脚本**

```bash
git clone https://github.com/njacknot/novelist-skill.git
cd novelist-skill
./scripts/install.sh --tool codex        # 或 gemini / claude-code / opencode / antigravity
```

详见 [INSTALL.md](INSTALL.md)。

### 2. 触发

安装完成后，在 Codex CLI 或 Gemini CLI 的对话里直接说：

```
用 novelist 帮我写一部悬疑小说
```

或：

```
/一键开书
```

CLI 会自动识别并激活本技能。

---

## ✨ 核心特性

### 🌿 简易模式（默认）

- **三层递进式问答**：Layer 1 必答（题材 / 主角 / 冲突）→ Layer 2 可选深度定制 → Layer 3 标题生成
- **偏好记忆**：`user-preferences.json` 跨项目学习你的写作偏好
- **中断续写**：扫描 `02-写作计划.json`，自动检测并从断点继续
- **三种写作模式**：逐章串行 / 子 Agent 并行 / Agent Teams（Claude Code 专属）
- **自动校验**：完稿后字数、连贯性自检，不合格自动重写（最多 3 轮）

### 🧱 专业模式（长篇强约束）

- **Iron Law**：6 条不可违反的铁律（章节闭环、开书确认、禁止元信息、禁止门禁失败绕过、禁止改纲、禁止剧情加速）
- **五步质量门禁**：更新记忆 → 检查一致性 → 风格校准 → 校稿 → 门禁检查
- **五层长期记忆**：门禁 + RAG 检索 + 知识图谱 + 大纲锚点 + 跨 Agent 审核
- **反向刹车 + 节奏配额**：禁止剧情加速，慢档/中档/快档三档制，A/B/C 配额每章至多 1 项
- **去 AI 味 humanizer**：两遍式润色，7 大 AI 写作模式逐一清除
- **多步流水线写作**：Beat Sheet → Beat 扩写 → 章节合成 → 门禁

### 🎯 创作技巧库（通用）

| 主题 | 文件 |
|------|------|
| 悬念钩子十三式 + 章首引子七式 | [references/guides/hook-techniques.md](references/guides/hook-techniques.md) |
| 十种开头技巧 + 打破读者预期 | [references/guides/chapter-guide.md](references/guides/chapter-guide.md) |
| 对话潜台词 + 人物声线 | [references/guides/dialogue-writing.md](references/guides/dialogue-writing.md) |
| 人物塑造（性格 + 缺陷 + 声线） | [references/guides/character-building.md](references/guides/character-building.md) |
| 情节结构（三幕式 / 英雄之旅 / 七点结构） | [references/guides/plot-structures.md](references/guides/plot-structures.md) |
| 字数不足时的扩充技巧 | [references/guides/content-expansion.md](references/guides/content-expansion.md) |

---

## 🗂️ 目录结构

```
novelist-skill/
├── SKILL.md                          # 技能主文档（Codex/Gemini 读取此文件）
├── README.md                         # 本文件
├── INSTALL.md                        # 详细安装说明
├── references/
│   ├── flows/                        # 简易模式 5 阶段流程
│   │   ├── phase0-initialization.md
│   │   ├── phase1-layer1-core.md
│   │   ├── phase1-layer2-customize.md
│   │   ├── phase1-layer3-title.md
│   │   ├── phase2-planning.md
│   │   ├── phase3-writing.md
│   │   ├── phase4-validation.md
│   │   └── shared-infrastructure.md
│   ├── guides/                       # 通用创作技巧
│   │   ├── hook-techniques.md
│   │   ├── chapter-guide.md
│   │   ├── dialogue-writing.md
│   │   ├── character-building.md
│   │   ├── plot-structures.md
│   │   ├── content-expansion.md
│   │   ├── character-template.md
│   │   ├── outline-template.md
│   │   ├── chapter-template.md
│   │   └── title-guide.md
│   └── advanced/                     # 专业模式强约束规范
│       ├── humanizer-guide.md
│       ├── anti-resolution-cooldown-spec.md
│       ├── beat-pipeline-spec.md
│       ├── outline-anchor-quota-spec.md
│       ├── story-graph-schema.md
│       ├── rag-consistency-design.md
│       ├── genre-style-matrix.md
│       ├── cross-agent-review-protocol.md
│       ├── editorial-team-protocol.md
│       ├── research-guide.md
│       ├── command-playbook.md
│       ├── gate-artifacts-spec.md
│       ├── million-word-roadmap.md
│       └── interactive-brainstorming-playbook.md
└── scripts/
    ├── check_chapter_wordcount.py    # 字数检查（简易模式必备）
    └── install.sh                    # 跨工具一键安装
```

---

## 📊 典型输出

### 简易模式（短中篇）

```
./novelist-projects/20260425-143000-午夜列车/
├── 00-人物档案.md
├── 01-大纲.md
├── 02-写作计划.json
├── 第01章-最后一班列车.md    (3247 字)
├── 第02章-消失的乘客.md      (3582 字)
└── ...
```

### 专业模式（百万字长篇）

```
./novelist-projects/20260425-190000-大唐逆子/
├── 00_memory/
│   ├── novel_plan.md
│   ├── novel_state.md
│   ├── idea_seed.md
│   ├── outline_anchors.json
│   ├── story_graph.json
│   └── retrieval/
├── 02_knowledge_base/
├── 03_manuscript/
│   └── 第001章_*.md ... 第800章_*.md
└── 04_editing/gate_artifacts/
    └── 第001章/
        ├── memory_update.md
        ├── consistency_report.md
        ├── style_calibration.md
        ├── copyedit_report.md
        └── gate_result.json
```

---

## 🎯 三大黄金法则

1. **展示而非讲述** — 用动作和对话表现，不要直接陈述
2. **冲突驱动剧情** — 每章必须有冲突或转折
3. **悬念承上启下** — 每章结尾必须留下钩子

---

## 🙏 致谢

本技能综合以下两个 Claude Code skill 的设计与文档：

- [`PenglongHuang/chinese-novelist-skill`](https://github.com/PenglongHuang/chinese-novelist-skill) — 三层递进式问答、偏好记忆、中断续写、三种写作模式
- [`leenbj/novel-creator-skill`](https://github.com/leenbj/novel-creator-skill) — Iron Law、五步门禁、RAG 检索、知识图谱、去 AI 味 humanizer、反向刹车

MIT License.
