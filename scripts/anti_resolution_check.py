#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anti_resolution_check.py — 反向刹车与事件冷却引擎（零外部依赖）

实现 references/advanced/million-word-roadmap.md §7「反向刹车与事件冷却」：
- check：检测本章是否越权解决主线冲突 / 事件冷却违规
- record：记录本章事件类型
- recommend：基于冷却状态推荐下一章事件类型
- status：输出当前事件矩阵状态

依赖：仅 Python 标准库（zero-dep）。
退出码：0 通过 / 1 违规 / 2 输入错误
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


# ───────────────────────────── 事件类型与冷却规则 ─────────────────────────────

EVENT_TYPES = {
    "conflict_thrill":    {"cn": "冲突爽点", "cooldown": 2, "max_consecutive": 2},
    "bond_deepening":     {"cn": "羁绊深化", "cooldown": 0, "max_consecutive": 4},
    "faction_building":   {"cn": "势力构建", "cooldown": 1, "max_consecutive": 3},
    "world_painting":     {"cn": "世界观铺陈", "cooldown": 0, "max_consecutive": 3},
    "tension_escalation": {"cn": "张力升级", "cooldown": 1, "max_consecutive": 3},
    "mystery_reveal":     {"cn": "悬念揭露", "cooldown": 3, "max_consecutive": 1},
    "comic_relief":       {"cn": "轻松日常", "cooldown": 0, "max_consecutive": 3},
}

# 每 5 章至少出现一次的事件类型
MANDATORY_EVERY_5 = {"bond_deepening", "world_painting"}

# 配额约束（Iron Law）
QUOTA_TYPES = {"A": "主线矛盾实质推进", "B": "主要关系决定性升级", "C": "核心秘密完整揭露"}
MAX_QUOTA_PER_CHAPTER = 1

# 关键词→事件类型映射（用于从正文自动推断）
EVENT_KEYWORDS: Dict[str, List[str]] = {
    "conflict_thrill":    ["战斗", "打斗", "厮杀", "交手", "出招", "暴怒", "冲突", "对峙", "决斗", "爆发"],
    "bond_deepening":     ["信任", "感动", "心意", "温暖", "默契", "陪伴", "守护", "关心", "情谊"],
    "faction_building":   ["势力", "联盟", "阵营", "结盟", "投靠", "归顺", "组织", "门派"],
    "world_painting":     ["传说", "历史", "世界", "大陆", "古老", "起源", "遗迹", "文明"],
    "tension_escalation": ["危险", "威胁", "阴谋", "暗中", "潜伏", "逼近", "危机", "酝酿"],
    "mystery_reveal":     ["真相", "秘密", "揭露", "身份", "真实", "隐藏", "揭开", "震惊"],
    "comic_relief":       ["笑", "打趣", "调侃", "闲聊", "日常", "休息", "吃饭", "逛街"],
}

# 配额关键词
QUOTA_KEYWORDS: Dict[str, List[str]] = {
    "A": ["击败", "消灭", "解决", "突破", "攻克", "覆灭", "终结", "摧毁", "彻底"],
    "B": ["告白", "决裂", "背叛", "结拜", "订婚", "分手", "永远", "再也不"],
    "C": ["真相", "身份", "揭露", "真实面目", "原来是", "竟然是", "一切都", "真正的"],
}


# ───────────────────────────── 状态存储 ─────────────────────────────


def _matrix_path(project_root: Path) -> Path:
    return project_root / "00_memory" / "event_matrix_state.json"


def _empty_matrix() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "chapter_events": [],  # [{chapter: N, types: [...], quotas: [...]}]
    }


def load_matrix(project_root: Path) -> Dict[str, Any]:
    path = _matrix_path(project_root)
    if not path.exists():
        return _empty_matrix()
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_matrix(project_root: Path, matrix: Dict[str, Any]) -> Path:
    path = _matrix_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    matrix["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with path.open("w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)
    return path


# ───────────────────────────── 事件推断 ─────────────────────────────


