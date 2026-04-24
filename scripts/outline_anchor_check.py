#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
outline_anchor_check.py — 大纲锚点与进度配额校验（零外部依赖）

实现 references/advanced/million-word-roadmap.md §6「大纲锚点与进度配额」：
- init：从大纲生成 outline_anchors.json
- check：校验当前章是否在允许范围内
- advance：推进锚点到下一章
- recalculate：改纲后重算全部锚点

依赖：仅 Python 标准库（zero-dep）。
退出码：0 在允许范围 / 1 检测到越界 / 2 输入错误
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 锚点结构 ─────────────────────────────


def _anchors_path(project_root: Path) -> Path:
    return project_root / "00_memory" / "outline_anchors.json"


def _empty_anchors() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_chapters_target": 0,
        "total_volumes": 0,
        "current_chapter": 0,
        "volumes": [],
    }


def load_anchors(project_root: Path) -> Dict[str, Any]:
    path = _anchors_path(project_root)
    if not path.exists():
        return _empty_anchors()
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_anchors(project_root: Path, anchors: Dict[str, Any]) -> Path:
    path = _anchors_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    anchors["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with path.open("w", encoding="utf-8") as f:
        json.dump(anchors, f, ensure_ascii=False, indent=2)
    return path


# ───────────────────────────── 从大纲解析 ─────────────────────────────


def _parse_outline_for_anchors(project_root: Path) -> Dict[str, Any]:
    """从 01-大纲.md / novel_plan.md 解析卷级结构。"""
    outline_candidates = [
        project_root / "01-大纲.md",
        project_root / "00_memory" / "novel_plan.md",
        project_root / "01_outline" / "outline.md",
    ]
    outline_path = None
    for c in outline_candidates:
        if c.exists():
            outline_path = c
            break

    if not outline_path:
        return _empty_anchors()

    text = outline_path.read_text(encoding="utf-8")
    anchors = _empty_anchors()

    # 解析卷结构
    volumes: List[Dict[str, Any]] = []
    current_volume: Optional[Dict[str, Any]] = None

    for line in text.splitlines():
        # 匹配卷标题：## 第X卷 / ## 卷X / ## Volume X
        vol_match = re.match(r"#{1,3}\s*(?:第\s*(\d+)\s*卷|卷\s*(\d+)|Volume\s*(\d+))[：:\s—\-]*(.*)", line, re.I)
        if vol_match:
            if current_volume:
                volumes.append(current_volume)
            vol_num = int(vol_match.group(1) or vol_match.group(2) or vol_match.group(3) or len(volumes) + 1)
            vol_title = vol_match.group(4).strip() if vol_match.group(4) else ""
            current_volume = {
                "volume_number": vol_num,
                "title": vol_title,
                "chapter_start": 0,
                "chapter_end": 0,
                "must_achieve": [],
                "must_not_reveal": [],
                "foreshadows_to_plant": [],
                "allowed_pace": "中档",
            }
            continue

        if current_volume:
            # 解析章节范围
            ch_range = re.match(r".*?第\s*(\d+)\s*章.*?第\s*(\d+)\s*章", line)
            if ch_range:
                current_volume["chapter_start"] = int(ch_range.group(1))
                current_volume["chapter_end"] = int(ch_range.group(2))

            # 解析禁止揭露
            if "禁止" in line or "不得" in line or "must_not" in line.lower():
                content = re.sub(r"^[\s\-*]+", "", line).strip()
                if content:
                    current_volume["must_not_reveal"].append(content)

            # 解析必须达成
            if "必须" in line or "核心目标" in line or "must_achieve" in line.lower():
                content = re.sub(r"^[\s\-*]+", "", line).strip()
                if content:
                    current_volume["must_achieve"].append(content)

            # 解析伏笔
            if "伏笔" in line or "铺垫" in line or "foreshadow" in line.lower():
                content = re.sub(r"^[\s\-*]+", "", line).strip()
                if content:
                    current_volume["foreshadows_to_plant"].append(content)

    if current_volume:
        volumes.append(current_volume)

    # 计算总章数
    total_chapters = 0
    for v in volumes:
        if v["chapter_end"] > total_chapters:
            total_chapters = v["chapter_end"]

    anchors["total_chapters_target"] = total_chapters if total_chapters > 0 else len(volumes) * 50
    anchors["total_volumes"] = len(volumes)
    anchors["volumes"] = volumes

    return anchors


# ───────────────────────────── 当前章约束计算 ─────────────────────────────


def get_chapter_constraints(anchors: Dict, chapter: int) -> Dict[str, Any]:
    """计算指定章节的约束。"""
    volumes = anchors.get("volumes", [])

    # 找到当前卷
    current_vol = None
    for v in volumes:
        start = v.get("chapter_start", 0)
        end = v.get("chapter_end", 0)
        if start <= chapter <= end:
            current_vol = v
            break

    if not current_vol:
        # 尝试按顺序推断
        if volumes:
            for v in volumes:
                if chapter <= v.get("chapter_end", 0):
                    current_vol = v
                    break
            if not current_vol:
                current_vol = volumes[-1]

    if not current_vol:
        return {
            "chapter": chapter,
            "volume": None,
            "allowed_plot_range": "无约束（锚点未配置）",
            "forbidden_reveals": [],
            "mandatory_tension": True,
            "pace": "中档",
            "progress_percentage": 0,
        }

    total = anchors.get("total_chapters_target", 1)
    progress = chapter / max(1, total) * 100

    # 后续卷的禁止揭露也要收集（防止提前剧透）
    forbidden: List[str] = list(current_vol.get("must_not_reveal", []))
    for v in volumes:
        if v.get("volume_number", 0) > current_vol.get("volume_number", 0):
            forbidden.extend(v.get("must_achieve", []))  # 后续卷的核心目标也是本卷的禁止揭露

    return {
        "chapter": chapter,
        "volume": current_vol.get("volume_number"),
        "volume_title": current_vol.get("title", ""),
        "allowed_plot_range": "; ".join(current_vol.get("must_achieve", [])) or "按大纲推进",
        "forbidden_reveals": list(dict.fromkeys(forbidden)),  # 去重保序
        "foreshadows_to_plant": current_vol.get("foreshadows_to_plant", []),
        "mandatory_tension": True,
        "pace": current_vol.get("allowed_pace", "中档"),
        "progress_percentage": round(progress, 1),
    }


# ───────────────────────────── 越界检测 ─────────────────────────────


def check_chapter_bounds(project_root: Path, chapter: int, chapter_file: Optional[Path] = None) -> List[Dict]:
    """检测本章是否越界。"""
    anchors = load_anchors(project_root)
    constraints = get_chapter_constraints(anchors, chapter)
    issues: List[Dict] = []

    if not chapter_file:
        return issues  # 没有正文可检测

    content = chapter_file.read_text(encoding="utf-8")

    # 检测禁止揭露
    for forbidden in constraints.get("forbidden_reveals", []):
        # 提取关键词（2-6 字汉字块）
        keywords = re.findall(r"[\u4e00-\u9fff]{2,6}", forbidden)
        hit_count = 0
        hit_words = []
        for kw in keywords:
            if kw in content:
                hit_count += 1
                hit_words.append(kw)
        # 命中超过半数关键词视为可疑
        if keywords and hit_count >= max(1, len(keywords) // 2):
            issues.append({
                "type": "forbidden_reveal",
                "severity": "P0",
                "detail": f"可能提前揭露禁止内容: '{forbidden}'（命中关键词: {', '.join(hit_words)}）",
                "chapter": chapter,
            })

    # 检测章末是否有悬念
    lines = content.strip().splitlines()
    tail = "\n".join(lines[-5:]) if lines else ""
    hook_markers = ["？", "……", "…", "却", "然而", "但是", "突然", "猛地", "谁知", "不料"]
    has_hook = any(m in tail for m in hook_markers)
    if not has_hook:
        issues.append({
            "type": "missing_tension",
            "severity": "P1",
            "detail": "章末未检测到悬念元素（？/……/转折词）",
            "chapter": chapter,
        })

    return issues


# ───────────────────────────── CLI ─────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    anchors = _parse_outline_for_anchors(project_root)
    path = save_anchors(project_root, anchors)
    vols = len(anchors.get("volumes", []))
    total = anchors.get("total_chapters_target", 0)
    print(f"✅ 锚点已初始化: {path}", file=sys.stderr)
    print(f"   卷数: {vols}，预计总章数: {total}", file=sys.stderr)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    anchors = load_anchors(project_root)
    chapter = args.chapter

    constraints = get_chapter_constraints(anchors, chapter)

    # 输出约束（供 Agent 注入 Prompt）
    output_lines = [
        f"# 第 {chapter} 章 · 大纲锚点约束\n",
        f"> 当前卷: 第 {constraints.get('volume', '?')} 卷 · {constraints.get('volume_title', '')}",
        f"> 全书进度: {constraints.get('progress_percentage', 0)}%",
        f"> 节奏档位: {constraints.get('pace', '中档')}\n",
        f"## 允许推进范围\n{constraints.get('allowed_plot_range', '按大纲推进')}\n",
    ]

    forbidden = constraints.get("forbidden_reveals", [])
    if forbidden:
        output_lines.append("## ⛔ 禁止揭露\n")
        for f_item in forbidden:
            output_lines.append(f"- {f_item}")
        output_lines.append("")

    foreshadows = constraints.get("foreshadows_to_plant", [])
    if foreshadows:
        output_lines.append("## 📌 本卷待埋伏笔\n")
        for fs in foreshadows:
            output_lines.append(f"- {fs}")
        output_lines.append("")

    output = "\n".join(output_lines)

    # 可选：检测正文越界
    issues: List[Dict] = []
    if args.chapter_file:
        cf = Path(args.chapter_file).expanduser().resolve()
        if cf.exists():
            issues = check_chapter_bounds(project_root, chapter, cf)

    if args.output:
        Path(args.output).expanduser().write_text(output, encoding="utf-8")
        print(f"✅ 约束已写入: {args.output}", file=sys.stderr)
    else:
        print(output)

    if issues:
        print(f"\n⚠ 检测到 {len(issues)} 个越界问题：", file=sys.stderr)
        for iss in issues:
            sev = iss.get("severity", "P2")
            prefix = "🔴" if sev == "P0" else "🟡"
            print(f"  {prefix} [{sev}] {iss['detail']}", file=sys.stderr)
        return 1

    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    anchors = load_anchors(project_root)
    anchors["current_chapter"] = args.to_chapter
    save_anchors(project_root, anchors)
    print(f"✅ 锚点已推进到第 {args.to_chapter} 章", file=sys.stderr)
    return 0


def cmd_recalculate(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    old = load_anchors(project_root)
    new = _parse_outline_for_anchors(project_root)
    new["current_chapter"] = old.get("current_chapter", 0)
    save_anchors(project_root, new)
    print(f"✅ 锚点已重算（保留当前进度: 第 {new['current_chapter']} 章）", file=sys.stderr)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="大纲锚点与进度配额校验（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="从大纲初始化锚点")
    pi.add_argument("--project-root", required=True)
    pi.set_defaults(func=cmd_init)

    pc = sub.add_parser("check", help="校验当前章约束")
    pc.add_argument("--project-root", required=True)
    pc.add_argument("--chapter", type=int, required=True, help="章节号")
    pc.add_argument("--chapter-file", default=None, help="章节文件（可选，用于越界检测）")
    pc.add_argument("--output", default=None)
    pc.set_defaults(func=cmd_check)

    pa = sub.add_parser("advance", help="推进锚点")
    pa.add_argument("--project-root", required=True)
    pa.add_argument("--to-chapter", type=int, required=True)
    pa.set_defaults(func=cmd_advance)

    pr = sub.add_parser("recalculate", help="改纲后重算锚点")
    pr.add_argument("--project-root", required=True)
    pr.set_defaults(func=cmd_recalculate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
