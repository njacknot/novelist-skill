# 第二阶段：规划 + 二次确认

> **前置条件**：本阶段使用 Phase 1（`phase1-questionnaire.md`）中“标题确认”步骤产出的小说标题。标题信息从对话上下文中获取，用于命名项目目录、写入大纲文件头和写作计划 JSON。

执行以下步骤：

1. **创建项目文件夹**：`./novelist-projects/{YYYYMMDD-HHmmss}-{已确认标题}/`（相对当前工作目录，使用 Phase 1 最终确认的小说标题）
2. **生成人物档案**：创建 `00-人物档案.md`，参考 [character-building.md](../guides/character-building.md) 创建主角、反派、配角档案。**人物档案必须详细**：每个角色的性格核心、致命缺陷、说话风格/口头禅、恐惧/弱项、背景故事都要具体到可以直接指导写作的程度
3. **生成大纲**：创建 `01-大纲.md`，使用 [outline-template.md](../guides/outline-template.md) 模板，参考 [plot-structures.md](../guides/plot-structures.md) 填入完整的章节规划。**大纲必须以人物驱动情节** 参照 `00-人物档案.md`，确保情节服务于人物成长弧线
4. **生成写作计划**：创建 `02-写作计划.json`，基于大纲内容填充，结构如下（v1.2.0 起新增 `gateScores` / `gateThresholds` / `readerProfile`，向后兼容）：
   ```jsonc
   {
     "version": 2,
     "novelName": "[小说名称]",
     "projectPath": "./novelist-projects/{timestamp}-[小说名称]",
     "platform": "[fanqie|general|qidian|...]",  // 番茄商业连载填 fanqie
     "totalChapters": [章节数],
     "targetWordsPerChapter": [1800, 5000],
     "minWordsPerChapter": 0,
     "createdAt": "[ISO时间]",
     "updatedAt": "[ISO时间]",
     "status": "planning",
     "writingMode": "[serial|subagent-parallel]",

     // v1.2.0 新增：门禁阈值（缺省即采用默认 70 分通过线）
     "gateThresholds": {
       "memory": 70,
       "consistency": 70,
       "style": 70,
       "copyedit": 70,
       "reader": 70
     },
     // v1.2.0 新增：读者画像，单值或数组（详见 reader-simulator-spec.md §读者画像配置）
     "readerProfile": "webnovel_veteran",
     "fanqieReviews": {
       "opening_3_chapters": { "passed": false, "reviewedAt": null, "notes": "" },
       "signing_20k": { "passed": false, "reviewedAt": null, "notes": "" },
       "second_review_50k": { "passed": false, "reviewedAt": null, "notes": "" },
       "final_review_80k": { "passed": false, "reviewedAt": null, "notes": "" }
     },

     "chapters": [
       {
         "chapterNumber": 1,
         "title": "[章节标题]",
         "filePath": "第01章-[章节标题].md",
         "status": "pending",
         "wordCount": null,
         "wordCountPass": null,
         "retryCount": 0,

         // v1.2.0 新增：门禁完成后由 chapter_gate_check.py 回写
         "generatedAt": null,
         "lastUpdatedAt": null,
         "gateDurationSeconds": null,
         "gateScores": null,
         "tags": []
       }
     ]
   }
   ```

   **`gateScores` 字段结构**（章节门禁完成后回写，schema 详见 [gate-artifacts-spec.md](../advanced/gate-artifacts-spec.md) §gate_result.json schema）：

   ```jsonc
   "gateScores": {
     "memory":      { "score": 90, "passed": true, "issues": 0 },
     "consistency": { "score": 85, "passed": true, "issues": 1 },
     "style":       { "score": 78, "passed": true, "issues": 2 },
     "copyedit":    { "score": 82, "passed": true, "issues": 0 },
     "reader": {
       "score": 75, "passed": true,
       "subscores": { "end_hook": 85, "retention": 75, "surprise": 70, "immersion": 80, "payoff": 75, "share": 80 }
     }
   }
   ```

   该字段由 `quality_dashboard.py` 消费，跨章绘制趋势图；详见 [quality-dashboard-spec.md](../advanced/quality-dashboard-spec.md)。

完成后，执行以下两步：

**1. 展示规划摘要并请求确认**

向用户展示规划摘要（小说名称、总章数、目标字数、主要人物）并请求确认。

**2. 写作模式选择**（用户确认规划后）

使用 `AskUserQuestion` 询问：

```
Question: 选择写作模式
Options:
- 逐章串行（主 Agent 自己逐章写，全程无中断，适合短中篇）
- 子Agent并行（仅非番茄项目可用；番茄项目只能并行准备素材/beat，正文必须串行）
```

用户选择后：
- 更新 `02-写作计划.json` 的 `writingMode` 字段
- 若 `platform == "fanqie"`，强制 `writingMode = "serial"`，并在进入 Phase 3 前运行：
  ```bash
  python3 scripts/fanqie_flow_policy.py --plan <项目路径>/02-写作计划.json
  ```
- 更新 `status` 为 `"in_progress"`
- 进入第三阶段：疯狂创作 → 详见 [phase3-writing.md](phase3-writing.md)
