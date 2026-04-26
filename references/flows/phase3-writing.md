# 第三阶段：节点式创作

**重要**：普通项目可逐章推进直到计划完成；番茄项目必须在首3章、2万字、5万字、8万字节点停下复盘。

---

## 0. 启动检测与模式读取

开始创作前：
1. 读取 `02-写作计划.json`
2. 读取 `writingMode` 字段，进入对应模式流程
   - 若 `platform == "fanqie"`，先运行 `python3 scripts/fanqie_flow_policy.py --plan <项目路径>/02-写作计划.json`
   - 若返回 `can_continue=false`，停止写新章，先完成返回的 `checkpoint` 或修正 `writingMode`
3. 如果存在 `status: "in_progress"` 的章节 → 从该章节继续（中断续写）
4. 如果所有章节 `status: "pending"` → 从第 1 章开始
5. 如果存在 `status: "failed"` 的章节（Phase 4 回退）→ 从第一个 failed 章节开始

---

## 1. 逐章创作流程（通用，所有模式共用）

每章创作时严格执行以下步骤：

### 步骤 1: 写前分析（必须执行）

1. 读取 `02-写作计划.json` — 查看各章节状态，确定下一个待创作章节
2. **读取 `01-大纲.md`** — 找到当前章节的规划信息，提取：核心事件、承接上章、悬念钩子、出场人物、场景列表
2.5. **读取 `00-人物档案.md`** — 根据大纲中本章的「出场人物」列表，提取每个出场角色的：性格核心、致命缺陷、说话风格/口头禅、恐惧/弱项、与其他角色的关系
2.6. **读取正典状态** — 专业模式优先读取 `00_memory/novel_state.md`、`00_memory/foreshadow_ledger.md`（若存在）。这些文件是正典；RAG/图谱/报告只作为派生视图，冲突时以正典为准。
2.7. **生成/校验章节控制卡** — 写正文前必须落盘轻量控制卡：
   ```bash
   python3 scripts/chapter_control_card.py generate --project-root <项目路径> --chapter <NN>
   python3 scripts/chapter_control_card.py validate --card-file <项目路径>/04_editing/control_cards/chNNN-control-card.md
   ```
   控制卡用于锁定本章任务、回忆压力、冲突、角色欲望/遮掩、禁止提前揭露的信息与章末钩子；不要扩成大而全设定书。
2.8. **题材表达开关** — 先读取 `platform`、题材和 `styleProfile`：
   - 番茄都市爽文、玄幻打脸、轻松流：可启用骚话系统
   - 番茄悬疑、现实、年代、种田、女频细腻向：不跑完整骚话系统，改为检查“角色声线 / 情绪钩子 / 关系张力”
   - 非番茄项目：按项目风格选择是否启用
2.9. **骚话插入点分析（条件触发）**（参考 [saohua.md](../guides/saohua.md) — 单文件覆盖所有层级）— 仅在题材表达开关允许时执行：
   - 场景扫描：识别本章中的骚话触发场景（实力对比/反派嘲讽/异性互动/立志誓言等）— 见 saohua.md §三、触发矩阵
   - 密度判定：根据章节类型确定骚话密度档位（高/中/低）— 见 §二、密度控制
   - 类型匹配：为每个触发场景分配骚话类型（A-H 八大分类）— 见 §一、86 模板速查表
   - 角色匹配：检查角色骚话人设卡（如已建立），确保风格一致— 见 §五、角色骚话人设卡
   - 题材校准：骚话类型与题材匹配— 见 §七、题材×场景风格矩阵
   - 名场面识别：若本章属于名场面（拍卖会/比武/退婚等）— 见 §六、十大名场面编排
   - 跨章节奏：确认本章在骚话节奏曲线中的位置（蓄力/爆发/冷却）与伏笔回收— 见 §八 & §九
3. 更新 `02-写作计划.json` — 将本章 `status` 设为 `"in_progress"`

### 步骤 2: 撰写