def infer_events(content: str) -> List[str]:
    """从正文推断事件类型。"""
    scores: Dict[str, int] = {et: 0 for et in EVENT_TYPES}
    for et, keywords in EVENT_KEYWORDS.items():
        for kw in keywords:
            count = content.count(kw)
            scores[et] += count

    # 返回得分最高的 1-3 个类型
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for et, score in ranked:
        if score >= 2:  # 至少命中 2 次
            result.append(et)
        if len(result) >= 3:
            break
    if not result and ranked:
        result.append(ranked[0][0])  # 至少返回一个

    return result


def infer_quotas(content: str) -> List[str]:
    """从正文推断配额触发（A/B/C）。"""
    triggered = []
    for qt, keywords in QUOTA_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in content)
        if hit >= 2:
            triggered.append(qt)
    return triggered


# ───────────────────────────── 冷却检测 ─────────────────────────────


def check_cooldown_violations(matrix: Dict, chapter: int, events: List[str]) -> List[Dict]:
    """检测冷却窗口违规。"""
    issues: List[Dict] = []
    history = matrix.get("chapter_events", [])

    for et in events:
        rule = EVENT_TYPES.get(et, {})
        cooldown = rule.get("cooldown", 0)
        max_consec = rule.get("max_consecutive", 99)
        cn_name = rule.get("cn", et)

        if cooldown <= 0:
            continue

        # 检查冷却窗口
        recent = [h for h in history if h["chapter"] > chapter - cooldown - 1 and et in h.get("types", [])]
        if len(recent) >= cooldown:
            issues.append({
                "type": "cooldown_violation",
                "severity": "P1",
                "detail": f"事件类型'{cn_name}'冷却期 {cooldown} 章内重复出现（最近: 第{recent[-1]['chapter']}章）",
                "chapter": chapter,
            })

        # 检查连续次数
        consecutive = 0
        for h in reversed(history):
            if et in h.get("types", []):
                consecutive += 1
            else:
                break
        if consecutive >= max_consec:
            issues.append({
                "type": "consecutive_violation",
                "severity": "P1",
                "detail": f"事件类型'{cn_name}'已连续 {consecutive} 章（上限 {max_consec}）",
                "chapter": chapter,
            })

    return issues


def check_mandatory_coverage(matrix: Dict, chapter: int) -> List[Dict]:
    """检查每 5 章的强制覆盖。"""
    issues: List[Dict] = []
    history = matrix.get("chapter_events", [])

    # 检查最近 5 章
    window_start = max(1, chapter - 4)
    recent = [h for h in history if window_start <= h["chapter"] <= chapter]

    if len(recent) >= 5:
        all_types: set = set()
        for h in recent:
            all_types.update(h.get("types", []))

        for mandatory in MANDATORY_EVERY_5:
            if mandatory not in all_types:
                cn = EVENT_TYPES.get(mandatory, {}).get("cn", mandatory)
                issues.append({
                    "type": "mandatory_missing",
                    "severity": "P1",
                    "detail": f"最近 5 章（第{window_start}-{chapter}章）缺少'{cn}'类事件",
                    "chapter": chapter,
                })

    return issues


def check_quota_violation(quotas: List[str], chapter: int) -> List[Dict]:
    """检查配额违规（同章 >= 2 个配额）。"""
    if len(quotas) >= 2:
        labels = [f"{q}({QUOTA_TYPES.get(q, q)})" for q in quotas]
        return [{
            "type": "quota_violation",
            "severity": "P0",
            "detail": f"第 {chapter} 章同时触发 {len(quotas)} 个配额: {', '.join(labels)}（Iron Law: 每章至多 1 项）",
            "chapter": chapter,
        }]
    return []


