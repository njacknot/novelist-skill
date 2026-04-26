#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章节控制卡生成与校验工具。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


REQUIRED_SECTIONS: tuple[str, ...] = (
    "章节身份",
    "本章任务",
    "回忆与回收压力",
    "冲突设计",
    "角色使用",
    "伏笔与禁止揭露",
    "场景单元",
    "文风/去 AI 任务",
    "风险扫描",
    "章末钩子",
)


def default_card_path(project_root: Path, chapter: int) -> Path:
    return project_root / "04_editing" / "control_cards" / f"ch{chapter:03d}-control-card.md"


def _load_plan(project_root: Path) -> Dict[str, Any]:
    path = project_root / "02-写作计划.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _find_plan_entry(plan: Dict[str, Any], chapter: int) -> Dict[str, Any]:
    for entry in plan.get("chapters") or []:
        try:
            if int(entry.get("chapterNumber") or entry.get("number") or 0) == chapter:
                return entry
        except (TypeError, ValueError):
            continue
    return {}


def _read_optional_snippet(path: Path, limit: int = 320) -> str:
    if not path.exists():
        return "未发现对应正典文件；本章写作前需先确认正典状态。"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return "正典文件为空；本章写作前需补齐当前状态。"
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("..." if len(text) > limit else "")


def render_card(project_root: Path, chapter: int, title: Optional[str] = None) -> str:
    plan = _load_plan(project_root)
    entry = _find_plan_entry(plan, chapter)
    chapter_title = title or str(entry.get("title") or f"第 {chapter:03d} 章")
    mission = str(
        entry.get("goal")
        or entry.get("summary")
        or entry.get("description")
        or "承接上一章状态，完成本章必要推进，不越级揭露核心谜底。"
    )
    hook = str(entry.get("hook") or entry.get("endingHook") or "以具体动作、物件或新信息留下下一章追读点。")
    state_snippet = _read_optional_snippet(project_root / "00_memory" / "novel_state.md")

    return "\n".join(
        [
            f"# 第 {chapter:03d} 章 · 控制卡",
            "",
            f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 控制卡路径：04_editing/control_cards/ch{chapter:03d}-control-card.md",
            "",
            "## 章节身份",
            "",
            f"第 {chapter:03d} 章：{chapter_title}。本卡是写作前承诺，门禁时用于核对本章是否漂移。",
            "",
            "## 本章任务",
            "",
            mission,
            "",
            "## 回忆与回收压力",
            "",
            f"写前先回读正典状态：{state_snippet}",
            "",
            "## 冲突设计",
            "",
            "本章至少保留一个可见冲突：目标、阻力、代价三者必须同时在场。",
            "",
            "## 角色使用",
            "",
            "主要角色要有明确欲望、遮掩或误判；对白和动作服务于人物立场，不只服务于解释信息。",
            "",
            "## 伏笔与禁止揭露",
            "",
            "可回收已到期伏笔；未到锚点的核心秘密只允许露出证据、误导或副作用，不直接公布答案。",
            "",
            "## 场景单元",
            "",
            "1. 进入场景并给出当下压力。",
            "2. 让角色做出选择或交换信息。",
            "3. 用代价、误会、物件或新线索收束。",
            "",
            "## 文风/去 AI 任务",
            "",
            "保留项目声线：用具体动作、现场细节和角色口吻替代抽象总结、万能情绪词和论文式连接。",
            "",
            "## 风险扫描",
            "",
            "重点检查剧情加速、角色动机漂移、重复模板句、旁白替角色总结、只解释不行动。",
            "",
            "## 章末钩子",
            "",
            hook,
            "",
        ]
    )


def generate_card(
    project_root: Path,
    chapter: int,
    output: Optional[Path] = None,
    title: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    project_root = project_root.expanduser().resolve()
    out_path = (output.expanduser().resolve() if output else default_card_path(project_root, chapter))
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"控制卡已存在：{out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_card(project_root, chapter, title), encoding="utf-8")
    return out_path


def _section_body(text: str, section: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(section)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def validate_card(card_file: Path) -> Dict[str, Any]:
    card_file = card_file.expanduser().resolve()
    if not card_file.exists():
        return {
            "passed": False,
            "card_file": str(card_file),
            "missing": True,
            "missing_sections": list(REQUIRED_SECTIONS),
            "empty_sections": [],
        }

    text = card_file.read_text(encoding="utf-8")
    missing_sections = [
        section
        for section in REQUIRED_SECTIONS
        if not re.search(rf"^##\s+{re.escape(section)}\s*$", text, re.MULTILINE)
    ]
    empty_sections = [
        section
        for section in REQUIRED_SECTIONS
        if section not in missing_sections and len(_section_body(text, section)) < 6
    ]
    return {
        "passed": not missing_sections and not empty_sections,
        "card_file": str(card_file),
        "missing": False,
        "missing_sections": missing_sections,
        "empty_sections": empty_sections,
        "section_count": len(REQUIRED_SECTIONS) - len(missing_sections),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="章节控制卡生成/校验工具（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="生成章节控制卡")
    gen.add_argument("--project-root", required=True)
    gen.add_argument("--chapter", required=True, type=int)
    gen.add_argument("--output", default=None)
    gen.add_argument("--title", default=None)
    gen.add_argument("--force", action="store_true", help="覆盖已存在控制卡")

    val = sub.add_parser("validate", help="校验章节控制卡")
    val.add_argument("--card-file", required=True)

    args = parser.parse_args(argv)
    try:
        if args.cmd == "generate":
            output = Path(args.output) if args.output else None
            path = generate_card(Path(args.project_root), args.chapter, output, args.title, args.force)
            print(f"控制卡已写入：{path}")
            return 0

        result = validate_card(Path(args.card_file))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["passed"] else 1
    except (FileExistsError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