4. 创建章节文件 — 文件名格式：`第{XX}章-{章节标题}.md`（标题来自 `02-写作计划.json` 中的 `title` 字段），按“章首引子→正文→章节备注”结构写作
5. **基于大纲规划创作** — 严格按照大纲中本章的核心事件和场景列表撰写正文
5.5. **撰写章首引子** — 按大纲中本章的章首引子类型，参考 [hook-techniques.md](../guides/hook-techniques.md)「章首引子七式」，创作 50-150 字的引子文字
6. 撰写正文 — **按 `targetWordsPerChapter` 的目标区间自然完成；允许短章低于 2200 字**。只有当 `02-写作计划.json.minWordsPerChapter > 0` 时，字数才作为硬门槛阻断。
   - 章首引子：已创作（步骤 5.5，参考 [hook-techniques.md](../guides/hook-techniques.md)「章首引子七式」）
   - 正文开头：第一段必须使用 [chapter-guide.md](../guides/chapter-guide.md) 十种开头技巧之一，建立即时冲突
   - 张力节奏：全章至少 2 个张力波峰，连续 500 字以上无冲突时必须引入新张力（参考 [hook-techniques.md](../guides/hook-techniques.md) 悬念强度等级）
   - 对话要求：每章至少 30% 对话内容，每段对话必须有潜台词或推进情节目的（参考 [dialogue-writing.md](../guides/dialogue-writing.md)）
   - 意外转折：每章至少 1 个读者预期之外的事件或信息（参考 [chapter-guide.md](../guides/chapter-guide.md)「打破读者预期」）
   - 人物一致性：对话和行为必须严格符合步骤 2.5 提取的角色设定（性格核心、缺陷、说话风格），角色不会做出不符合其性格的事（除非是刻意设计的成长/转变，且需要前文铺垫）
   - **题材表达**：若启用骚话，根据步骤 2.9 的分析结果插入；若未启用，改为强化角色声线、情绪钩子和关系张力，禁止为了金句破坏题材口吻
   - 内容不足但剧情未完成？使用 [content-expansion.md](../guides/content-expansion.md) 扩充技巧；短章已经完成叙事任务时不要为了凑字数注水
7. 设置结尾钩子 — 按大纲中本章的悬念钩子设计 → [hook-techniques.md](../guides/hook-techniques.md)「悬念钩子十三式」
8. **字数检查** — 必须使用脚本统计；若项目设置硬下限，则传入对应数值：`python scripts/check_chapter_wordcount.py <章节文件路径> [minWordsPerChapter]`

### 步骤 3: 撰写后优化

9. 连贯性检查 — 人物一致性、情节连贯、节奏控制
9.5. **张力检查** — 检查全章节奏是否有波峰波谷、对话是否有个性、是否有意外转折（参考 [hook-techniques.md](../guides/hook-techniques.md) 悬念强度等级和 [chapter-guide.md](../guides/chapter-guide.md)「打破读者预期」）
9.6. **控制卡对照** — 对照 `04_editing/control_cards/chNNN-control-card.md` 检查本章是否完成“本章任务”和“章末钩子”，是否越界揭露了控制卡禁止揭露的信息。
10. **深度润色（去除AI味）** — 重点检查并修改：
    - **去除过度修饰的形容词**：删减“璀璨”、“瑰丽”等AI常用词堆砌
    - **减少抽象陈述**：把“心中涌起复杂的情感”改为具体动作/对话
    - **打破四字格律**：避免“心潮澎湃、热血沸腾”等陈词滞调
    - **增加口语化表达**：人物对话要有个性
    - **优化节奏感**：长句短句交替
    - **细节具象化**：用具体细节替代笼统描述
    - **表达质量自查**：若本章启用骚话，检查是否匹配角色人设、铺垫和密度；若未启用，检查角色声线、情绪钩子和关系张力是否自然，禁止强行追求“截图级金句”