def check_anti_resolution(content: str, chapter: int, total_chapters: int) -> List[Dict]:
    """反向刹车：非终局章节禁止解决主线核心冲突。"""
    issues: List[Dict] = []

    # 如果在全书前 80%，检测过度解决
    if total_chapters > 0 and chapter < total_chapters * 0.8:
        resolution_markers = [
            "终于解决了", "彻底消灭", "大获全胜", "一切都结束了",
            "从此以后", "皆大欢喜", "再也没有", "完美解决",
            "所有问题都", "全部消灭", "永远消失",
        ]
        hits = [m for m in resolution_markers if m in content]
        if hits:
            issues.append({
                "type": "premature_resolution",
                "severity": "P0",
                "detail": f"非终局章节（{chapter}/{total_chapters}）出现过度解决标记: {', '.join(hits)}",
                "chapter": chapter,
            })

    # 检查章末是否留有未解决问题
    tail = content[-500:] if len(content) > 500 else content
    open_markers = ["但是", "然而", "却", "可是", "不过", "只是", "问题是",
                    "？", "……", "谁知", "不料", "没想到"]
    has_open = any(m in tail for m in open_markers)
    if not has_open and total_chapters > 0 and chapter < total_chapters * 0.95:
        issues.append({
            "type": "no_open_question",
            "severity": "P1",
            "detail": "章末未留下未解决问题或悬念",
            "chapter": chapter,
        })

    return issues


# ───────────────────────────── 推荐 ─────────────────────────────


def recommend_next(matrix: Dict, chapter: int) -> Dict[str, Any]:
    """基于冷却状态推荐下一章事件类型。"""
    history = matrix.get("chapter_events", [])

    # 计算每个类型的"就绪度"
    readiness: Dict[str, Dict] = {}
    for et, rule in EVENT_TYPES.items():
        cooldown = rule.get("cooldown", 0)
        cn = rule.get("cn", et)

        # 最近一次出现
        last_chapter = 0
        for h in reversed(history):
            if et in h.get("types", []):
                last_chapter = h["chapter"]
                break

        gap = chapter - last_chapter
        ready = gap >= cooldown
        priority = "推荐" if ready and gap >= 3 else "可用" if ready else f"冷却中（还需 {cooldown - gap} 章）"

        readiness[et] = {
            "cn": cn,
            "last_used": last_chapter,
            "gap": gap,
            "ready": ready,
            "priority": priority,
        }

    # 检查强制覆盖需求
    window = [h for h in history if h["chapter"] > chapter - 4]
    recent_types: set = set()
    for h in window:
        recent_types.update(h.get("types", []))

    urgent = []
    for mandatory in MANDATORY_EVERY_5:
        if mandatory not in recent_types:
            urgent.append(mandatory)

    return {
        "next_chapter": chapter + 1,
        "readiness": readiness,
        "urgent_needed": urgent,
    }


# ───────────────────────────── CLI ─────────────────────────────


