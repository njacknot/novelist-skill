# 百万字路线图（执行参考）

> 本文件是百万字项目的统一路线图，同时承载“规划中但尚未脚本化”的高级规范摘要。

## 1. 输入最小集

- 题材
- 一句话脑洞
- 主角目标
- 核心冲突
- 预期结局（可暂时模糊）

## 2. 结构化展开

1. 一句话脑洞 → 三句话卖点（冲突、代价、爽点）
2. 三句话卖点 → 三幕十二节点
3. 十二节点 → 卷级路线（建议 8-12 卷）
4. 卷级路线 → 章级冲刺（每卷 40-80 章）

## 3. 建议规模（可调）

- 总字数：200万 - 500万
- 单章字数：按剧情自然浮动，常规目标 1800 - 4500，允许短章低于 2200
- 每卷字数：20万 - 45万
- 每 10 章一次冲刺复盘

## 4. 每 10 章冲刺模板

- 本轮目标：
- 必达剧情点：
- 必回收伏笔：
- 风格约束：
- 风险清单：
- 验收标准（是否可进入下轮）：

## 5. 失控处理

- 若主线偏离：回滚到 `novel_plan.md` 最近稳定里程碑。
- 若人物漂移：强制以 `character_tracker.md` 为准重写冲突场景。
- 若风格飘移：立即执行 `/风格 --提取` + `/风格 --迁移`。

---

## 6. 大纲锚点与进度配额（规划中）

### 目标

避免 AI 在早期章节过度推进主线，确保章节推进符合长线配额。

### 核心约束

- 每章写前读取 `00_memory/outline_anchors.json`
- 注入配额提示：当前进度、允许推进范围、禁止揭露内容、必须保留张力
- 越界即门禁失败：提前揭露、过度解决、无悬念收尾

### 建议结构

- `total_chapters_target`
- `total_volumes`
- `current_chapter`
- `volumes[]`（卷级 must_not_reveal / must_achieve / foreshadows_to_plant）
- `current_node`（当前章 allowed_plot_range / forbidden_reveals / mandatory_tension）

### 计划脚本

```bash
python3 scripts/outline_anchor_manager.py init --project-root <目录>
python3 scripts/outline_anchor_manager.py check --project-root <目录> --chapter <章号>
python3 scripts/outline_anchor_manager.py advance --project-root <目录> --to-chapter <章号>
python3 scripts/outline_anchor_manager.py recalculate --project-root <目录>
```

---

## 7. 反向刹车与事件冷却（规划中）

### 反向刹车（Anti-Resolution）

- 非终局章节禁止解决主线核心冲突
- 每章至少新增一个未解决次要问题
- 章末必须有悬念元素（疑问/危机/转折）
- 允许解决次要冲突，但必须伴随新代价或新风险

### 事件矩阵与冷却

事件池建议：

- `conflict_thrill`
- `bond_deepening`
- `faction_building`
- `world_painting`
- `tension_escalation`

规则建议：

- 冲突爽点不得连续 > 2 章
- 每 5 章至少出现一次 `bond_deepening` 或 `world_painting`
- 每类事件有独立冷却窗口，冷却期内不得做主 beat

状态建议存储：`00_memory/event_matrix_state.json`

### 计划脚本

```bash
python3 scripts/event_matrix_scheduler.py status --project-root <目录>
python3 scripts/event_matrix_scheduler.py recommend --project-root <目录> --chapter <章号>
python3 scripts/event_matrix_scheduler.py record --project-root <目录> --chapter <章号> --types "conflict_thrill,bond_deepening"
```

---

## 8. Beat Sheet 流水线（规划中）

### 五步链路

1. Beat Sheet 生成（3-5 个 beat）
2. Beat 独立扩写（每 beat 600-1200 字）
3. 章节合成（过渡、时态、人称、钩子）
4. 进入门禁
5. 图谱回写

### 关键约束

- 每章至少 1 个冲突型 beat
- 不得连续 2 个同类型 beat
- 最后一个 beat 必须留下悬念或新问题
- 扩写时禁止提前引入后续 beat 冲突

### 计划脚本

```bash
python3 scripts/beat_sheet_generator.py --project-root <目录> --chapter-goal "<本章目标>" --beat-count 4
python3 scripts/beat_flesh_writer.py --project-root <目录> --beat-file <beat_sheet.json> --beat-id 1
python3 scripts/chapter_synthesizer.py --project-root <目录> --beats-dir <beats目录> --output <章节文件>
```