10.5. **读者视角预演**（写后先行，避免 Phase 4 批量回修）
    - 专业模式：必须执行 `/检查 --读者 --chapter <NN>`，按 [reader-simulator-spec.md](../advanced/reader-simulator-spec.md) 生成 `04_editing/gate_artifacts/<chapter_id>/reader_report.md`
    - 番茄模式：推荐执行，但 `reader.score` 只作 advisory，不作为每章硬门禁；首3章/2万字节点复盘时人工读取报告
    - 简易模式：推荐执行；若跳过则在 Phase 4 统一补跑
    - 6 子分写入 `02-写作计划.json` 的 `chapters[N].gateScores.reader.subscores`
    - 若 `reader.score < gateThresholds.reader`（默认 70）→ 按 `reader_report.md §8 修复建议` P0/P1 先行修复，修复后重跑 `/检查 --读者`
11. **字数检查** — 再次使用脚本确认；未设置硬下限时只记录字数

### 步骤 4: 收尾

12. 生成章节摘要 — 在 `01-大纲.md` 的章节摘要区追加（300-500字，保证连贯性参考）
13. 更新正典与计划 — 将本章摘要/角色状态/伏笔状态写回 `00_memory/novel_state.md` 等正典文件；再更新 `02-写作计划.json`，将本章 `status` 设为 `"completed"`，填入 `wordCount`
13.5. **质量趋势刷新**（批次/节点级）
    - 触发时机：番茄模式在首3章、2万字、5万字、8万字和每10章；专业模式每完成 5 章、一个子 Agent 批次结束、或一个卷（arc）完结时
    - 执行 `/面板 --质量 --project <项目路径>`，按 [quality-dashboard-spec.md](../advanced/quality-dashboard-spec.md) 生成六维趋势图
    - 仪表盘告警规则：
      - 任一维度连续 3 章下降 → 暂停创作，进入 `/章 --修复` 循环
      - 读者维度子分中 `end_hook_score` 或 `retention_score` 跌破 60 → 重写当章末尾
      - 总分连续 2 章低于 70 → 回滚到最近一次 ≥70 的章节重规划

---

## 2. 串行模式（writingMode: "serial"）

**主 Agent 自己逐章创作，全程不中断。**

### 自驱循环

```
WHILE 02-写作计划.json 中存在 status != "completed" 的章节:
    如果 platform == "fanqie": 运行 fanqie_flow_policy.py
    如果返回 can_continue=false: 停止，输出节点复盘任务
    执行「逐章创作流程」（步骤 1-4）
    ⚠️ 完成一章后，立即读取 JSON 认领下一章，不要向用户确认，不要停下来
普通项目所有章节完成 → 进入第四阶段：自动校验
番茄项目到达节点 → 输出复盘包，不进入下一章
```

### 马拉松/续写回写保护

长时间自动续写或外部 runner 调 `/章 --续写` 时，必须用快照确认“真的写回了项目文件”，避免模型只在 stdout 里说完成：

```bash
python3 scripts/writeback_audit.py snapshot --project-root <项目路径> --output <项目路径>/.flow/writeback-before.json
# 执行本轮续写 / 门禁 / 索引重建
python3 scripts/writeback_audit.py changed --project-root <项目路径> --before <项目路径>/.flow/writeback-before.json
```

如果 `changed` 返回未变化，停止本轮，不得把 stdout 文本当成章节完成。

**关键提醒（每章完成后必须遵守）**：
> 本章已完成。立即读取 `02-写作计划.json` 并运行流程守卫。普通项目继续认领下一个 pending 章节；番茄项目若到达节点，立即输出复盘包并停止，不进入下一章。

---

## 3. 子Agent并行模式（writingMode: "subagent-parallel"）

> 番茄项目禁用正文并行。`platform == "fanqie"` 时，子 Agent 只能做素材检索、竞品拆解、beat 候选或违禁词扫描，不能直接写入 `03_manuscript/`、`01-大纲.md`、`00_memory/novel_state.md`、`02-写作计划.json`。