def cmd_check(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    matrix = load_matrix(project_root)

    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 章节文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    content = chapter_file.read_text(encoding="utf-8")
    chapter = args.chapter

    # 推断事件类型和配额
    events = infer_events(content)
    quotas = infer_quotas(content)

    # 获取总章数
    total_chapters = args.total_chapters
    if total_chapters == 0:
        anchors_path = project_root / "00_memory" / "outline_anchors.json"
        if anchors_path.exists():
            with anchors_path.open("r", encoding="utf-8") as f:
                anchors = json.load(f)
            total_chapters = anchors.get("total_chapters_target", 0)

    # 收集所有问题
    all_issues: List[Dict] = []
    all_issues.extend(check_cooldown_violations(matrix, chapter, events))
    all_issues.extend(check_mandatory_coverage(matrix, chapter))
    all_issues.extend(check_quota_violation(quotas, chapter))
    all_issues.extend(check_anti_resolution(content, chapter, total_chapters))

    # 输出
    event_cn = [EVENT_TYPES.get(e, {}).get("cn", e) for e in events]
    quota_cn = [f"{q}({QUOTA_TYPES.get(q, q)})" for q in quotas]

    print(f"第 {chapter} 章 · 反向刹车检测", file=sys.stderr)
    print(f"  推断事件类型: {', '.join(event_cn)}", file=sys.stderr)
    if quotas:
        print(f"  配额触发: {', '.join(quota_cn)}", file=sys.stderr)

    if not all_issues:
        print("✅ 未检测到违规", file=sys.stderr)
        return 0

    p0 = [i for i in all_issues if i.get("severity") == "P0"]
    p1 = [i for i in all_issues if i.get("severity") == "P1"]

    print(f"\n⚠ 检测到 {len(all_issues)} 个问题（P0: {len(p0)}, P1: {len(p1)}）：", file=sys.stderr)
    for iss in all_issues:
        sev = iss.get("severity", "P2")
        prefix = "🔴" if sev == "P0" else "🟡"
        print(f"  {prefix} [{sev}] {iss['detail']}", file=sys.stderr)

    return 1 if p0 else 0  # 只有 P0 才阻断


def cmd_record(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    matrix = load_matrix(project_root)
    chapter = args.chapter
    types = [t.strip() for t in args.types.split(",")]

    # 验证类型
    for t in types:
        if t not in EVENT_TYPES:
            print(f"错误: 无效事件类型 '{t}'，允许: {', '.join(EVENT_TYPES.keys())}", file=sys.stderr)
            return 2

    # 移除已有记录（覆盖更新）
    matrix["chapter_events"] = [h for h in matrix.get("chapter_events", []) if h["chapter"] != chapter]
    matrix["chapter_events"].append({
        "chapter": chapter,
        "types": types,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    })
    matrix["chapter_events"].sort(key=lambda h: h["chapter"])

    save_matrix(project_root, matrix)
    cn_names = [EVENT_TYPES[t]["cn"] for t in types]
    print(f"✅ 已记录第 {chapter} 章事件: {', '.join(cn_names)}", file=sys.stderr)
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    matrix = load_matrix(project_root)
    chapter = args.chapter

    rec = recommend_next(matrix, chapter)
    print(f"\n📋 第 {rec['next_chapter']} 章事件推荐\n")

    if rec["urgent_needed"]:
        urgent_cn = [EVENT_TYPES[u]["cn"] for u in rec["urgent_needed"]]
        print(f"🔴 紧急需要: {', '.join(urgent_cn)}（5 章强制覆盖要求）\n")

    print("| 事件类型 | 上次使用 | 间隔 | 状态 |")
    print("|---------|:-------:|:----:|------|")
    for et, info in rec["readiness"].items():
        last = f"第{info['last_used']}章" if info["last_used"] > 0 else "从未"
        print(f"| {info['cn']} | {last} | {info['gap']} 章 | {info['priority']} |")
    print()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    matrix = load_matrix(project_root)
    history = matrix.get("chapter_events", [])

    print(f"\n📊 事件矩阵状态（共 {len(history)} 条记录）\n")
    if not history:
        print("  （空）")
        return 0

    for h in history[-20:]:  # 最近 20 条
        types_cn = [EVENT_TYPES.get(t, {}).get("cn", t) for t in h.get("types", [])]
        print(f"  第 {h['chapter']:>3} 章: {', '.join(types_cn)}")
    print()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="反向刹车与事件冷却引擎（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="检测本章是否违规")
    pc.add_argument("--project-root", required=True)
    pc.add_argument("--chapter", type=int, required=True)
    pc.add_argument("--chapter-file", required=True, help="章节文件路径")
    pc.add_argument("--total-chapters", type=int, default=0, help="全书总章数（0=自动读取锚点）")
    pc.set_defaults(func=cmd_check)

    pr = sub.add_parser("record", help="记录本章事件类型")
    pr.add_argument("--project-root", required=True)
    pr.add_argument("--chapter", type=int, required=True)
    pr.add_argument("--types", required=True, help="事件类型（逗号分隔）")
    pr.set_defaults(func=cmd_record)

    prec = sub.add_parser("recommend", help="推荐下一章事件类型")
    prec.add_argument("--project-root", required=True)
    prec.add_argument("--chapter", type=int, required=True, help="当前章号")
    prec.set_defaults(func=cmd_recommend)

    ps = sub.add_parser("status", help="查看事件矩阵状态")
    ps.add_argument("--project-root", required=True)
    ps.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
