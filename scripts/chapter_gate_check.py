#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter_gate_check.py — 章节门禁结算器。

职责：
- 读取章节正文、02-写作计划.json 和 gate_artifacts。
- 执行字数统计、AI 风险门禁、必需产物存在性校验、读者分校验。
- 番茄项目默认使用轻门禁：合规/开篇钩子/承诺提示/章末钩子/正典回写，读者分仅作建议。
- 写入 gate_result.json，并回写 02-写作计划.json 的章节状态与 gateScores。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_chapter_wordcount import check_chapter
from chapter_control_card import default_card_path, validate_card
from text_humanizer import RiskDetector


REQUIRED_ARTIFACTS: Dict[str, Tuple[str, ...]] = {
    "memory": ("memory_update.md",),
    "consistency": ("consistency_report.md",),
    "style": ("style_calibration.md",),
    "copyedit": ("copyedit_report.md", "publish_ready.md"),
}

FANQIE_OPENING_MARKERS = (
    "死", "血", "失踪", "报警", "秘密", "真相", "危险", "背叛", "欠债", "威胁",
    "突然", "忽然", "猛地", "竟然", "却", "但是", "不能", "不许", "十年前", "邮戳",
)

FANQIE_END_HOOK_MARKERS = (
    "？", "?", "……", "…", "突然", "忽然", "秘密", "真相", "门外", "敲门",
    "危险", "死", "血", "身份", "十年前", "坏了", "消失",
)

FANQIE_P0_PATTERNS = (
    r"具体自杀步骤",
    r"毒品制作",
    r"性行为(?:过程|细节)",
    r"教唆犯罪",
)


def _load_plan(project_root: Path) -> Tuple[Dict[str, Any], Path]:
    path = project_root / "02-写作计划.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到 02-写作计划.json：{path}")
    return json.loads(path.read_text(encoding="utf-8")), path


def _chapter_from_file(path: Path) -> Optional[int]:
    match = re.search(r"第\s*0?(\d+)\s*章", path.name)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else None


def _find_plan_entry(plan: Dict[str, Any], chapter: int, chapter_file: Path) -> Optional[Dict[str, Any]]:
    chapters = plan.get("chapters") or []
    for entry in chapters:
        try:
            if int(entry.get("chapterNumber") or entry.get("number") or 0) == chapter:
                return entry
        except (TypeError, ValueError):
            continue
    for entry in chapters:
        if Path(str(entry.get("filePath") or entry.get("file") or "")).name == chapter_file.name:
            return entry
    return None


def _artifact_dir(project_root: Path, chapter: int) -> Path:
    return project_root / "04_editing" / "gate_artifacts" / f"ch{chapter:03d}"


def _configured_min_words(plan: Dict[str, Any], override: Optional[int]) -> Optional[int]:
    if override is not None:
        return override if override > 0 else None
    raw = plan.get("minWordsPerChapter")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _is_fanqie_project(plan: Dict[str, Any]) -> bool:
    values = [
        plan.get("platform"),
        plan.get("channel"),
        plan.get("targetPlatform"),
        plan.get("publishPlatform"),
    ]
    return any(str(value).lower() in {"fanqie", "番茄", "番茄小说"} for value in values if value)


