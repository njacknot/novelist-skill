#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读者模拟审稿脚本（v1.2.0 引入）

实现 references/advanced/reader-simulator-spec.md 契约：
- 读取章节正文 + 计划 + 大纲 + 人物档案
- 两种运行模式：
    1. 启发式评分（默认，无外部依赖，零网络）——基于文本特征打分
    2. Prompt 驱动模式（--prompt-only）——仅输出给 LLM/Agent 的待填补模板
- 产物：04_editing/gate_artifacts/<chapter_id>/reader_report.md
- 回写：02-写作计划.json 的 chapters[N].gateScores.reader
- 退出码：0 通过 / 1 未达阈值 / 2 输入错误
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 常量 ─────────────────────────────

SUB_WEIGHTS: Dict[str, int] = {
    "end_hook": 25,
    "retention": 25,
    "surprise": 15,
    "immersion": 15,
    "payoff": 10,
    "share": 10,
}

DEFAULT_THRESHOLD = 70

# AI 模板化句式（出戏检测）——命中即扣分
AI_TEMPLATE_PATTERNS: List[str] = [
    r"眼中闪过(?:一丝|一抹|一道).*?的(?:光芒|神色|寒光)",
    r"心中涌起(?:一阵|一股|一丝).*?的(?:情感|情绪|感觉)",
    r"握紧(?:了)?拳头",
    r"下意识地(?:咬紧|咬住|握紧|攥紧)",
    r"(?:心潮澎湃|热血沸腾|怒火中烧|怒不可遏|义愤填膺)",
    r"让(?:所有人|众人|大家)都(?:大吃一惊|震惊不已|瞠目结舌)",
    r"一丝(?:坚定|决绝|凌厉|狠辣|阴冷)的(?:光芒|神色)",
    r"仿佛.*?一般",
    r"脸上露出.*?的(?:笑容|神色|表情)",
    r"(?:不容置疑|不容拒绝)的(?:语气|口吻)",
]

# 意外感标识（预期外转折词）
SURPRISE_MARKERS: List[str] = [
    "没想到", "谁能想到", "谁知道", "万万没想到",
    "竟然", "居然", "不料", "意外", "突然",
    "霎时间", "猛地", "骤然", "刹那",
]

# 钩子特征关键词
HOOK_MARKERS: List[str] = [
    "？", "……", "…", "！",
    "但是", "却是", "然而", "只是",
    "谜", "秘密", "真相", "身份",
    "死", "杀", "救", "危险",
]


# ───────────────────────────── 数据结构 ─────────────────────────────


@dataclass
class ChapterContext:
    number: int
    title: str
    file_path: Path
    word_count: int
    content: str
    paragraphs: List[str]
    dialogues: List[str]
    last_paragraph: str
    tags: List[str] = field(default_factory=list)


@dataclass
class ReaderScore:
    end_hook: int = 0
    retention: int = 0
    surprise: int = 0
    immersion: int = 0
    payoff: int = 0
    share: int = 0
    findings: Dict[str, List[str]] = field(default_factory=dict)
    ai_hits: List[Tuple[str, str]] = field(default_factory=list)  # (match_text, pattern)
    hook_quote: str = ""
    hook_type: str = ""
    surprise_hits: List[str] = field(default_factory=list)
    payoff_hits: List[str] = field(default_factory=list)
    share_candidates: List[str] = field(default_factory=list)

    def total(self) -> float:
        return (
            self.end_hook * SUB_WEIGHTS["end_hook"]
            + self.retention * SUB_WEIGHTS["retention"]
            + self.surprise * SUB_WEIGHTS["surprise"]
            + self.immersion * SUB_WEIGHTS["immersion"]
            + self.payoff * SUB_WEIGHTS["payoff"]
            + self.share * SUB_WEIGHTS["share"]
        ) / 100.0

    def as_subscore_dict(self) -> Dict[str, int]:
        return {
            "end_hook": self.end_hook,
            "retention": self.retention,
            "surprise": self.surprise,
            "immersion": self.immersion,
            "payoff": self.payoff,
            "share": self.share,
        }


# ───────────────────────────── 读取 ─────────────────────────────


def _count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _strip_markdown(text: str) -> str:
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text


