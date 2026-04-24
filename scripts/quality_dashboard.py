#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
质量趋势仪表盘（v1.2.0 引入）

实现 references/advanced/quality-dashboard-spec.md 的 CLI 产物：
- 五维门禁趋势（一致性/文风/校稿/记忆/读者）
- 读者维度 6 子项趋势
- 拐点检测、离群/高光章、下一步建议
- 多种输出格式：cli / json / md / csv

依赖：仅 Python 标准库（zero-dep）。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Windows 控制台编码兼容
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 数据模型 ─────────────────────────────

DIMENSIONS: Tuple[str, ...] = ("consistency", "style", "copyedit", "memory", "reader")
DIMENSION_CN: Dict[str, str] = {
    "consistency": "一致性",
    "style": "文风",
    "copyedit": "校稿",
    "memory": "记忆",
    "reader": "读者",
}
READER_SUB_ORDER: Tuple[str, ...] = (
    "end_hook",
    "retention",
    "surprise",
    "immersion",
    "payoff",
    "share",
)
READER_SUB_CN: Dict[str, str] = {
    "end_hook": "end_hook",
    "retention": "retention",
    "surprise": "surprise",
    "immersion": "immersion",
    "payoff": "payoff",
    "share": "share",
}
DEFAULT_THRESHOLDS: Dict[str, int] = {
    "consistency": 70,
    "style": 70,
    "copyedit": 70,
    "memory": 70,
    "reader": 70,
}


