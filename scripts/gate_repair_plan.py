#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 gate_result.json 和现有报告生成最短修复计划。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_chapter_wordcount import check_chapter
from text_humanizer import RiskDetector


def _chapter_from_file(path: Path) -> Optional[int]:
    match = re.search(r"第\s*0?(\d+)\s*章", path.name)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else None


def _artifact_dir(project_root: Path, chapter: int) -> Path:
    return project_root / "04_editing" / "gate_artifacts" / f"ch{chapter:03d}"


def _load_gate_result(artifact_root: Path) -> Dict[str, Any]:
    path = artifact_root / "gate_result.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"passed": False, "fail_reason": "gate_result_json_invalid"}


def _actions_from_gate(gate: Dict[str, Any]) -> List[str]:
    actions: List[str] = []
    for name, payload in (gate.get("dimensions") or {}).items():
        if payload.get("passed"):
            continue
        missing = payload.get("missing") or []
        if missing:
            actions.append(f"补齐 `{name}` 门禁产物：{', '.join(missing)}。")
            continue
        if name == "reader":
            actions.append("按 `reader_report.md §8` 优先修复 P0/P1，再重跑 `reader_simulator.py`。")
        elif name == "copyedit":
            actions.append("处理 copyedit/AI 风险失败项，优先修复 critical 与高危模板重复。")
        elif name == "fanqie_opening":
            actions.append("重写首段 300 字：给出即时冲突、异常信息、明确欲望或危险信号。")
        elif name == "fanqie_end_hook":
            actions.append("重写章末 1-3 段：用新线索、危险、误会或选择代价制造下一章追读点。")
        elif name == "canon_writeback":
            actions.append("先把本章事实变化写回 `00_memory/novel_state.md`，再重跑门禁。")
        elif name == "fanqie_safety":
            actions.append("处理番茄安全合规 P0 风险，改成非操作性、非露骨、非现实煽动表达。")
        elif name == "ai_risk":
            actions.append("处理 AI 高危模板或替换事故，优先恢复角色声线和具体动作。")
        else:
            actions.append(f"修复 `{name}` 维度报告中的失败项，并重新生成对应产物。")
    if gate.get("word_count_pass") is False:
        actions.append("如项目设置了硬性最低字数，按 beat 缺口扩写；否则将 `minWordsPerChapter` 置为 0 取消硬卡。")
    return actions


def render_repair_plan(project_root: Path, chapter_file: Path, chapter: int) -> str:
    artifact_root = _artifact_dir(project_root, chapter)
    gate = _load_gate_result(artifact_root)
    actions = _actions_from_gate(gate)

    word_result = check_chapter(str(chapter_file), gate.get("min_words"))
    risk = RiskDetector().detect_file(chapter_file)

    if risk.gate_status == "fail":
        actions.append("重写或替换 AI 风险门禁中的 fail 项；优先处理替换事故和重复致命模板。")
    if not actions:
        actions.append("未发现阻断项；如仍需修订，请从读者体验或人物声线做人工精修。")

    unique_actions = list(dict.fromkeys(actions))
    status = "通过" if gate.get("passed") else "未通过/未运行"

    lines = [
        f"# 第 {chapter:03d} 章 · 修复计划",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 章节文件：{chapter_file.name}",
        f"> 最近门禁：{status}",
        f"> 字数：{word_result['word_count']}（硬下限：{word_result['min_words'] or '未设置'}）",
        f"> AI 风险：{risk.gate_status} / {risk.ai_risk_score:.1f}",
        "",
        "## 最短修复路径",
        "",
    ]
    for idx, action in enumerate(unique_actions, 1):
        lines.append(f"{idx}. {action}")
    lines.extend([
        "",
        "## 复验命令",
        "",
        "```bash",
        f"python3 scripts/chapter_gate_check.py --project-root {project_root} --chapter-file {chapter_file}",
        "```",
        "",
    ])
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="门禁失败修复计划生成器（novelist）")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter-file", required=True)
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).expanduser().resolve()
    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not project_root.is_dir():
        print(f"错误：项目目录不存在 - {project_root}", file=sys.stderr)
        return 2
    if not chapter_file.exists():
        print(f"错误：章节文件不存在 - {chapter_file}", file=sys.stderr)
        return 2
    chapter = args.chapter or _chapter_from_file(chapter_file)
    if not chapter:
        print("错误：无法从文件名推断章节号，请传入 --chapter", file=sys.stderr)
        return 2

    artifact_root = _artifact_dir(project_root, chapter)
    artifact_root.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).expanduser().resolve() if args.output else artifact_root / "repair_plan.md"
    plan = render_repair_plan(project_root, chapter_file, chapter)
    output.write_text(plan, encoding="utf-8")
    print(f"修复计划已写入：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