def _extract_dialogues(text: str) -> List[str]:
    """提取对话：支持多种引号类型（中文全角、英文直引号、日式方括号）。"""
    patterns = [
        r"\u201c([^\u201d]+)\u201d",
        r"\"([^\"\n]+)\"",
        r"\u300c([^\u300d]+)\u300d",
    ]
    found: List[str] = []
    for pat in patterns:
        found.extend(re.findall(pat, text))
    return [d.strip() for d in found if d.strip()]


def load_plan(project_root: Path) -> Dict:
    plan_path = project_root / "02-写作计划.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"未找到 02-写作计划.json：{plan_path}")
    with plan_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_plan(project_root: Path, plan: Dict) -> None:
    plan_path = project_root / "02-写作计划.json"
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def resolve_chapter_file(project_root: Path, plan: Dict, chapter_number: int) -> Path:
    chapters = plan.get("chapters") or []
    target = next((c for c in chapters if int(c.get("chapterNumber") or 0) == chapter_number), None)
    if not target:
        raise FileNotFoundError(f"02-写作计划.json 中未找到第 {chapter_number} 章")
    manuscript_dir = project_root / "03_manuscript"
    if not manuscript_dir.exists():
        # 兼容老项目：平铺在项目根
        manuscript_dir = project_root
    candidates: List[Path] = []
    for name_key in ("filePath", "file"):
        v = target.get(name_key)
        if v:
            candidates.append(manuscript_dir / v)
    # 回退：按章节号模糊匹配
    pattern = re.compile(rf"第\s*0?{chapter_number}\s*章")
    for p in manuscript_dir.glob("*.md"):
        if pattern.search(p.name):
            candidates.append(p)
    for cand in candidates:
        if cand.exists():
            return cand
    raise FileNotFoundError(f"未找到第 {chapter_number} 章正文文件（搜索路径：{manuscript_dir}）")


def load_chapter_context(chapter_file: Path, plan_entry: Dict) -> ChapterContext:
    raw = chapter_file.read_text(encoding="utf-8")
    stripped = _strip_markdown(raw)
    # 跳过章首标题
    lines = stripped.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("第") and "章" in line:
            start = i + 1
            break
    body = "\n".join(lines[start:])
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    dialogues = _extract_dialogues(raw)
    last_paragraph = paragraphs[-1] if paragraphs else ""
    return ChapterContext(
        number=int(plan_entry.get("chapterNumber") or 0),
        title=str(plan_entry.get("title") or chapter_file.stem),
        file_path=chapter_file,
        word_count=_count_chinese(body),
        content=body,
        paragraphs=paragraphs,
        dialogues=dialogues,
        last_paragraph=last_paragraph,
        tags=[str(t) for t in (plan_entry.get("tags") or [])],
    )


def load_outline_foreshadows(project_root: Path) -> List[str]:
    """从 01-大纲.md 粗略提取伏笔/铺垫关键字。"""
    outline_path = project_root / "01-大纲.md"
    if not outline_path.exists():
        return []
    text = outline_path.read_text(encoding="utf-8")
    keywords: List[str] = []
    for m in re.findall(r"伏笔[:：]\s*(.+)", text):
        keywords.extend(re.findall(r"[\u4e00-\u9fff]{2,6}", m))
    for m in re.findall(r"铺垫[:：]\s*(.+)", text):
        keywords.extend(re.findall(r"[\u4e00-\u9fff]{2,6}", m))
    # 去重 + 保留前 30 个
    seen: List[str] = []
    for k in keywords:
        if k not in seen:
            seen.append(k)
    return seen[:30]


# ───────────────────────────── 启发式评分 ─────────────────────────────


def _clamp(x: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(x))))


def score_end_hook(ctx: ChapterContext) -> Tuple[int, str, str]:
    """返回 (score, hook_type, hook_quote)。"""
    tail = ctx.content[-220:] if len(ctx.content) > 220 else ctx.content
    last_para = ctx.last_paragraph
    score = 60
    hook_type = "未识别"
    hook_quote = last_para[-120:]

    if any(c in tail for c in ["？", "?"]):
        score += 10
        hook_type = "疑问悬念"
    if any(c in tail for c in ["……", "…"]):
        score += 8
        hook_type = hook_type if hook_type != "未识别" else "省略悬念"
    if any(w in tail for w in ["死", "杀", "救", "危险", "血"]):
        score += 6
        hook_type = hook_type if hook_type != "未识别" else "生死钩子"
    if any(w in tail for w in ["身份", "秘密", "真相", "面具", "纹身"]):
        score += 10
        hook_type = hook_type if hook_type != "未识别" else "身份悬念"
    if any(w in tail for w in ["突然", "猛地", "骤然", "刹那"]):
        score += 6
    # 过短结尾扣分
    if len(last_para) < 30:
        score -= 8
    # 全章最后句是平铺直叙的描写
    if re.search(r"[。].{0,10}$", tail) and not any(m in tail for m in HOOK_MARKERS):
        score -= 6
    return _clamp(score), hook_type, hook_quote


