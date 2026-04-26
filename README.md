<div align="center">

# ✍️ novelist skill

**面向 Codex CLI / Gemini CLI 的中文小说全流程创作技能**

*一个 skill 覆盖番茄签约冲刺、短篇到百万字长篇：番茄模式 + 简易模式 + 专业模式*

[![Skill](https://img.shields.io/badge/Agent_Skills-Standard-blue)](https://github.com/obra/Skills)
[![Codex CLI](https://img.shields.io/badge/Codex_CLI-supported-success)](https://github.com/openai/codex)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-supported-success)](https://geminicli.com/docs/cli/skills/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## 📖 这是什么？

`novelist` 是一个遵循 [Agent Skills 开放标准](https://github.com/obra/Skills) 的中文小说创作技能，综合了 [`chinese-novelist-skill`](https://github.com/PenglongHuang/chinese-novelist-skill) 的清晰创作流程与 [`novel-creator-skill`](https://github.com/leenbj/novel-creator-skill) 的长篇强约束机制。

一份 SKILL、三档模式：

| 模式 | 适用规模 | 核心机制 |
|------|---------|----------|
| **番茄模式** `platform: fanqie` | 商业连载 / 签约冲刺 | 首3章 → 2万字 → 5万字 → 8万字节点复盘 + 轻门禁 + 串行正文 |
| **简易模式**（默认） | 10–50 章 / 单章自然浮动，允许短章低于 2200 字 | 三层问答 → 自动规划 → 串行写作 → 字数统计 |
| **专业模式** `/专业模式` | 100 万字以上 | Iron Law + 写前控制卡 + 六步门禁（v1.2.0） + RAG 检索 + 知识图谱 + 大纲锚点 + 反向刹车 + 去 AI 味 + 质量趋势仪表盘 |

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
- **两种写作模式**：逐章串行 / 子 Agent 并行
- **自动校验**：完稿后文件、字数、连贯性自检；字数默认只统计，配置硬下限后才阻断

### 🍅 番茄模式（商业连载）

- **节点复盘**：首3章、2万字、5万字、8万字自动停点，不一口气写完整本
- **轻门禁**：控制卡、安全合规、首段钩子、章末追读点、正典回写、AI 高危风险硬卡；读者模拟分只作建议
- **串行正文**：禁用章节正文并行，子 Agent 只能准备素材/beat/竞品拆解
- **题材适配**：爽文/打脸/轻松流可启用骚话系统，悬疑/现实/年代/种田/细腻女频默认改为角色声线与情绪钩子

### 🧱 专业模式（长篇强约束）

- **Iron Law**：6 条不可违反的铁律（章节闭环、开书确认、禁止元信息、禁止门禁失败绕过、禁止改纲、禁止剧情加速）
- **写前控制卡 + 六步质量门禁**（v1.2.0新增读者维度）：控制卡 → 更新记忆 → 检查一致性 → 风格校准 → 校稿 → **读者审稿** → 门禁检查
- **质量趋势仪表盘**（v1.2.0）：`/面板 --质量` 输出五维度趋势 + 读者 6 子项 + 拐点告警 + 离群/高光章
- **读者模拟审稿**（v1.2.0）：`/检查 --读者` 模拟网文老读者给出 6 子分章末钩子/追读力/意外感/沉浸度/回报感/传播性
- **正典优先的长期记忆**：`00_memory/novel_state.md` / 大纲 / 人物档案是正典，RAG 与知识图谱只做派生视图；门禁 + 控制卡 + 跨 Agent 审核负责防漂移
- **反向刹车 + 节奏配额**：禁止剧情加速，慢档/中档/快档三档制，A/B/C 配额每章至多 1 项
- **去 AI 味 humanizer**：清风险 + 回声线 + 自审，7 大 AI 写作模式逐一清除，并提供批量专项风险门禁
- **多步流水线写作**：Beat Sheet → Beat 扩写 → 章节合成 → 门禁

### 💥 网文骚话系统（通用）

- **八大分类**：装逼打脸 / 毒舌吐槽 / 撩人情话 / 霸气宣言 / 反讽自嘲 / 威胁恐吓 / 欲扬先抑 / 旁白骚评
- **密度三档控制**：高（4-6 句/章）/ 中（2-3 句）/ 低（0-1 句），根据章节类型自动判定
- **场景触发矩阵**：检测情节要素自动推荐骚话类型 + 优先级
- **题材×场景风格矩阵**：玄幻/都市/修仙/武侠/科幻/言情/历史 × 八大类型交叉匹配
- **十大名场面专题**：拍卖会 / 比武大会 / 退婚 / 宗门大比 / 商战 / 法庭 / 家族室会 / 敢死队谈判 / 救人 / 突破渡劫
- **六大组合技**：欲抑→打脸 / 毒舌→威胁 / 自嘲→宣言 / 情话→宣言 / 旁白→打脸 / 三重奏
- **跨章节奏曲线**：蓄力→爆发→冷却的 10/20 章弧编排模板
- **骚话伏笔系统**：预言式 / 回旋镖式 / 递进式三种伏笔类型 + 管理表
- **多人骚话对决**：五阶段对决节奏 + 主角vs反派 / 双雄 / 师生 / 多人混战四种模板
- **角色骚话人设卡**：每个角色独立的骚话风格 + 成长弧线
- **质量红线**：土味红线 / 出戏红线 / 密度红线 / 强行红线

### 🎯 创作技巧库（通用）

| 主题 | 文件 |
|------|------|
| 悬念钩子十三式 + 章首引子七式 | [references/guides/hook-techniques.md](references/guides/hook-techniques.md) |
| 十种开头技巧 + 打破读者预期 | [references/guides/chapter-guide.md](references/guides/chapter-guide.md) |
| 对话潜台词 + 人物声线 | [references/guides/dialogue-writing.md](references/guides/dialogue-writing.md) |
| 人物塑造（性格 + 缺陷 + 声线） | [references/guides/character-building.md](references/guides/character-building.md) |
| 情节结构（三幕式 / 英雄之旅 / 七点结构） | [references/guides/plot-structures.md](references/guides/plot-structures.md) |
| 字数不足时的扩充技巧 | [references/guides/content-expansion.md](references/guides/content-expansion.md) |
| **骚话完整系统**（单文件：86 模板 + 人设卡 + 名场面 + 题材矩阵 + 节奏 + 伏笔 + 对决 + 组合技） | [references/guides/saohua.md](references/guides/saohua.md) |
| 读者模拟审稿规范（v1.2.0） | [references/advanced/reader-simulator-spec.md](references/advanced/reader-simulator-spec.md) |
| 质量趋势仪表盘规范（v1.2.0） | [references/advanced/quality-dashboard-spec.md](references/advanced/quality-dashboard-spec.md) |

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
│   │   ├── phase1-questionnaire.md
│   │   ├── phase2-planning.md
│   │   ├── phase3-writing.md
│   │   ├── phase4-validation.md
│   ├── guides/                       # 通用创作技巧
│   │   ├── hook-techniques.md
│   │   ├── chapter-guide.md
│   │   ├── dialogue-writing.md
│   │   ├── character-building.md
│   │   ├── plot-structures.md
│   │   ├── content-expansion.md
│   │   ├── outline-template.md
│   │   ├── title-guide.md
│   │   ├── platform-rules.md         # 商业投稿：平台机制 / 违禁词 / 命名 / 标签
│   │   └── saohua.md                 # ★ 骚话完整系统（v1.3 单文件：模板+人设+名场+矩阵+节奏+伏笔+对决+组合技）
│   └── advanced/                     # 专业模式强约束规范
│       ├── humanizer-guide.md
│       ├── cross-agent-review-protocol.md
│       ├── command-contracts.md      # 命令契约 + 子命令路由（v1.1.0）
│       ├── gate-artifacts-spec.md    # 六步门禁产物规范（v1.2.0 新增 reader_report）
│       ├── million-word-roadmap.md   # ★ 统一路线图（含锚点/冷却/beat/图谱/RAG/题材矩阵规划）
│       ├── reader-simulator-spec.md  # ★ 读者模拟审稿规范（v1.2.0）
│       └── quality-dashboard-spec.md # ★ 质量趋势仪表盘规范（v1.2.0）
└── scripts/
    ├── check_chapter_wordcount.py    # 字数检查（简易模式必备）
    ├── text_humanizer.py             # 去 AI 味检测 + 批量专项风险门禁
    ├── command_alias.py              # 命令别名路由 + lint（v1.1.0 新增）
    ├── chapter_control_card.py       # 章节控制卡生成/校验
    ├── chapter_gate_check.py         # 门禁结算 + gate_result 回写
    ├── gate_repair_plan.py           # 门禁失败修复计划生成
    ├── fanqie_flow_policy.py         # 番茄节点复盘 + 正文并行守卫
    ├── plot_rag_retriever.py         # 剧情检索兼容入口
    ├── writeback_audit.py            # 续写/马拉松模式回写快照审计
    ├── reader_simulator.py           # ★ 读者模拟审稿（v1.2.0 新增）
    ├── quality_dashboard.py          # ★ 质量趋势仪表盘（v1.2.0 新增）
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
└── 04_editing/
    ├── control_cards/
    │   └── ch001-control-card.md
    ├── gate_artifacts/
    │   └── 第001章/
    │       ├── memory_update.md
    │       ├── consistency_report.md
    │       ├── style_calibration.md
    │       ├── copyedit_report.md
    │       ├── reader_report.md          # v1.2.0 新增
    │       └── gate_result.json
    └── dashboards/
        └── quality_YYYYMMDD.md           # v1.2.0 新增：周期性质量复盘
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
- [`leenbj/novel-creator-skill`](https://github.com/leenbj/novel-creator-skill) — Iron Law、门禁、RAG 检索、知识图谱、去 AI 味 humanizer、反向刹车

MIT License.