@dataclass
class ChapterRecord:
    """单章记录（来自 02-写作计划.json）"""

    number: int
    title: str
    status: str
    word_count: int
    word_count_pass: Optional[bool]
    retry_count: int
    gate_duration_seconds: Optional[float]
    tags: List[str]
    gate_scores: Dict[str, Optional[Dict[str, float]]] = field(default_factory=dict)
    reader_subscores: Dict[str, Optional[int]] = field(default_factory=dict)

    def dim_score(self, dim: str) -> Optional[float]:
        info = self.gate_scores.get(dim)
        if not info:
            return None
        score = info.get("score")
        if score is None:
            return None
        try:
            return float(score)
        except (TypeError, ValueError):
            return None

    def dim_passed(self, dim: str) -> Optional[bool]:
        info = self.gate_scores.get(dim)
        if not info:
            return None
        return info.get("passed")

    def total_score(self) -> Optional[float]:
        scores = [self.dim_score(d) for d in DIMENSIONS]
        valid = [s for s in scores if s is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    def weakest(self) -> Tuple[Optional[str], Optional[float]]:
        pairs = [(d, self.dim_score(d)) for d in DIMENSIONS]
        pairs = [(d, s) for d, s in pairs if s is not None]
        if not pairs:
            return (None, None)
        pairs.sort(key=lambda x: x[1])
        return pairs[0]

    def strongest(self) -> Tuple[Optional[str], Optional[float]]:
        pairs = [(d, self.dim_score(d)) for d in DIMENSIONS]
        pairs = [(d, s) for d, s in pairs if s is not None]
        if not pairs:
            return (None, None)
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[0]


@dataclass
class DashboardData:
    project_path: Path
    project_title: str
    total_planned: int
    chapters: List[ChapterRecord]
    thresholds: Dict[str, int]
    reader_profile: object

    def completed(self) -> List[ChapterRecord]:
        return [c for c in self.chapters if c.status == "completed" or c.gate_scores]


# ───────────────────────────── 加载 ─────────────────────────────


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_gate_scores(raw: Optional[Dict]) -> Tuple[Dict[str, Optional[Dict[str, float]]], Dict[str, Optional[int]]]:
    """把原始 gateScores 字典归一化为 {dim: {score, passed, issues}}。"""
    result: Dict[str, Optional[Dict[str, float]]] = {d: None for d in DIMENSIONS}
    reader_subs: Dict[str, Optional[int]] = {s: None for s in READER_SUB_ORDER}

    if not raw:
        return result, reader_subs

    for dim in DIMENSIONS:
        payload = raw.get(dim)
        if not isinstance(payload, dict):
            continue
        score = _safe_float(payload.get("score"))
        passed = payload.get("passed")
        issues = _safe_int(payload.get("issues"), 0)
        if score is None and passed is None:
            continue
        result[dim] = {"score": score, "passed": passed, "issues": issues}

    reader_payload = raw.get("reader") if isinstance(raw.get("reader"), dict) else None
    if reader_payload:
        subs = reader_payload.get("subscores") or {}
        # 兼容 end_hook / end_hook_score 两种键
        alias = {
            "end_hook": ["end_hook", "end_hook_score"],
            "retention": ["retention", "retention_score"],
            "surprise": ["surprise", "surprise_score"],
            "immersion": ["immersion", "immersion_score"],
            "payoff": ["payoff", "payoff_score"],
            "share": ["share", "share_score"],
        }
        for key, candidates in alias.items():
            for c in candidates:
                if c in subs:
                    reader_subs[key] = _safe_int(subs.get(c), 0)
                    break

    return result, reader_subs


def load_dashboard_data(project_root: Path) -> DashboardData:
    plan_path = project_root / "02-写作计划.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"未找到 02-写作计划.json：{plan_path}")

    with plan_path.open("r", encoding="utf-8") as f:
        plan = json.load(f)

    title = plan.get("title") or plan.get("projectTitle") or project_root.name
    chapters_raw = plan.get("chapters") or []
    thresholds_raw = plan.get("gateThresholds") or {}
    thresholds = {**DEFAULT_THRESHOLDS, **{k: _safe_int(v, DEFAULT_THRESHOLDS.get(k, 70)) for k, v in thresholds_raw.items() if k in DEFAULT_THRESHOLDS}}
    reader_profile = plan.get("readerProfile") or "webnovel_veteran"

    chapters: List[ChapterRecord] = []
    for raw in chapters_raw:
        if not isinstance(raw, dict):
            continue
        number = _safe_int(raw.get("chapterNumber") or raw.get("number"), 0)
        if number <= 0:
            continue
        gate_scores, reader_subs = _normalize_gate_scores(raw.get("gateScores"))
        chapters.append(
            ChapterRecord(
                number=number,
                title=str(raw.get("title") or ""),
                status=str(raw.get("status") or "pending"),
                word_count=_safe_int(raw.get("wordCount"), 0),
                word_count_pass=raw.get("wordCountPass"),
                retry_count=_safe_int(raw.get("retryCount"), 0),
                gate_duration_seconds=_safe_float(raw.get("gateDurationSeconds")),
                tags=[str(t) for t in (raw.get("tags") or [])],
                gate_scores=gate_scores,
                reader_subscores=reader_subs,
            )
        )

    chapters.sort(key=lambda c: c.number)

    return DashboardData(
        project_path=project_root,
        project_title=str(title),
        total_planned=len(chapters_raw),
        chapters=chapters,
        thresholds=thresholds,
        reader_profile=reader_profile,
    )


# ───────────────────────────── 统计 ─────────────────────────────


def _mean(values: Iterable[float]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _rolling_mean(values: Sequence[Optional[float]], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        sub = [v for v in values[start : i + 1] if v is not None]
        out.append(sum(sub) / len(sub) if sub else None)
    return out


def detect_inflection(series: Sequence[Optional[float]], threshold_warn: float = 5.0, window: int = 5) -> List[Tuple[int, str, float]]:
    """返回 [(index, severity, delta)]：severity ∈ {info, warn, critical}。"""
    findings: List[Tuple[int, str, float]] = []
    if len(series) < window * 2:
        return findings
    for i in range(window * 2 - 1, len(series)):
        recent = [v for v in series[i - window + 1 : i + 1] if v is not None]
        prev = [v for v in series[i - 2 * window + 1 : i - window + 1] if v is not None]
        if len(recent) < 2 or len(prev) < 2:
            continue
        delta = (sum(recent) / len(recent)) - (sum(prev) / len(prev))
        if delta <= -10 and len(recent) >= window:
            findings.append((i, "critical", delta))
        elif delta <= -threshold_warn:
            findings.append((i, "warn", delta))
    return findings


# ───────────────────────────── 渲染：ASCII ─────────────────────────────

BLOCK_CHARS: Tuple[str, ...] = (" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█")


def bar(score: Optional[float], width: int = 18) -> str:
    if score is None:
        return "─" * width
    fill = max(0.0, min(100.0, score)) / 100.0
    full = int(fill * width)
    remainder = (fill * width - full) * len(BLOCK_CHARS)
    tail_idx = int(remainder)
    tail = BLOCK_CHARS[tail_idx] if tail_idx > 0 else ""
    empty = "░" * (width - full - (1 if tail else 0))
    return "█" * full + tail + empty


def trend_arrow(recent: Optional[float], prev: Optional[float]) -> str:
    if recent is None or prev is None:
        return "─"
    diff = recent - prev
    if diff >= 5:
        return "↑↑"
    if diff >= 2:
        return "↑"
    if diff <= -5:
        return "↓↓"
    if diff <= -2:
        return "↓"
    return "→"


def ascii_line_chart(
    series: Sequence[Optional[float]],
    chapter_numbers: Sequence[int],
    width: int = 60,
    height: int = 5,
    y_min: int = 50,
    y_max: int = 100,
) -> List[str]:
    """绘制简易 ASCII 折线。"""
    if not series or not any(v is not None for v in series):
        return ["  (暂无数据)"]
    # 压缩到目标宽度（如果章节过多则抽样）
    n = len(series)
    step = max(1, math.ceil(n / width))
    sampled: List[Tuple[int, Optional[float]]] = []
    for idx in range(0, n, step):
        window_vals = [v for v in series[idx : idx + step] if v is not None]
        value = sum(window_vals) / len(window_vals) if window_vals else None
        sampled.append((chapter_numbers[idx], value))

    y_range = y_max - y_min
    rows = height
    grid = [[" "] * len(sampled) for _ in range(rows)]
    for col, (_, v) in enumerate(sampled):
        if v is None:
            continue
        clamped = max(y_min, min(y_max, v))
        ratio = (clamped - y_min) / y_range if y_range else 0.0
        row = rows - 1 - int(round(ratio * (rows - 1)))
        row = max(0, min(rows - 1, row))
        grid[row][col] = "●"

    # 轴标签
    step_label = max(1, y_range // (rows - 1)) if rows > 1 else y_range
    labels = [y_max - step_label * i for i in range(rows)]
    lines: List[str] = []
    for i, row in enumerate(grid):
        lines.append(f"    {labels[i]:>4} │ " + "".join(row))
    axis = "         └" + "─" * len(sampled)
    lines.append(axis)
    # x 轴刻度
    if sampled:
        marks_count = min(6, len(sampled))
        step_x = max(1, len(sampled) // marks_count)
        x_line = [" "] * len(sampled)
        labels_bottom: List[str] = []
        for i in range(0, len(sampled), step_x):
            labels_bottom.append(str(sampled[i][0]))
        # 简单地把所有章号列在最底部
        lines.append("          " + "  ".join(f"{ch[0]:<3}" for ch in sampled[:: max(1, len(sampled) // marks_count)]))
    return lines


# ───────────────────────────── 渲染：CLI ─────────────────────────────


def render_cli(data: DashboardData, window: int = 30, top_n: int = 5, threshold_warn: float = 5.0) -> str:
    completed = data.completed()
    total_completed = len(completed)
    last_n = completed[-window:] if completed else []

    out: List[str] = []
    sep = "═" * 71
    out.append(sep)
    out.append(f"  质量趋势仪表盘 · 《{data.project_title}》")
    out.append(
        f"  统计：第 {completed[0].number if completed else 0}-{completed[-1].number if completed else 0} 章"
        f" · 完成 {total_completed} 章 · 全书规划 {data.total_planned} 章"
        + (f" ({total_completed / data.total_planned * 100:.1f}%)" if data.total_planned else "")
    )
    out.append(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(sep)
    out.append("")

    # 全书概况
    total_words = sum(c.word_count for c in completed)
    passed_chapters = [c for c in completed if all((c.dim_passed(d) or c.dim_score(d) is None or (c.dim_score(d) or 0) >= data.thresholds[d]) for d in DIMENSIONS)]
    retry_chapters = [c for c in completed if c.retry_count > 0]
    avg_dur = _mean([c.gate_duration_seconds for c in completed if c.gate_duration_seconds])
    avg_words = total_words // total_completed if total_completed else 0
    out.append("▌ 全书概况\n")
    out.append(f"  总字数：{total_words:,} 字 · 章均 {avg_words:,} 字")
    if total_completed:
        pass_rate = len(passed_chapters) / total_completed * 100
        retry_rate = len(retry_chapters) / total_completed * 100
        out.append(f"  门禁通过率：{len(passed_chapters)}/{total_completed} ({pass_rate:.1f}%) · 修复触发率：{len(retry_chapters)}/{total_completed} ({retry_rate:.1f}%)")
    if avg_dur is not None:
        mins = int(avg_dur // 60)
        secs = int(avg_dur % 60)
        out.append(f"  门禁均耗时：{mins} 分 {secs} 秒/章")
    out.append("")

    # 维度趋势
    out.append(f"▌ 五维门禁趋势（最近 {len(last_n)} 章 · 横轴 = 章号）\n")
    for dim in DIMENSIONS:
        name = DIMENSION_CN[dim]
        series = [c.dim_score(dim) for c in last_n]
        current = next((v for v in reversed(series) if v is not None), None)
        overall = _mean([c.dim_score(dim) for c in completed])
        prev5 = _mean([c.dim_score(dim) for c in last_n[-10:-5]])
        recent5 = _mean([c.dim_score(dim) for c in last_n[-5:]])
        lowest_chapter = None
        lowest_score = None
        for c in completed:
            s = c.dim_score(dim)
            if s is None:
                continue
            if lowest_score is None or s < lowest_score:
                lowest_score = s
                lowest_chapter = c
        threshold = data.thresholds.get(dim, 70)
        cur_disp = f"{int(round(current))}" if current is not None else "—"
        mean_disp = f"{overall:.0f}" if overall is not None else "—"
        extra = ""
        if lowest_chapter and lowest_score is not None:
            extra = f"，最低 第{lowest_chapter.number}章 {int(round(lowest_score))}"
        warn = ""
        if current is not None and current < threshold:
            warn = "  ⚠"
        out.append(f"  {name:<4}  {bar(current)}  {cur_disp:>3}  {trend_arrow(recent5, prev5)}  (均值 {mean_disp}{extra}){warn}")
    out.append("")

    # 读者维度 ASCII 趋势
    out.append("  📈 ASCII 趋势（读者维度）：")
    reader_series = [c.dim_score("reader") for c in last_n]
    chapter_nums = [c.number for c in last_n]
    if reader_series:
        out.extend(ascii_line_chart(reader_series, chapter_nums))
    else:
        out.append("    (暂无数据)")
    out.append("")

    # 读者子项
    out.append(f"▌ 读者维度子项（最近 {min(10, len(last_n))} 章均值）\n")
    reader_recent = last_n[-10:] if last_n else []
    for sub in READER_SUB_ORDER:
        values = [c.reader_subscores.get(sub) for c in reader_recent]
        avg = _mean([v for v in values if v is not None])
        prev_half = _mean([v for v in values[: len(values) // 2] if v is not None])
        recent_half = _mean([v for v in values[len(values) // 2 :] if v is not None])
        disp = f"{avg:.0f}" if avg is not None else "—"
        arrow = trend_arrow(recent_half, prev_half)
        warn = "  ⚠" if avg is not None and avg < 65 else ""
        out.append(f"  {sub:<9}  {bar(avg)}  {disp:>3}  {arrow}{warn}")
    out.append("")

    # 风险拐点
    out.append("▌ 风险拐点\n")
    risk_lines: List[str] = []
    for dim in DIMENSIONS:
        full_series = [c.dim_score(dim) for c in completed]
        findings = detect_inflection(full_series, threshold_warn=threshold_warn)
        for idx, severity, delta in findings[-3:]:
            chap = completed[idx]
            prefix = "🔴" if severity == "critical" else "🟡"
            risk_lines.append(f"  {prefix} 第 {chap.number} 章 — {DIMENSION_CN[dim]}分拐点 (Δ={delta:.1f})")
    if not risk_lines:
        risk_lines.append("  🟢 无明显拐点")
    out.extend(risk_lines)
    out.append("")

    # 离群 / 高光
    ranked = [(c, c.total_score()) for c in completed if c.total_score() is not None]
    ranked_sorted_low = sorted(ranked, key=lambda x: (x[1], x[0].number))[:top_n]
    ranked_sorted_high = sorted(ranked, key=lambda x: (-x[1], x[0].number))[:top_n]

    def _row(c: ChapterRecord, total: float, weakest: bool) -> str:
        if weakest:
            d, s = c.weakest()
        else:
            d, s = c.strongest()
        tag_str = "·".join(c.tags) if c.tags else "—"
        dim_str = f"{DIMENSION_CN.get(d, d or '—')} {int(round(s))}" if s is not None else "—"
        return f"   #{c.number:<3} │ {int(round(total)):>3}  │ {dim_str:<14} │ {tag_str}"

    out.append("▌ 离群章（最低 {n} 章）\n".format(n=top_n))
    out.append("   章号 │ 总分 │ 最弱维度       │ 标签")
    out.append("  ──────┼──────┼────────────────┼─────────")
    for c, total in ranked_sorted_low:
        out.append(_row(c, total, weakest=True))
    out.append("")

    out.append("▌ 增长高光（最高 {n} 章）\n".format(n=top_n))
    out.append("   章号 │ 总分 │ 最强维度       │ 标签")
    out.append("  ──────┼──────┼────────────────┼─────────")
    for c, total in ranked_sorted_high:
        out.append(_row(c, total, weakest=False))
    out.append("")

    # 下一步建议
    out.append(sep)
    out.append("  📌 下一步建议")
    suggestions = build_suggestions(data, completed, last_n, risk_lines)
    for i, s in enumerate(suggestions, 1):
        out.append(f"  {i}. {s}")
    out.append(sep)

    return "\n".join(out)


def build_suggestions(data: DashboardData, completed: List[ChapterRecord], last_n: List[ChapterRecord], risk_lines: List[str]) -> List[str]:
    suggestions: List[str] = []
    if not completed:
        return ["暂无完成章节，先写几章再回来复盘"]

    # 低于阈值的维度
    for dim in DIMENSIONS:
        recent = _mean([c.dim_score(dim) for c in last_n[-5:]])
        if recent is not None and recent < data.thresholds.get(dim, 70):
            suggestions.append(f"{DIMENSION_CN[dim]}维度最近 5 章均值 {recent:.1f} < 阈值 {data.thresholds.get(dim, 70)}：优先跑 /章 --修复")

    # 读者子项
    for sub in READER_SUB_ORDER:
        values = [c.reader_subscores.get(sub) for c in last_n[-5:]]
        avg = _mean([v for v in values if v is not None])
        if avg is not None and avg < 65:
            suggestions.append(f"读者 {sub} 最近 5 章均值 {avg:.1f}：参考 reader-simulator-spec.md §8 修复建议")

    if not suggestions:
        suggestions.append("当前各维度稳定，持续监控即可。下次复盘建议：每 5 章或每卷收尾")
    return suggestions


# ───────────────────────────── 渲染：JSON / CSV / MD ─────────────────────────────


def render_json(data: DashboardData) -> str:
    payload = {
        "project": {
            "title": data.project_title,
            "path": str(data.project_path),
            "totalPlanned": data.total_planned,
            "readerProfile": data.reader_profile,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
        },
        "thresholds": data.thresholds,
        "chapters": [],
        "summary": {},
    }
    completed = data.completed()
    for c in completed:
        payload["chapters"].append(
            {
                "number": c.number,
                "title": c.title,
                "status": c.status,
                "wordCount": c.word_count,
                "retryCount": c.retry_count,
                "tags": c.tags,
                "gateScores": {
                    dim: c.gate_scores.get(dim) for dim in DIMENSIONS
                },
                "readerSubscores": c.reader_subscores,
                "totalScore": c.total_score(),
            }
        )
    payload["summary"] = {
        "completed": len(completed),
        "totalWords": sum(c.word_count for c in completed),
        "dimensionMean": {
            dim: _mean([c.dim_score(dim) for c in completed]) for dim in DIMENSIONS
        },
        "readerSubMean": {
            sub: _mean([c.reader_subscores.get(sub) for c in completed if c.reader_subscores.get(sub) is not None])
            for sub in READER_SUB_ORDER
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_csv(data: DashboardData) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["chapter", "title", "status", "wordCount", "retryCount"]
    header.extend([f"score_{d}" for d in DIMENSIONS])
    header.extend([f"reader_{s}" for s in READER_SUB_ORDER])
    header.append("totalScore")
    header.append("tags")
    writer.writerow(header)
    for c in data.completed():
        row = [c.number, c.title, c.status, c.word_count, c.retry_count]
        row.extend([c.dim_score(d) for d in DIMENSIONS])
        row.extend([c.reader_subscores.get(s) for s in READER_SUB_ORDER])
        row.append(c.total_score())
        row.append("|".join(c.tags))
        writer.writerow(row)
    return buf.getvalue()


def _fmt_score(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def render_markdown(data: DashboardData) -> str:
    completed = data.completed()
    lines: List[str] = []
    lines.append(f"# 质量趋势仪表盘 · 《{data.project_title}》\n")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 完成章节：{len(completed)} / {data.total_planned}\n")

    lines.append("## 维度均值\n")
    lines.append("| 维度 | 均值 | 最近 5 章均值 | 阈值 |")
    lines.append("|------|:----:|:------------:|:----:|")
    for dim in DIMENSIONS:
        overall = _mean([c.dim_score(dim) for c in completed])
        recent5 = _mean([c.dim_score(dim) for c in completed[-5:]])
        lines.append(
            f"| {DIMENSION_CN[dim]} | {_fmt_score(overall)} | {_fmt_score(recent5)} | {data.thresholds.get(dim, 70)} |"
        )

    lines.append("\n## 章节明细\n")
    lines.append("| # | 标题 | 字数 | 总分 | 最弱维度 | 标签 |")
    lines.append("|---|------|:----:|:----:|----------|------|")
    for c in completed:
        total = c.total_score()
        weak_dim, weak_score = c.weakest()
        weak_label = "—"
        if weak_dim is not None and weak_score is not None:
            weak_label = f"{DIMENSION_CN.get(weak_dim, weak_dim)} {int(round(weak_score))}"
        lines.append(
            f"| {c.number} | {c.title} | {c.word_count:,} | {_fmt_score(total)} | {weak_label} | {' '.join(c.tags)} |"
        )
    return "\n".join(lines)


# ───────────────────────────── Summary / 单维度 ─────────────────────────────


def render_summary(data: DashboardData) -> str:
    completed = data.completed()
    last5 = completed[-5:]
    lines: List[str] = []
    lines.append(f"📊 {data.project_title}  ·  {len(completed)}/{data.total_planned} 章")
    lines.append(f"总字数：{sum(c.word_count for c in completed):,}  ·  章均 {(sum(c.word_count for c in completed) // max(1, len(completed))):,}")
    lines.append("")
    lines.append("最近 5 章维度均值：")
    for dim in DIMENSIONS:
        avg = _mean([c.dim_score(dim) for c in last5])
        disp = f"{avg:.1f}" if avg is not None else "—"
        lines.append(f"  {DIMENSION_CN[dim]:<4} : {disp}")
    return "\n".join(lines)


# ───────────────────────────── CLI 入口 ─────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="质量趋势仪表盘（novelist v1.2.0）")
    parser.add_argument("--project-root", required=True, help="项目目录（必填）")
    parser.add_argument("--range", dest="chapter_range", default=None, help="章节范围 start-end")
    parser.add_argument("--window", type=int, default=30, help="趋势窗口（默认 30 章）")
    parser.add_argument("--dimension", default="all", choices=list(DIMENSIONS) + ["all", "reader-only"])
    parser.add_argument("--format", dest="output_format", default="cli", choices=["cli", "json", "md", "csv"])
    parser.add_argument("--output", default=None, help="输出到文件（默认 stdout）")
    parser.add_argument("--threshold-warn", type=float, default=5.0, help="拐点告警阈值（分）")
    parser.add_argument("--top", type=int, default=5, help="离群/高光章数量")
    parser.add_argument("--summary", action="store_true", help="仅输出简要概览")
    parser.add_argument("--no-color", action="store_true", help="禁用颜色（预留）")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"错误：项目目录不存在 - {project_root}", file=sys.stderr)
        return 2

    try:
        data = load_dashboard_data(project_root)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"错误：02-写作计划.json 解析失败 - {e}", file=sys.stderr)
        return 2

    # 范围过滤
    if args.chapter_range:
        try:
            start_s, end_s = args.chapter_range.split("-", 1)
            start, end = int(start_s), int(end_s)
            data.chapters = [c for c in data.chapters if start <= c.number <= end]
        except ValueError:
            print(f"错误：--range 格式无效（期望 start-end）：{args.chapter_range}", file=sys.stderr)
            return 2

    # 选择渲染
    if args.summary:
        payload = render_summary(data)
    elif args.output_format == "json":
        payload = render_json(data)
    elif args.output_format == "csv":
        payload = render_csv(data)
    elif args.output_format == "md":
        payload = render_markdown(data)
    else:
        payload = render_cli(data, window=args.window, top_n=args.top, threshold_warn=args.threshold_warn)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(f"✅ 已写入 {output_path}", file=sys.stderr)
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