---

## 9. 正典优先、图谱/RAG 派生

长篇防漂移的第一来源不是图谱或检索，而是项目正典文件：

- `00_memory/novel_state.md`：当前剧情事实、角色状态、关系强度、未清债务
- `01-大纲.md`：主线、卷目标、章节承诺
- `00-人物档案.md`：角色底层欲望、缺陷、声线、禁区
- `00_memory/foreshadow_ledger.md`（若存在）：伏笔状态与回收窗口

每章通过门禁后，先更新这些正典文件，再重建 `story_graph.json` 与 `00_memory/retrieval/*`。如果 RAG 命中、图谱边或报告结论与正典冲突，先修正正典或明确改纲，再重新派生索引；不要让派生视图反向覆盖正典。

---

## 10. 知识图谱 Schema 与回写（规划中）

### 存储

- 图谱文件：`00_memory/story_graph.json`
- 顶层建议：`version`, `last_updated_chapter`, `nodes`, `edges`, `timeline`

### 节点类型建议

- `character`, `location`, `faction`, `item`, `event`, `foreshadow`, `worldrule`, `power_system`

### 边类型建议

- `ally`, `enemy`, `mentor`, `subordinate`, `romantic`
- `belongs_to`, `located_at`, `triggers`, `foreshadows`, `owns`

### 操作协议

- 每章写后：抽取增量节点/边 + 更新时间线 + 基础一致性校验
- 改纲时：标记受影响节点与边，生成级联更新报告
- 门禁一致性阶段：校验状态、地点、伏笔超期、关系强度变化

### 计划脚本

```bash
python3 scripts/story_graph_builder.py init --project-root <目录>
python3 scripts/story_graph_updater.py update --project-root <目录> --chapter <章节文件>
python3 scripts/story_graph_updater.py validate --project-root <目录>
python3 scripts/story_graph_updater.py cascade --project-root <目录> --changes <变更描述>
python3 scripts/story_graph_builder.py export --project-root <目录> --format mermaid
```

---

## 11. 长篇一致性 RAG（规划中）

### 结论

可行且有价值，但不能替代门禁。定位是“检索前置 + 质量后置”。

### 原则

- 元数据过滤（角色命中/章节号/关键词）
- 两级检索（候选池粗筛 + Top-K 精排）
- 小检索集（默认 `Top-K=4`）
- 增量更新索引（每章后）
- 条件触发（复杂剧情才检索）
- 片段优先，不回读整章
- 返回命中原因，保证可解释性

### 文件建议

- `00_memory/retrieval/story_index.json`
- `00_memory/retrieval/entity_chapter_map.json`
- `00_memory/retrieval/chapter_meta/*.meta.json`
- `00_memory/retrieval/next_plot_context.md`

### 推荐链路

1. 每章写后：`/检索 --索引重建`
2. 写下一章前：`/检索 --剧情`
3. 进入 `/章 --写`
4. 写后继续门禁链路

---

## 12. 题材风格矩阵（基线）

| 题材 | 推荐人称 | 句长节奏 | 对话占比 | 叙事侧重 | 风格关键词 |
|---|---|---|---|---|---|
| 玄幻升级 | 第三人称近景 | 中短句、强节拍 | 35%-50% | 成长、打脸、升级反馈 | 爽点密集、阶段性爆点 |
| 都市异能 | 第一/第三混合 | 短句快节奏 | 40%-60% | 现实压迫与反转 | 口语化、快反应 |
| 历史权谋 | 第三人称 | 中长句、慢起快收 | 25%-40% | 信息差、博弈链 | 克制、暗线推进 |
| 悬疑推理 | 第一/限制第三 | 短句+留白 | 20%-35% | 线索、误导、回收 | 冷静、精准、反转 |
| 科幻冒险 | 第三人称 | 中句稳定 | 20%-35% | 设定兑现、行动代价 | 具象、硬逻辑 |
| 女性言情 | 第一/第三 | 中句、情绪波峰 | 45%-65% | 关系演化、情绪递进 | 细腻、情感牵引 |
| 恐怖惊悚 | 第一人称优先 | 短句碎拍 | 15%-30% | 感官压力、未知升级 | 压迫感、悬置 |

### 选择规则

1. 先按题材选基线。
2. 再按目标读者年龄调整句长和信息密度。
3. 若有样章，优先服从样章风格特征；题材基线仅做边界约束。
4. 同题材出现多个候选风格时，优先选择“冲突表达更清晰”的方案。