**核心机制**（非番茄项目）：主 Agent 将章节分成不重叠的批次，每个批次派生一个子 Agent。批次内串行写作，批次间并行执行。

### 主 Agent 流程

```
1. 计算批次分配:
   - 每批 5-8 章（根据总章数动态调整）
   - 批次间不重叠
   - 示例: 30 章 → 5 批 × 6 章
2. 为每个批次派生子 Agent（使用 Agent 工具，多个批次可并行派生）:
   - 每个 Agent 内部串行执行「逐章创作流程」
3. 所有子 Agent 完成后 → 进入第四阶段：自动校验
```

### 子 Agent prompt 模板（并行模式）

```
你是一个小说批量创作 Agent。你需要创作第 {start} 章到第 {end} 章。

## 项目信息
- 项目路径: {projectPath}
- 你负责的章节: 第 {start} 章 到 第 {end} 章

## 创作步骤（对每一章依次执行）
1. **首先读取 {projectPath}/01-大纲.md**，找到当前章节的规划信息（核心事件、承接上章、悬念钩子、出场人物、场景列表）
1.5. **读取 {projectPath}/00-人物档案.md**，根据大纲中本章的「出场人物」，提取每个出场角色的：性格核心、致命缺陷、说话风格/口头禅、恐惧/弱项、与其他角色的关系
1.6. 读取 `00_memory/novel_state.md`（若存在），生成/校验 `04_editing/control_cards/chNNN-control-card.md`
2. 读取 02-写作计划.json，确认章节状态
3. 将当前章节 status 更新为 "in_progress"
4. 创建章节文件，文件名格式：`第{XX}章-{章节标题}.md`（标题来自 `02-写作计划.json` 的 `title` 字段），基于大纲规划撰写正文（按 `targetWordsPerChapter` 目标区间，允许短章低于 2200 字）
5. 按大纲中的章首引子类型，参考 hook-techniques.md「章首引子七式」创作章首引子（50-150字）
6. 正文开头第一段必须使用 chapter-guide.md 十种开头技巧之一
7. 全章至少 2 个张力波峰，连续 500 字以上无冲突必须引入新张力
8. 每章至少 30% 对话，对话必须有潜台词和角色个性，**对话风格必须符合人物档案中的设定**
9. 每章至少 1 个读者预期外的转折（参考 chapter-guide.md「打破读者预期」）
10. **人物行为必须严格符合提取的角色设定**（性格、缺陷、说话风格），角色不会做出不符合其性格的事
11. 结尾按大纲中的悬念钩子设计（参考 hook-techniques.md「悬念钩子十三式」）
7. 运行字数检查: python scripts/check_chapter_wordcount.py <文件路径> [minWordsPerChapter]
8. 深度润色（去除AI味）
8.5. 执行读者视角预演: python scripts/reader_simulator.py --project {projectPath} --chapter <NN>（生成 04_editing/gate_artifacts/<chapter_id>/reader_report.md，未达 70 分需按报告 §8 P0/P1 先行修复后重跑）
9. 再次字数检查
10. 在 01-大纲.md 追加 300-500 字章节摘要
11. 更新 `00_memory/novel_state.md` 与 status → "completed"，填入 wordCount + gateScores.reader
12. 立即继续下一章

## 重要约束
- 不要使用 AskUserQuestion，不要向用户确认任何事
- **每章开始前必须读取大纲**，严格按大纲的核心事件和悬念钩子创作
- 每章开始前必须有控制卡；门禁会校验 `04_editing/control_cards/chNNN-control-card.md`
- 默认不以 3000 字作为硬门槛；若项目设置 `minWordsPerChapter > 0`，才按该值阻断
- 你负责的所有章节必须全部完成

完成后报告: 各章编号、字数、是否通过字数检查
```

**并发安全**：非番茄项目每个子 Agent 负责不重叠的章节批次，只更新自己负责的章节状态；主 Agent 最后必须合并检查 `02-写作计划.json`、`01-大纲.md` 和 `00_memory/novel_state.md`。番茄项目不允许正文并行写入。
