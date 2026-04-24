#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cross_agent_reviewer.py — 跨 Agent 双智能体审核工具（零外部依赖）

实现 references/advanced/cross-agent-review-protocol.md：
- review：生成单章审核 Prompt + 三维度结构化报告模板
- batch-review：生成批处理审核 Prompt
- unresolved：查看未解决问题列表
- parse：解析审核报告 → 提取 P0/P1/P2 问题

依赖：仅 Python 标准库（zero-dep）。
退出码：0 成功 / 1 有未解决问题 / 2 输入错误
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 审稿官人设 ─────────────────────────────

REVIEWER_PERSONA = """你是一位拥有十年网文阅读经验、对设定极其敏感的资深编辑。
你的唯一任务就是找茬。你绝不会说"写得不错"——你只关注问题。
你对以下问题零容忍：
- 时间线错乱和空间瞬移
- 设定吃书（前后矛盾）
- 历史/专业常识错误
- 节奏拖沓或爽点缺失
- AI味过重（翻译腔、过度总结、缺乏人物性格差异的对话）"""


# ───────────────────────────── 报告模板 ─────────────────────────────


REVIEW_TEMPLATE = """# 第 {chapter} 章 · 外部审核报告

> 审核时间：{timestamp}
> 审核轮次：第 {round} 轮
> 审核工具：{reviewer_tool}

---

## 维度一：逻辑与连续性硬伤

请逐条列出，每条标注：章节号、具体位置、严重等级（P0致命/P1严重/P2建议）

| # | 严重度 | 位置 | 类型 | 问题描述 | 修复建议 |
|---|:------:|------|------|---------|---------|
| 1 | P0/P1/P2 | 第X段 | 时间线/空间/设定/常识 | 具体问题 | 如何修复 |

## 维度二：阅读体验与节奏把控

- 连续多章无核心冲突？ □是 □否
- 爽点密度达标？ □是 □否
- 是否存在"水字数"段落？ □是 □否
- 情绪曲线合理？ □是 □否
- 章末钩子质量？ □强 □中 □弱

## 维度三：文笔去AI化

请列出具体出戏句子：

| # | 严重度 | 位置 | AI 模式类型 | 原文 | 修改建议 |
|---|:------:|------|-----------|------|---------|
| 1 | P0/P1 | 第X段 | 翻译腔/过度总结/对话同质/描写空洞/情感直白 | "原文" | "修改后" |

---

## 综合评定

- P0 问题数：
- P1 问题数：
- P2 问题数：
- 整体评分：/100
- 建议：□通过 □修复后通过 □强制重写
"""


def generate_review_prompt(
    chapter: int,
    chapter_content: str,
    context_chapters: str = "",
    reviewer_tool: str = "外部 Agent",
    round_num: int = 1,
) -> str:
    """生成单章审核 Prompt。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prompt = f"""# 审稿任务

{REVIEWER_PERSONA}

## 审核目标
- 章节：第 {chapter} 章
- 审核轮次：第 {round_num} 轮
- 时间：{timestamp}

## 前文摘要（供参考）
{context_chapters if context_chapters else '（无前文摘要）'}

## 待审正文

{chapter_content}

## 输出要求

请严格按以下模板输出审核报告，不要遗漏任何维度：

{REVIEW_TEMPLATE.format(
    chapter=chapter,
    timestamp=timestamp,
    round=round_num,
    reviewer_tool=reviewer_tool,
)}