def score_retention(ctx: ChapterContext) -> int:
    """追读力：有效信息 + 对话比例 + 段落节奏。短章不天然扣分。"""
    score = 60
    if 800 <= ctx.word_count <= 6000:
        score += 8
    elif ctx.word_count < 800:
        score -= 10
    elif ctx.word_count > 7000:
        score -= 8

    dialogue_chars = sum(_count_chinese(d) for d in ctx.dialogues)
    dialogue_ratio = dialogue_chars / max(1, ctx.word_count)
    if dialogue_ratio >= 0.3:
        score += 10
    elif dialogue_ratio < 0.15:
        score -= 8

    # 段落数量（避免巨型段落）
    avg_para_chars = ctx.word_count / max(1, len(ctx.paragraphs))
    if avg_para_chars > 400:
        score -= 10  # 巨型段落拖累节奏
    if len(ctx.paragraphs) >= 20:
        score += 3

    return _clamp(score)


def score_surprise(ctx: ChapterContext) -> Tuple[int, List[str]]:
    hits: List[str] = []
    for marker in SURPRISE_MARKERS:
        if marker in ctx.content:
            hits.append(marker)
    unique = list(dict.fromkeys(hits))
    score = 55 + min(30, len(unique) * 5)
    if len(unique) == 0:
        score = 45
    if len(unique) >= 6:
        score -= 5  # 过多滥用反而刻意
    return _clamp(score), unique


def score_immersion(ctx: ChapterContext) -> Tuple[int, List[Tuple[str, str]]]:
    hits: List[Tuple[str, str]] = []
    for pat in AI_TEMPLATE_PATTERNS:
        for m in re.finditer(pat, ctx.content):
            hits.append((m.group(0), pat))
    score = 90 - len(hits) * 6
    # 四字格律堆砌惩罚
    chengyu = re.findall(r"[\u4e00-\u9fff]{4}(?:，|,)[\u4e00-\u9fff]{4}", ctx.content)
    score -= min(15, len(chengyu) * 2)
    return _clamp(score), hits


def score_payoff(ctx: ChapterContext, foreshadows: List[str]) -> Tuple[int, List[str]]:
    if not foreshadows:
        return 70, []  # 无大纲时给中性分
    hits: List[str] = []
    for fs in foreshadows:
        if fs and fs in ctx.content:
            hits.append(fs)
    if not hits:
        return 55, []
    score = 60 + min(30, len(hits) * 8)
    return _clamp(score), hits


def score_share(ctx: ChapterContext) -> Tuple[int, List[str]]:
    """传播性：寻找简短有力、有修辞反差的句子。"""
    candidates: List[str] = []
    # 对话中的短句
    for d in ctx.dialogues:
        chars = _count_chinese(d)
        if 8 <= chars <= 30 and (
            "你" in d or "我" in d or "让" in d
        ) and any(p in d for p in ["。", "！", "？", ".", "!", "?"]):
            candidates.append(d)
    # 段落中的金句（句号前后对称 / 反转）
    for para in ctx.paragraphs:
        for s in re.split(r"[。！？]", para):
            chars = _count_chinese(s)
            if 8 <= chars <= 40 and "，" in s and ("。" in para):
                # 粗略：逗号分割后两半长度接近的句子更有"对仗感"
                parts = s.split("，")
                if len(parts) == 2:
                    a, b = _count_chinese(parts[0]), _count_chinese(parts[1])
                    if abs(a - b) <= 3 and min(a, b) >= 3:
                        candidates.append(s.strip())
    # 去重
    uniq: List[str] = []
    seen = set()
    for c in candidates:
        key = c.strip()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    score = 55 + min(35, len(uniq) * 6)
    return _clamp(score), uniq[:5]


