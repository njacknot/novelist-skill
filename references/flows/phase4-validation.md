# 第四阶段：自动校验与修复

**目标**：确保所有章节文件存在、控制卡/门禁结果可追踪；字数默认只统计，只有项目显式设置 `minWordsPerChapter > 0` 时才硬性阻断。

---

## 校验流程

### 1. 初始化校验

读取 `02-写作计划.json`，将项目 `status` 更新为 `"validating"`。

### 2. 逐章检查

对每一章执行以下检查：

1. **文件存在性**：检查 `filePath` 指定的文件是否存在
2. **控制卡检查**：确认 `04_editing/control_cards/chNNN-control-card.md` 存在且通过校验
   ```bash
   python scripts/chapter_control_card.py validate --card-file <项目路径>/04_editing/control_cards/chNNN-control-card.md
   ```
3. **字数检查**：使用脚本统计字数；如计划配置了硬下限，则传入该值
   ```bash
   python scripts/check_chapter_wordcount.py <章节文件路径> [minWordsPerChapter]
   ```
4. **门禁结算**：使用脚本生成/刷新 `gate_result.json`，并回写 `gateScores`；番茄项目会自动使用轻门禁
   ```bash
   python scripts/chapter_gate_check.py --project-root <项目路径> --chapter-file <章节文件路径> --chapter <NN>
   ```
5. **更新 JSON**：将 `wordCount`、`wordCountPass`、`gateScores` 写入对应章节记录

### 3. 汇总结果

- **全部通过**（所有章节文件存在，控制卡/门禁通过，且启用硬下限时 `wordCountPass == true`）→ 更新项目 `status` 为 `"completed"`，进入步骤5
- **有不通过** → 进入步骤4
- **番茄项目到达节点**：运行 `python scripts/fanqie_flow_policy.py --plan <项目路径>/02-写作计划.json`，如返回 `can_continue=false`，项目状态更新为 `"needs_fanqie_review"`，不得继续写新章

### 4. 自动修复（最多3轮）

对每个不通过的章节：

1. 将 `status` 设为 `"failed"`，`retryCount` 加 1
2. 回到第三阶段对该章节执行逐章创作流程（写前分析→撰写→润色→收尾）
3. 重写完成后重新检查控制卡、字数与门禁
4. 更新 `00_memory/novel_state.md` 与 `02-写作计划.json`

循环规则：
- 最多执行 **3轮** 校验-修复循环
- 超过3次仍不合格的章节，保留记录并将项目 `status` 更新为 `"needs_attention"`，不得标记为 `"completed"`
- 所有修复完成且复验通过后，才更新项目 `status` 为 `"completed"`

### 5. 完成报告

向用户展示创作完成总结：

```
📊 《[小说名称]》创作完成

总章数：[X] 章
总字数：[X] 字
完成率：[X]%

各章节状态：
✅ 第1章：[标题]（[字数]字）
✅ 第2章：[标题]（[字数]字）
...

项目文件夹：./novelist-projects/[timestamp]-[小说名称]/
```

如有不合格章节（超过3次重写仍未通过），报告标题使用“需要处理”，并标注：
```
⚠️ 第X章：门禁未通过（原因：[fail_reason]），已重试3次，项目状态：needs_attention
```