## 重要规则
1. 每个问题必须给出具体位置（段落号或引用原文）
2. 必须区分 P0（致命）、P1（严重）、P2（建议）
3. 不要客气，不要说"整体写得不错"——只找问题
4. AI 味检测要精准：引用原文 + 给出具体修改建议
5. 如果本章确实没有问题，可以评 100 分并标注"通过"
"""
    return prompt


def generate_batch_review_prompt(
    project_root: Path,
    chapter_start: int,
    chapter_end: int,
) -> str:
    """生成批处理审核 Prompt。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prompt = f"""# 批处理审核任务（第 {chapter_start}-{chapter_end} 章）

{REVIEWER_PERSONA}

## 任务说明
请对第 {chapter_start} 到第 {chapter_end} 章进行批处理审核。
除了逐章审核的三个维度外，请额外检查：

1. **跨章节奏曲线**：{chapter_end - chapter_start + 1} 章跨度内的节奏曲线是否合理
2. **支线推进均衡性**：各支线是否均衡推进，有无被遗忘的支线
3. **伏笔密度**：是否有积压或遗忘的伏笔
4. **角色出场频率**：重要角色是否长期缺席

## 章节文件位置
请读取 `{project_root}/03_manuscript/` 下的第 {chapter_start}-{chapter_end} 章文件。

## 输出格式

### 逐章问题表

| 章号 | P0 数 | P1 数 | P2 数 | 最严重问题 |
|:----:|:-----:|:-----:|:-----:|-----------|

### 跨章分析

#### 节奏曲线评估
（描述 {chapter_end - chapter_start + 1} 章的节奏走势，是否有连续平淡或连续高潮）

#### 支线跟踪
（列出活跃支线和被遗忘的支线）

#### 伏笔审计
（列出已埋未收的伏笔，标注积压章数）

#### 角色出场频率
（列出重要角色最近出场章号，标注长期缺席的角色）

### 建议

按优先级排序的修复建议。

---

> 时间：{timestamp}
> 审核范围：第 {chapter_start}-{chapter_end} 章
> 产物路径：04_editing/batch_review_ch{chapter_start}-{chapter_end}.md
"""
    return prompt


# ───────────────────────────── 未解决问题管理 ─────────────────────────────


def _unresolved_path(project_root: Path) -> Path:
    return project_root / "04_editing" / "unresolved_issues.md"


def load_unresolved(project_root: Path) -> str:
    path = _unresolved_path(project_root)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def append_unresolved(project_root: Path, chapter: int, issues: List[str]) -> None:
    """追加未解决问题。"""
    path = _unresolved_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## 第 {chapter} 章（{timestamp}）\n\n"
    for iss in issues:
        entry += f"- [ ] {iss}\n"
    entry += "\n"

    with path.open("a", encoding="utf-8") as f:
        if path.stat().st_size == 0:
            f.write("# 未解决问题清单\n\n> 由 cross_agent_reviewer.py 自动生成\n")
        f.write(entry)


# ───────────────────────────── 报告解析 ─────────────────────────────


def parse_review_report(report_text: str) -> Dict[str, Any]:
    """解析审核报告，提取问题列表。"""
    issues: List[Dict] = []

    # 匹配表格行中的问题
    table_pattern = re.compile(
        r"\|\s*\d+\s*\|\s*(P[012])\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|"
    )
    for m in table_pattern.finditer(report_text):
        issues.append({
            "severity": m.group(1),
            "location": m.group(2).strip(),
            "type": m.group(3).strip(),
            "problem": m.group(4).strip(),
            "fix": m.group(5).strip(),
        })

    # 提取综合评分
    score_match = re.search(r"整体评分[：:]\s*(\d+)", report_text)
    score = int(score_match.group(1)) if score_match else None

    # 提取建议
    recommendation = "修复后通过"
    if "强制重写" in report_text:
        recommendation = "强制重写"
    elif "通过" in report_text and "修复" not in report_text:
        recommendation = "通过"

    p0 = [i for i in issues if i["severity"] == "P0"]
    p1 = [i for i in issues if i["severity"] == "P1"]
    p2 = [i for i in issues if i["severity"] == "P2"]

    return {
        "total_issues": len(issues),
        "p0_count": len(p0),
        "p1_count": len(p1),
        "p2_count": len(p2),
        "score": score,
        "recommendation": recommendation,
        "issues": issues,
    }


# ───────────────────────────── CLI ─────────────────────────────