def compute_scores(ctx: ChapterContext, foreshadows: List[str]) -> ReaderScore:
    end_score, hook_type, hook_quote = score_end_hook(ctx)
    retention = score_retention(ctx)
    surprise, surprise_hits = score_surprise(ctx)
    immersion, ai_hits = score_immersion(ctx)
    payoff, payoff_hits = score_payoff(ctx, foreshadows)
    share, share_candidates = score_share(ctx)
    return ReaderScore(
        end_hook=end_score,
        retention=retention,
        surprise=surprise,
        immersion=immersion,
        payoff=payoff,
        share=share,
        hook_quote=hook_quote,
        hook_type=hook_type,
        ai_hits=ai_hits,
        surprise_hits=surprise_hits,
        payoff_hits=payoff_hits,
        share_candidates=share_candidates,
    )


# ───────────────────────────── 报告渲染 ─────────────────────────────


def render_report(
    ctx: ChapterContext,
    score: ReaderScore,
    reader_profile: object,
    threshold: int,
    foreshadows: List[str],
) -> str:
    total = score.total()
    status = "✅ 通过" if total >= threshold else "❌ 未达阈值"

    lines: List[str] = []
    lines.append(f"# 第 {ctx.number} 章 · 读者审稿报告\n")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 章节：第 {ctx.number} 章 - {ctx.title}")
    lines.append(f"> 章节字数：{ctx.word_count}")
    profile_disp = ", ".join(reader_profile) if isinstance(reader_profile, list) else str(reader_profile)
    lines.append(f"> 模拟读者画像：{profile_disp}")
    lines.append(f"> 评分模式：启发式（heuristic）\n")
    lines.append("---\n")

    lines.append(f"## 总分：{total:.2f} / 100  {status}\n")
    lines.append("| 子分项 | 得分 | 权重 | 加权 |")
    lines.append("|-------|:----:|:----:|:----:|")
    for sub, weight in SUB_WEIGHTS.items():
        v = getattr(score, sub)
        lines.append(f"| {sub}_score | {v} | {weight} | {v * weight / 100:.2f} |")
    lines.append(f"| **合计** | **—** | **100** | **{total:.2f}** |\n")

    lines.append("---\n")
    lines.append(f"## §1 章末钩子分析（end_hook_score: {score.end_hook}）\n")
    lines.append(f"**钩子类型**：{score.hook_type}")
    lines.append(f"**钩子位置**：末段（第 {len(ctx.paragraphs)} 段）")
    lines.append("**末段引用**：\n")
    quote = score.hook_quote.strip().replace("\n", " ")
    lines.append(f"> {quote}\n")
    if score.end_hook >= 80:
        lines.append("✅ 钩子强度良好，具备悬念元素。")
    elif score.end_hook >= 70:
        lines.append("🟡 钩子可用，但可考虑加强一个肢体反应或反转元素。")
    else:
        lines.append("❌ 钩子偏弱，建议参考 hook-techniques.md「悬念钩子十三式」重写末段。")
    lines.append("")

    lines.append("---\n")
    lines.append(f"## §2 追读力诊断（retention_score: {score.retention}）\n")
    lines.append(f"- 本章字数：{ctx.word_count}（默认不设硬下限；800-6000 视为常规可读区间）")
    d_chars = sum(_count_chinese(d) for d in ctx.dialogues)
    ratio = d_chars / max(1, ctx.word_count) * 100
    lines.append(f"- 对话字数占比：{ratio:.1f}% （目标 ≥ 30%）")
    avg = ctx.word_count / max(1, len(ctx.paragraphs))
    lines.append(f"- 平均段落字数：{avg:.0f}（>400 将显著降低追读力）")
    lines.append("")

    lines.append("---\n")
    lines.append(f"## §3 出戏检测（immersion_score: {score.immersion}）\n")
    if not score.ai_hits:
        lines.append("✅ 未命中 AI 模板化句式，沉浸度良好。\n")
    else:
        lines.append(f"发现 **{len(score.ai_hits)} 处出戏点**（AI 模板化句式）：\n")
        for i, (match, _pat) in enumerate(score.ai_hits[:10], 1):
            lines.append(f"### 出戏点 {i}")
            lines.append(f"> {match}\n")
            lines.append("❌ **问题**：AI 模板化句式，老读者易立即识别。")
            lines.append("💡 **建议**：改为具体动作 / 细节描写。参考 phase3-writing.md §10 深度润色。\n")

    lines.append("---\n")
    lines.append(f"## §4 意外感评估（surprise_score: {score.surprise}）\n")
    if score.surprise_hits:
        lines.append(f"✅ **本章预期外标识**：{', '.join(score.surprise_hits)}")
    else:
        lines.append("🟡 **未检测到明显的预期外标识**——建议至少 1 处反转或出人意料的信息。")
    lines.append("参考 [hook-techniques.md](../../../../references/guides/hook-techniques.md)「打破读者预期」\n")

    lines.append("---\n")
    lines.append(f"## §5 回报感（payoff_score: {score.payoff}）\n")
    if foreshadows:
        lines.append(f"前文伏笔候选关键词：{', '.join(foreshadows[:10])}")
        if score.payoff_hits:
            lines.append(f"✅ **本章回收**：{', '.join(score.payoff_hits)}")
        else:
            lines.append("❌ **本章未显式回收前文伏笔**——考虑补一个小回报。")
    else:
        lines.append("🟡 未在 01-大纲.md 找到显式伏笔字段，跳过自动回报分析。")
    lines.append("")

    lines.append("---\n")
    lines.append(f"## §6 传播性（share_score: {score.share}）\n")
    if score.share_candidates:
        lines.append("**截图候选**：\n")
        for i, s in enumerate(score.share_candidates, 1):
            stars = "★" * min(5, 2 + (len(s) // 10))
            lines.append(f"{i}. **{stars}** {s}")
    else:
        lines.append("🟡 未检测到明显的『截图候选』短句——考虑加一句对仗 / 反差对白。")
    lines.append("")

    lines.append("---\n")
    lines.append("## §7 弃书风险点\n")
    risk_level = "🟢 低"
    if total < threshold:
        risk_level = "🔴 高"
    elif total < threshold + 5:
        risk_level = "🟡 中"
    lines.append(f"**整体风险**：{risk_level}（总分 {total:.2f} vs 阈值 {threshold}）")
    lines.append("")

    lines.append("---\n")
    lines.append("## §8 修复建议（按优先级排序）\n")
    lines.append("| # | 优先级 | 位置 | 问题 | 修复 |")
    lines.append("|---|:------:|------|------|------|")
    suggestions: List[Tuple[str, str, str, str]] = []
    if score.end_hook < 70:
        suggestions.append(("P0", "末段", "章末钩子强度不足", "参考 hook-techniques.md「悬念钩子十三式」重写末段"))
    if score.immersion < 70 and score.ai_hits:
        suggestions.append(("P0", "正文多处", f"{len(score.ai_hits)} 处 AI 模板化句式", "逐句替换为具体动作/细节"))
    if score.retention < 70:
        suggestions.append(("P1", "正文节奏", "有效信息 / 对话比例 / 段落长度未达标", "参考 phase3-writing.md §6"))
    if score.surprise < 70:
        suggestions.append(("P1", "正文", "缺少预期外信息", "至少加 1 个反转锚点"))
    if score.payoff < 70 and foreshadows:
        suggestions.append(("P2", "下一章", "前文伏笔未回收", "在下一章回收至少 1 条伏笔"))
    if score.share < 70:
        suggestions.append(("P2", "正文", "缺少『截图句』", "加 1 句对仗 / 反差对白"))
    if not suggestions:
        lines.append("| — | — | — | 无明显问题 | 继续保持 |")
    else:
        for i, (pri, loc, issue, fix) in enumerate(suggestions, 1):
            lines.append(f"| {i} | {pri} | {loc} | {issue} | {fix} |")
    lines.append("")

    lines.append("---\n")
    lines.append("## §9 LLM / 主 Agent 深化审稿提示\n")
    lines.append("> 启发式仅提供基线分数。如需接入主 Agent 或 LLM API 进一步分析，请使用以下 prompt 模板：\n")
    lines.append(render_prompt_block(ctx, foreshadows, reader_profile))

    return "\n".join(lines)


def render_prompt_block(ctx: ChapterContext, foreshadows: List[str], reader_profile: object) -> str:
    profile_disp = ", ".join(reader_profile) if isinstance(reader_profile, list) else str(reader_profile)
    prompt = [
        "```prompt",
        f"你是一位模拟读者，画像：{profile_disp}",
        "阅读以下章节正文，给出 reader-simulator-spec.md 所定义的 6 项打分并按模板输出：",
        "",
        f"章节：第 {ctx.number} 章 - {ctx.title}",
        f"字数：{ctx.word_count}",
        f"大纲已登记的伏笔关键词：{', '.join(foreshadows[:15]) or '（无）'}",
        "",
        "评分项：end_hook / retention / surprise / immersion / payoff / share（0-100 整数）",
        "",
        "请严格按 reader-simulator-spec.md §reader_report.md 完整模板生成全部 §1-§9 内容。",
        "```",
    ]
    return "\n".join(prompt)


# ───────────────────────────── 回写 + 主流程 ─────────────────────────────


def write_back_plan(plan: Dict, chapter_number: int, score: ReaderScore, threshold: int) -> None:
    chapters = plan.setdefault("chapters", [])
    target = next((c for c in chapters if int(c.get("chapterNumber") or 0) == chapter_number), None)
    if not target:
        return
    gate_scores = target.setdefault("gateScores", {})
    total = score.total()
    gate_scores["reader"] = {
        "score": round(total, 2),
        "passed": total >= threshold,
        "subscores": score.as_subscore_dict(),
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def artifact_path(project_root: Path, chapter_number: int) -> Path:
    chapter_id = f"ch{chapter_number:03d}"
    return project_root / "04_editing" / "gate_artifacts" / chapter_id / "reader_report.md"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="读者模拟审稿（novelist v1.2.0）")
    parser.add_argument("--project-root", required=True, help="项目目录（必填）")
    parser.add_argument("--chapter", type=int, required=True, help="章节号（必填）")
    parser.add_argument("--threshold", type=int, default=None, help="读者维度通过线（默认读 gateThresholds.reader 或 70）")
    parser.add_argument("--reader-profile", default=None, help="覆盖 readerProfile（逗号分隔可多个）")
    parser.add_argument("--prompt-only", action="store_true", help="仅输出 LLM prompt，不写报告文件")
    parser.add_argument("--output", default=None, help="覆盖默认产物路径")
    parser.add_argument("--dry-run", action="store_true", help="不写回 02-写作计划.json")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"错误：项目目录不存在 - {project_root}", file=sys.stderr)
        return 2

    try:
        plan = load_plan(project_root)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"错误：读取 02-写作计划.json 失败 - {e}", file=sys.stderr)
        return 2

    threshold = args.threshold
    if threshold is None:
        threshold = int((plan.get("gateThresholds") or {}).get("reader", DEFAULT_THRESHOLD))

    reader_profile = args.reader_profile.split(",") if args.reader_profile else plan.get("readerProfile", "webnovel_veteran")
    if isinstance(reader_profile, list) and len(reader_profile) == 1:
        reader_profile = reader_profile[0]

    plan_entry = next((c for c in (plan.get("chapters") or []) if int(c.get("chapterNumber") or 0) == args.chapter), None)
    if not plan_entry:
        print(f"错误：02-写作计划.json 中未找到第 {args.chapter} 章", file=sys.stderr)
        return 2

    try:
        chapter_file = resolve_chapter_file(project_root, plan, args.chapter)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2

    ctx = load_chapter_context(chapter_file, plan_entry)
    foreshadows = load_outline_foreshadows(project_root)

    if args.prompt_only:
        print(render_prompt_block(ctx, foreshadows, reader_profile))
        return 0

    score = compute_scores(ctx, foreshadows)
    report = render_report(ctx, score, reader_profile, threshold, foreshadows)

    out_path = Path(args.output).expanduser() if args.output else artifact_path(project_root, args.chapter)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ 读者审稿报告已生成：{out_path}", file=sys.stderr)
    print(f"   总分：{score.total():.2f}  阈值：{threshold}  {'通过' if score.total() >= threshold else '未达阈值'}", file=sys.stderr)

    if not args.dry_run:
        write_back_plan(plan, args.chapter, score, threshold)
        save_plan(project_root, plan)
        print(f"✅ 已回写 02-写作计划.json · chapters[{args.chapter}].gateScores.reader", file=sys.stderr)

    return 0 if score.total() >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