def _reader_score_from_report(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(r"总分[：:]\s*(\d+(?:\.\d+)?)\s*/\s*100", text)
    return float(match.group(1)) if match else None


def _reader_dimension(
    plan_entry: Optional[Dict[str, Any]],
    artifact_root: Path,
    threshold: int,
) -> Dict[str, Any]:
    reader_payload = None
    if plan_entry:
        gate_scores = plan_entry.get("gateScores") or {}
        if isinstance(gate_scores.get("reader"), dict):
            reader_payload = gate_scores["reader"]

    if reader_payload and reader_payload.get("score") is not None:
        score = float(reader_payload["score"])
        return {
            "passed": score >= threshold,
            "score": score,
            "issues": 0 if score >= threshold else 1,
            "subscores": reader_payload.get("subscores", {}),
        }

    score = _reader_score_from_report(artifact_root / "reader_report.md")
    if score is None:
        return {"passed": False, "score": 0, "issues": 1, "missing": ["reader_report.md"]}
    return {"passed": score >= threshold, "score": score, "issues": 0 if score >= threshold else 1}


def _reader_advisory_dimension(
    plan_entry: Optional[Dict[str, Any]],
    artifact_root: Path,
    threshold: int,
) -> Dict[str, Any]:
    base = _reader_dimension(plan_entry, artifact_root, threshold)
    base["advisory"] = True
    base["rawPassed"] = bool(base.get("passed"))
    base["passed"] = True
    return base


def _artifact_dimension(artifact_root: Path, names: Tuple[str, ...]) -> Dict[str, Any]:
    missing = []
    empty = []
    for name in names:
        path = artifact_root / name
        if not path.exists():
            missing.append(name)
        elif path.stat().st_size == 0:
            empty.append(name)

    passed = not missing and not empty
    return {
        "passed": passed,
        "score": 80 if passed else 0,
        "issues": len(missing) + len(empty),
        "missing": missing,
        "empty": empty,
    }


def _control_card_dimension(project_root: Path, chapter: int) -> Dict[str, Any]:
    card_path = default_card_path(project_root, chapter)
    validation = validate_card(card_path)
    issue_count = len(validation.get("missing_sections") or []) + len(validation.get("empty_sections") or [])
    if validation.get("missing"):
        issue_count = max(issue_count, 1)
    result: Dict[str, Any] = {
        "passed": bool(validation.get("passed")),
        "score": 90 if validation.get("passed") else 0,
        "issues": issue_count,
        "cardFile": str(card_path.relative_to(project_root)),
    }
    if validation.get("missing"):
        result["missing"] = [card_path.name]
    if validation.get("missing_sections"):
        result["missingSections"] = validation["missing_sections"]
    if validation.get("empty_sections"):
        result["emptySections"] = validation["empty_sections"]
    return result


def _copyedit_dimension(artifact_root: Path, chapter_file: Path) -> Dict[str, Any]:
    base = _artifact_dimension(artifact_root, REQUIRED_ARTIFACTS["copyedit"])
    risk = RiskDetector().detect_file(chapter_file)
    risk_failed = risk.gate_status == "fail"
    issues = base["issues"] + (1 if risk_failed else 0)
    passed = bool(base["passed"]) and not risk_failed
    result = {
        "passed": passed,
        "score": max(0, 90 - int(risk.ai_risk_score)),
        "issues": issues,
        "aiRiskScore": risk.ai_risk_score,
        "aiRiskStatus": risk.gate_status,
    }
    if base.get("missing"):
        result["missing"] = base["missing"]
    if base.get("empty"):
        result["empty"] = base["empty"]
    return result


def _ai_risk_dimension(chapter_file: Path) -> Dict[str, Any]:
    risk = RiskDetector().detect_file(chapter_file)
    failed = risk.gate_status == "fail"
    return {
        "passed": not failed,
        "score": max(0, 90 - int(risk.ai_risk_score)),
        "issues": 1 if failed else 0,
        "aiRiskScore": risk.ai_risk_score,
        "aiRiskStatus": risk.gate_status,
    }


def _count_hanzi(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _fanqie_safety_dimension(content: str) -> Dict[str, Any]:
    hits: List[str] = []
    for pattern in FANQIE_P0_PATTERNS:
        if re.search(pattern, content):
            hits.append(pattern)
    return {
        "passed": not hits,
        "score": 100 if not hits else 0,
        "issues": len(hits),
        "hits": hits,
    }


def _fanqie_opening_dimension(content: str, chapter: int) -> Dict[str, Any]:
    paragraphs = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    opening = paragraphs[0][:300] if paragraphs else content[:300]
    hits = [marker for marker in FANQIE_OPENING_MARKERS if marker in opening]
    has_dialogue = "“" in opening or '"' in opening
    passed = bool(hits or has_dialogue)
    if chapter > 3 and not passed:
        return {
            "passed": True,
            "score": 60,
            "issues": 0,
            "advisory": True,
            "warning": "首3章后开篇钩子只作提示。",
        }
    return {
        "passed": passed,
        "score": 85 if passed else 0,
        "issues": 0 if passed else 1,
        "markers": hits,
        "openingHanzi": _count_hanzi(opening),
    }


def _fanqie_promise_dimension(plan_entry: Optional[Dict[str, Any]], content: str) -> Dict[str, Any]:
    if not plan_entry:
        return {"passed": True, "score": 70, "issues": 0, "advisory": True}
    must_include = plan_entry.get("mustInclude") or plan_entry.get("promiseKeywords") or []
    if isinstance(must_include, str):
        must_include = [must_include]
    if not must_include:
        return {
            "passed": True,
            "score": 70,
            "issues": 0,
            "advisory": True,
            "warning": "未配置 mustInclude/promiseKeywords，主线承诺仅人工复盘。",
        }
    missing = [str(item) for item in must_include if str(item) and str(item) not in content]
    return {
        "passed": not missing,
        "score": 85 if not missing else 0,
        "issues": len(missing),
        "missing": missing,
    }


def _fanqie_end_hook_dimension(content: str) -> Dict[str, Any]:
    tail = content[-220:] if len(content) > 220 else content
    hits = [marker for marker in FANQIE_END_HOOK_MARKERS if marker in tail]
    passed = bool(hits)
    return {
        "passed": passed,
        "score": 85 if passed else 0,
        "issues": 0 if passed else 1,
        "markers": hits,
    }


def _fanqie_canon_dimension(project_root: Path) -> Dict[str, Any]:
    state_path = project_root / "00_memory" / "novel_state.md"
    passed = state_path.exists() and state_path.stat().st_size > 0
    return {
        "passed": passed,
        "score": 85 if passed else 0,
        "issues": 0 if passed else 1,
        "stateFile": "00_memory/novel_state.md",
        "missing": [] if passed else ["00_memory/novel_state.md"],
    }


def _fanqie_dimensions(
    project_root: Path,
    chapter_file: Path,
    chapter: int,
    plan_entry: Optional[Dict[str, Any]],
    artifact_root: Path,
    reader_threshold: int,
) -> Dict[str, Dict[str, Any]]:
    content = chapter_file.read_text(encoding="utf-8")
    return {
        "control_card": _control_card_dimension(project_root, chapter),
        "fanqie_safety": _fanqie_safety_dimension(content),
        "fanqie_opening": _fanqie_opening_dimension(content, chapter),
        "fanqie_promise": _fanqie_promise_dimension(plan_entry, content),
        "fanqie_end_hook": _fanqie_end_hook_dimension(content),
        "canon_writeback": _fanqie_canon_dimension(project_root),
        "ai_risk": _ai_risk_dimension(chapter_file),
        "reader": _reader_advisory_dimension(plan_entry, artifact_root, reader_threshold),
    }


def run_gate(
    project_root: Path,
    chapter_file: Path,
    chapter: int,
    min_words: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Path]:
    plan, plan_path = _load_plan(project_root)
    threshold = int((plan.get("gateThresholds") or {}).get("reader", 70))
    gate_mode = "fanqie" if _is_fanqie_project(plan) else "professional"
    effective_min = _configured_min_words(plan, min_words)
    plan_entry = _find_plan_entry(plan, chapter, chapter_file)
    artifact_root = _artifact_dir(project_root, chapter)
    artifact_root.mkdir(parents=True, exist_ok=True)

    word_result = check_chapter(str(chapter_file), effective_min)

    if gate_mode == "fanqie":
        dimensions = _fanqie_dimensions(project_root, chapter_file, chapter, plan_entry, artifact_root, threshold)
    else:
        dimensions: Dict[str, Dict[str, Any]] = {}
        dimensions["control_card"] = _control_card_dimension(project_root, chapter)
        dimensions["memory"] = _artifact_dimension(artifact_root, REQUIRED_ARTIFACTS["memory"])
        dimensions["consistency"] = _artifact_dimension(artifact_root, REQUIRED_ARTIFACTS["consistency"])
        dimensions["style"] = _artifact_dimension(artifact_root, REQUIRED_ARTIFACTS["style"])
        dimensions["copyedit"] = _copyedit_dimension(artifact_root, chapter_file)
        dimensions["reader"] = _reader_dimension(plan_entry, artifact_root, threshold)

    fail_reasons: List[str] = []
    if word_result["status"] != "pass":
        fail_reasons.append(f"word_count_below_min: {word_result['word_count']}/{effective_min}")
    for name, payload in dimensions.items():
        if not payload.get("passed"):
            fail_reasons.append(f"{name}_failed")

    passed = not fail_reasons
    result = {
        "chapter_id": f"ch{chapter:03d}",
        "chapter_file": str(chapter_file.relative_to(project_root) if chapter_file.is_relative_to(project_root) else chapter_file),
        "gate_mode": gate_mode,
        "passed": passed,
        "fail_reason": "; ".join(fail_reasons) if fail_reasons else None,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "word_count": word_result["word_count"],
        "word_count_pass": word_result["status"] == "pass",
        "min_words": effective_min,
        "dimensions": dimensions,
    }

    out_path = artifact_root / "gate_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if plan_entry is not None:
        plan_entry["wordCount"] = word_result["word_count"]
        plan_entry["wordCountPass"] = word_result["status"] == "pass"
        plan_entry["gateScores"] = dimensions
        plan_entry["lastUpdatedAt"] = datetime.now().isoformat(timespec="seconds")
        plan_entry["status"] = "completed" if passed else "failed"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    return result, plan, out_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="章节门禁结算器（novelist）")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter-file", required=True)
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--min-words", type=int, default=None, help="硬性最低字数；0 或省略表示读取计划，计划未配置则不硬卡")
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

    try:
        result, _plan, out_path = run_gate(project_root, chapter_file, chapter, args.min_words)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"错误：门禁执行失败 - {exc}", file=sys.stderr)
        return 2

    print(f"门禁结果：{'通过' if result['passed'] else '未通过'}")
    print(f"写入：{out_path}")
    if result["fail_reason"]:
        print(f"原因：{result['fail_reason']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
