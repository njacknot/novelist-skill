# 门禁产物规范

每章都必须在以下目录产生产物：
- `04_editing/gate_artifacts/<chapter_id>/`

必需文件（v1.2.0 起六维度，新增 `reader_report.md`）：
1. `memory_update.md`         — 由 `/检查 --记忆` 生成
2. `consistency_report.md`    — 由 `/检查 --一致性` 生成
3. `style_calibration.md`     — 由 `/检查 --文风` 生成
4. `copyedit_report.md`       — 由 `/门禁 --校稿` 生成
5. `publish_ready.md`         — 由 `/门禁 --校稿` 生成
6. **`reader_report.md`**     — 由 `/检查 --读者` 生成（v1.2.0 新增，详见 [reader-simulator-spec.md](./reader-simulator-spec.md)）
7. `gate_result.json`         — 由校验脚本自动生成

失败修复文件（门禁失败时生成）：
- `repair_plan.md`（由 `/章 --修复` 生成）

## 生成与校验顺序

1. `/检查 --记忆` 生成 `memory_update.md`
2. `/检查 --一致性` 生成 `consistency_report.md`
3. `/检查 --文风` 生成 `style_calibration.md`
4. `/门禁 --校稿` 生成 `copyedit_report.md` 与 `publish_ready.md`
5. **`/检查 --读者` 生成 `reader_report.md`**（v1.2.0 新增）
6. `/门禁 --运行` 执行脚本写入 `gate_result.json` + 同步 `02-写作计划.json` 的 `chapters[N].gateScores`
7. 失败时执行 `/章 --修复` 生成 `repair_plan.md`

## 通过标准

- 所有必需文件存在且非空。
- 文件修改时间不早于章节文件。
- `publish_ready.md` 必须包含发布关键词（默认：可发布/通过/PASS）。
- **`reader_report.md` 总分必须 ≥ `gateThresholds.reader`（默认 70）**。
- 章节文件必须为 `03_manuscript/*.md`。
- `02_knowledge_base/` 不得混入章节文件（例如 `第xx章*.md`）。

## gate_result.json schema（v1.2.0）

```jsonc
{
  "chapter_id": "01",
  "chapter_file": "03_manuscript/第01章-最后一班列车.md",
  "passed": true,
  "fail_reason": null,         // 失败时填，如 "reader_below_threshold: 65/70"
  "checked_at": "2026-04-24T11:23:05+08:00",
  "duration_seconds": 142,
  "dimensions": {
    "memory":      { "passed": true, "score": 90, "issues": 0 },
    "consistency": { "passed": true, "score": 85, "issues": 1 },
    "style":       { "passed": true, "score": 78, "issues": 2 },
    "copyedit":    { "passed": true, "score": 82, "issues": 0 },
    "reader":      { "passed": true, "score": 75, "subscores": { "end_hook": 85, "retention": 75, "surprise": 70, "immersion": 80, "payoff": 75, "share": 80 } }
  }
}
```

## 数据回写

`/门禁 --运行` 执行成功后，必须将 `dimensions` 同步写入 `02-写作计划.json` 的 `chapters[chapter_id-1].gateScores`，供 `quality_dashboard.py` 消费。详见 [quality-dashboard-spec.md](./quality-dashboard-spec.md)。