def cmd_review(args: argparse.Namespace) -> int:
    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 章节文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    content = chapter_file.read_text(encoding="utf-8")
    chapter = args.chapter

    # 读取前文摘要
    context = ""
    if args.project_root:
        project_root = Path(args.project_root).expanduser().resolve()
        outline = project_root / "01-大纲.md"
        if outline.exists():
            context = outline.read_text(encoding="utf-8")[:2000]  # 截取前 2000 字

    prompt = generate_review_prompt(
        chapter=chapter,
        chapter_content=content,
        context_chapters=context,
        reviewer_tool=args.reviewer or "外部 Agent",
        round_num=args.round,
    )

    if args.output:
        Path(args.output).expanduser().write_text(prompt, encoding="utf-8")
        print(f"✅ 审核 Prompt 已写入: {args.output}", file=sys.stderr)
    else:
        print(prompt)

    return 0


def cmd_batch_review(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    start, end = args.chapter_start, args.chapter_end

    prompt = generate_batch_review_prompt(project_root, start, end)

    if args.output:
        Path(args.output).expanduser().write_text(prompt, encoding="utf-8")
        print(f"✅ 批处理审核 Prompt 已写入: {args.output}", file=sys.stderr)
    else:
        print(prompt)

    return 0


def cmd_unresolved(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    content = load_unresolved(project_root)

    if not content:
        print("✅ 无未解决问题", file=sys.stderr)
        return 0

    print(content)
    # 计算未勾选的 checkbox
    unchecked = content.count("- [ ]")
    checked = content.count("- [x]")
    print(f"\n未解决: {unchecked} / 已解决: {checked}", file=sys.stderr)
    return 1 if unchecked > 0 else 0


def cmd_parse(args: argparse.Namespace) -> int:
    report_file = Path(args.report_file).expanduser().resolve()
    if not report_file.exists():
        print(f"错误: 报告文件不存在 - {report_file}", file=sys.stderr)
        return 2

    text = report_file.read_text(encoding="utf-8")
    result = parse_review_report(text)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["p0_count"] > 0:
        print(f"\n🔴 {result['p0_count']} 个 P0 问题需要立即修复", file=sys.stderr)

        # 自动追加到 unresolved
        if args.project_root:
            p0_issues = [f"[P0] {i['problem']}" for i in result["issues"] if i["severity"] == "P0"]
            project_root = Path(args.project_root).expanduser().resolve()
            chapter = args.chapter or 0
            append_unresolved(project_root, chapter, p0_issues)
            print(f"   已追加到 04_editing/unresolved_issues.md", file=sys.stderr)

    return 1 if result["p0_count"] > 0 else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="跨 Agent 双智能体审核工具（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("review", help="生成单章审核 Prompt")
    pr.add_argument("--chapter-file", required=True)
    pr.add_argument("--chapter", type=int, required=True)
    pr.add_argument("--project-root", default=None)
    pr.add_argument("--reviewer", default=None, help="审核工具名")
    pr.add_argument("--round", type=int, default=1, help="审核轮次")
    pr.add_argument("--output", default=None)
    pr.set_defaults(func=cmd_review)

    pb = sub.add_parser("batch-review", help="生成批处理审核 Prompt")
    pb.add_argument("--project-root", required=True)
    pb.add_argument("--chapter-start", type=int, required=True)
    pb.add_argument("--chapter-end", type=int, required=True)
    pb.add_argument("--output", default=None)
    pb.set_defaults(func=cmd_batch_review)

    pu = sub.add_parser("unresolved", help="查看未解决问题")
    pu.add_argument("--project-root", required=True)
    pu.set_defaults(func=cmd_unresolved)

    pp = sub.add_parser("parse", help="解析审核报告")
    pp.add_argument("--report-file", required=True)
    pp.add_argument("--project-root", default=None)
    pp.add_argument("--chapter", type=int, default=None)
    pp.set_defaults(func=cmd_parse)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
