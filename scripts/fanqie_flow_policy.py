#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""番茄连载流程守卫：节点复盘与写作模式约束。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CHECKPOINTS = (
    {
        "id": "opening_3_chapters",
        "label": "首3章评审",
        "min_chapters": 3,
        "min_words": 0,
        "review_prompt": "检查开篇300字、前三章主线承诺、人物欲望、题材标签兑现和章末追读点。",
    },
    {
        "id": "signing_20k",
        "label": "2万字签约包",
        "min_chapters": 0,
        "min_words": 20000,
        "review_prompt": "整理2万字签约包：简介、标签、前三章卖点、主线爽点、人物设定和低质AI风险。",
    },
    {
        "id": "second_review_50k",
        "label": "5万字二评修订",
        "min_chapters": 0,
        "min_words": 50000,
        "review_prompt": "复盘5万字前的留存风险、主线清晰度、爽点兑现和可持续日更节奏。",
    },
    {
        "id": "final_review_80k",
        "label": "8万字最终签约包",
        "min_chapters": 0,
        "min_words": 80000,
        "review_prompt": "整理8万字最终签约材料，确认后续30章主线、人物关系和更新计划。",
    },
)


def is_fanqie_project(plan: Dict[str, Any]) -> bool:
    values = [
        plan.get("platform"),
        plan.get("channel"),
        plan.get("targetPlatform"),
        plan.get("publishPlatform"),
    ]
    return any(str(value).lower() in {"fanqie", "番茄", "番茄小说"} for value in values if value)


def _completed_chapters(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        chapter
        for chapter in (plan.get("chapters") or [])
        if str(chapter.get("status") or "").lower() == "completed"
    ]


def _total_words(chapters: Iterable[Dict[str, Any]]) -> int:
    total = 0
    for chapter in chapters:
        try:
            total += int(chapter.get("wordCount") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _review_passed(plan: Dict[str, Any], checkpoint_id: str) -> bool:
    reviews = plan.get("fanqieReviews") or {}
    review = reviews.get(checkpoint_id) or {}
    return bool(review.get("passed"))


def pending_checkpoint(plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_fanqie_project(plan):
        return None
    completed = _completed_chapters(plan)
    chapter_count = len(completed)
    total_words = _total_words(completed)
    for checkpoint in CHECKPOINTS:
        if _review_passed(plan, checkpoint["id"]):
            continue
        if chapter_count >= checkpoint["min_chapters"] and total_words >= checkpoint["min_words"]:
            return {
                **checkpoint,
                "completed_chapters": chapter_count,
                "total_words": total_words,
            }
    return None


def evaluate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    if is_fanqie_project(plan) and plan.get("writingMode") == "subagent-parallel":
        issues.append("subagent_parallel_forbidden")
    checkpoint = pending_checkpoint(plan)
    return {
        "platform": "fanqie" if is_fanqie_project(plan) else str(plan.get("platform") or ""),
        "can_continue": not issues and checkpoint is None,
        "issues": issues,
        "checkpoint": checkpoint,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="番茄连载节点复盘与并行写作守卫")
    parser.add_argument("--plan", required=True, help="02-写作计划.json 路径")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        plan = json.loads(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：无法读取计划 - {exc}", file=sys.stderr)
        return 2

    result = evaluate_plan(plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["can_continue"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
