#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_humanizer.py — 去 AI 味检测与润色工具（零外部依赖）

实现 references/advanced/humanizer-guide.md 的完整 7 大 AI 写作模式检测：
- detect：扫描章节正文 → JSON 输出命中列表
- report：生成可读 Markdown 报告
- prompt：输出两遍式润色 Prompt

依赖：仅 Python 标准库（zero-dep）。
退出码：0 通过（AI 味低） / 1 超标 / 2 输入错误
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 7 大 AI 写作模式检测规则 ─────────────────────────────

# 模式 1: AI 高频词汇
AI_VOCAB: List[Tuple[str, str, str]] = [
    # (词/正则, 问题描述, 改法建议)
    (r"不禁", "剥夺角色主动性", "直接写角色的行动"),
    (r"映入眼帘", "陈词滥调的视觉过渡", "直接写看到了什么"),
    (r"心中暗道|暗自思忖|暗自想道", "内心独白套话", "删除或改为行动"),
    (r"嘴角微扬|勾起一抹弧度|嘴角上扬", "微笑套话（AI 特征极强）", "\"他笑了\"或删掉"),
    (r"不由自主|情不自禁", "主体性剥夺", "改为角色主动发出行动"),
    (r"只见|此时此刻", "场景过渡套话", "直接切换场景"),
    (r"目光如炬|目光深邃|目光灼灼", "眼睛描写套话", "写眼睛看向哪里、做了什么"),
    (r"脸色一变|身形一顿|脸色骤变", "反应套话", "写具体的生理反应"),
    (r"眼中闪过一[丝抹道]", "AI 模板化眼神描写", "换具体动作"),
    (r"心中涌起一[阵股丝]", "AI 模板化情感描写", "用行为展现"),
    (r"握紧了?拳头", "握拳套话", "换其他紧张动作"),
    (r"下意识地", "频繁使用削弱角色主体性", "大部分情况可删除"),
    (r"仿佛.{2,15}一般", "过度比喻", "用具体感知描写替代"),
]

# 模式 2: 弱化副词泛滥（每千字 > 3 个即报警）
WEAK_ADVERBS = [
    "微微", "淡淡", "缓缓", "轻轻", "悄然", "默默", "隐隐",
    "静静", "渐渐", "慢慢", "稍稍", "略略",
]
WEAK_ADVERB_THRESHOLD_PER_1K = 3

# 模式 3: 意义膨胀
INFLATION_WORDS: List[Tuple[str, str]] = [
    ("前所未有", "删掉，用具体后续影响替代"),
    ("意义深远", "改为具体的后续变化"),
    ("可谓", "直接陈述，不要加评价"),
    ("堪称", "直接陈述"),
    ("不可估量", "用具体数字或后果替代"),
    ("翻天覆地", "写具体发生了什么"),
]

# 模式 4: 通用结论套话
CONCLUSION_CLICHES: List[Tuple[str, str]] = [
    ("未来可期", "用悬念或具体行动结尾"),
    ("前途无量", "删掉，用行动展示"),
    ("充满希望", "用角色的下一步行动替代"),
    ("满怀期待", "用具体准备动作替代"),
    ("崭新的篇章", "删掉或用具体场景结尾"),
]

# 模式 5: 论文式段落结构
ESSAY_MARKERS: List[Tuple[str, str]] = [
    ("不难看出", "直接写结论行动"),
    ("由此可见", "删掉，用行动推进"),
    ("事实上", "大部分情况可删除"),
    ("值得注意的是", "直接写要注意什么"),
    ("显而易见", "删掉"),
    ("总而言之", "小说里不需要总结"),
    ("综上所述", "小说里不需要总结"),
    ("换句话说", "大部分情况可删除"),
]

# 模式 6: 正式语体入侵
FORMAL_REGISTER: List[Tuple[str, str]] = [
    ("于是乎", "改口语化表达或删掉"),
    ("与此同时", "删掉或用\"这边...那边...\""),
    ("从而", "改为\"就\"或删掉"),
    ("因而", "改为\"所以\"或删掉"),
    ("诚然", "删掉"),
    ("一方面.*另一方面", "拆成两个场景分别写"),
    ("综合考虑", "小说正文不需要这种表达"),
    ("客观来说", "删掉"),
    ("不可否认", "删掉，直接写"),
]

# 模式 7: 排比三连（A、B 和 C 堆砌）
TRIPLE_PATTERN = re.compile(
    r"([\u4e00-\u9fff]{1,8})[、，,]([\u4e00-\u9fff]{1,8})[和与及以及还有]([\u4e00-\u9fff]{1,8})"
)


# ───────────────────────────── 数据结构 ─────────────────────────────


@dataclass
class Hit:
    """单个命中。"""
    pattern_id: int
    category: str  # 1-7 的模式编号
    category_name: str
    matched_text: str
    suggestion: str
    line_number: int = 0
    severity: str = "P1"  # P0/P1/P2


@dataclass
class DetectionResult:
    """检测结果。"""
    file_path: str
    word_count: int
    hits: List[Hit] = field(default_factory=list)
    adverb_density: float = 0.0  # 每千字弱化副词数
    triple_count: int = 0
    ai_score: int = 0  # 0-100，越高越像 AI 写的

    def summary(self) -> Dict[str, int]:
        cats: Dict[str, int] = {}
        for h in self.hits:
            cats[h.category_name] = cats.get(h.category_name, 0) + 1
        return cats


# ───────────────────────────── 核心检测 ─────────────────────────────


def _count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def detect(content: str, filepath: str = "") -> DetectionResult:
    """执行 7 大模式检测。"""
    word_count = _count_chinese(content)
    lines = content.splitlines()
    hits: List[Hit] = []
    pid = 0

    # ——— 模式 1: AI 高频词汇 ———
    for pattern, problem, fix in AI_VOCAB:
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pattern, line):
                pid += 1
                hits.append(Hit(
                    pattern_id=pid,
                    category="1",
                    category_name="AI高频词汇",
                    matched_text=m.group(0),
                    suggestion=fix,
                    line_number=i,
                    severity="P1",
                ))

    # ——— 模式 2: 弱化副词泛滥 ———
    adverb_total = 0
    for adv in WEAK_ADVERBS:
        count = content.count(adv)
        adverb_total += count
        if count >= 3:  # 单个副词出现 3+ 次报告
            pid += 1
            hits.append(Hit(
                pattern_id=pid,
                category="2",
                category_name="弱化副词泛滥",
                matched_text=f"{adv} × {count}",
                suggestion=f"删除大部分'{adv}'，仅保留真正需要强调微弱程度的",
                severity="P1",
            ))
    adverb_density = adverb_total / max(1, word_count) * 1000

    if adverb_density > WEAK_ADVERB_THRESHOLD_PER_1K:
        pid += 1
        hits.append(Hit(
            pattern_id=pid,
            category="2",
            category_name="弱化副词泛滥",
            matched_text=f"总密度 {adverb_density:.1f}/千字（阈值 {WEAK_ADVERB_THRESHOLD_PER_1K}）",
            suggestion="全局删减弱化副词",
            severity="P0",
        ))

    # ——— 模式 3: 意义膨胀 ———
    for word, fix in INFLATION_WORDS:
        for i, line in enumerate(lines, 1):
            if word in line:
                pid += 1
                hits.append(Hit(
                    pattern_id=pid, category="3", category_name="意义膨胀",
                    matched_text=word, suggestion=fix, line_number=i, severity="P2",
                ))

    # ——— 模式 4: 通用结论套话 ———
    for word, fix in CONCLUSION_CLICHES:
        for i, line in enumerate(lines, 1):
            if word in line:
                pid += 1
                hits.append(Hit(
                    pattern_id=pid, category="4", category_name="通用结论套话",
                    matched_text=word, suggestion=fix, line_number=i, severity="P1",
                ))

    # ——— 模式 5: 论文式段落结构 ———
    for word, fix in ESSAY_MARKERS:
        for i, line in enumerate(lines, 1):
            if word in line:
                pid += 1
                hits.append(Hit(
                    pattern_id=pid, category="5", category_name="论文式段落结构",
                    matched_text=word, suggestion=fix, line_number=i, severity="P0",
                ))

    # ——— 模式 6: 正式语体入侵 ———
    for word, fix in FORMAL_REGISTER:
        for i, line in enumerate(lines, 1):
            if re.search(word, line):
                pid += 1
                hits.append(Hit(
                    pattern_id=pid, category="6", category_name="正式语体入侵",
                    matched_text=re.search(word, line).group(0) if re.search(word, line) else word,
                    suggestion=fix, line_number=i, severity="P1",
                ))

    # ——— 模式 7: 排比三连 ———
    triple_count = 0
    for i, line in enumerate(lines, 1):
        for m in TRIPLE_PATTERN.finditer(line):
            triple_count += 1
            if triple_count >= 3:  # 3 次以上才报告
                pid += 1
                hits.append(Hit(
                    pattern_id=pid, category="7", category_name="排比三连",
                    matched_text=m.group(0),
                    suggestion="检查三元组是否可删一项", line_number=i, severity="P2",
                ))

    # 计算 AI 味分数（0-100）
    # 命中越多越像 AI
    ai_score = min(100, len(hits) * 5 + int(adverb_density * 8))

    return DetectionResult(
        file_path=filepath,
        word_count=word_count,
        hits=hits,
        adverb_density=round(adverb_density, 2),
        triple_count=triple_count,
        ai_score=ai_score,
    )


# ───────────────────────────── 报告渲染 ─────────────────────────────


def render_report(result: DetectionResult) -> str:
    """生成 Markdown 报告。"""
    lines: List[str] = []
    lines.append("# 去 AI 味检测报告\n")
    lines.append(f"> 文件: {result.file_path}")
    lines.append(f"> 字数: {result.word_count}")
    lines.append(f"> 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> AI 味指数: **{result.ai_score}/100**（越低越好）\n")

    status = "✅ AI 味较低" if result.ai_score < 30 else "🟡 有 AI 痕迹" if result.ai_score < 60 else "🔴 AI 味明显"
    lines.append(f"## 总评: {status}\n")

    # 按类别分组
    summary = result.summary()
    lines.append("## 各模式命中统计\n")
    lines.append("| 模式 | 命中数 |")
    lines.append("|------|:------:|")
    category_names = [
        "AI高频词汇", "弱化副词泛滥", "意义膨胀",
        "通用结论套话", "论文式段落结构", "正式语体入侵", "排比三连",
    ]
    for cn in category_names:
        count = summary.get(cn, 0)
        icon = "🔴" if count >= 5 else "🟡" if count >= 2 else "🟢"
        lines.append(f"| {icon} {cn} | {count} |")
    lines.append(f"\n弱化副词密度: {result.adverb_density:.1f}/千字（阈值 {WEAK_ADVERB_THRESHOLD_PER_1K}）\n")

    # 按严重度分组输出
    for severity in ("P0", "P1", "P2"):
        sev_hits = [h for h in result.hits if h.severity == severity]
        if not sev_hits:
            continue
        label = {"P0": "🔴 严重", "P1": "🟡 建议修复", "P2": "🟢 可选优化"}[severity]
        lines.append(f"## {label}（{len(sev_hits)} 处）\n")
        lines.append("| # | 行号 | 类型 | 命中 | 建议 |")
        lines.append("|---|:----:|------|------|------|")
        for i, h in enumerate(sev_hits[:30], 1):  # 最多显示 30 条
            ln = f"L{h.line_number}" if h.line_number else "—"
            lines.append(f"| {i} | {ln} | {h.category_name} | {h.matched_text} | {h.suggestion} |")
        if len(sev_hits) > 30:
            lines.append(f"\n... 还有 {len(sev_hits) - 30} 处（省略）")
        lines.append("")

    return "\n".join(lines)


def render_prompt(content: str, result: DetectionResult) -> str:
    """生成两遍式润色 Prompt。"""
    top_hits = sorted(result.hits, key=lambda h: ("P0", "P1", "P2").index(h.severity))[:15]
    hit_desc = "\n".join(f"  - L{h.line_number}: \"{h.matched_text}\" → {h.suggestion}" for h in top_hits)

    prompt = f"""你是一位资深网文编辑，现在要对以下章节进行"去 AI 味"润色。

## 第一遍：清除 AI 模式

检测到以下 {len(result.hits)} 处 AI 写作痕迹（按优先级排列前 15 条）：

{hit_desc}

请逐一处理以上问题，原则：
1. 用具体细节替代抽象套话
2. 用行动替代状态描述
3. 删除大部分弱化副词（微微、淡淡、缓缓等）
4. 对话标签统一用"说"或直接删除
5. 删除论文式开头（不难看出、事实上等）

## 第二遍：AI 自审

完成第一遍后，对自己的修改稿提问：
> "这段文字哪些地方还是明显 AI 生成的感觉？"

列出 3-5 条具体问题，然后针对这些问题再次修改后输出最终版。

## 约束
- 不要改变剧情和人物行为
- 保持原文的信息量
- 节奏变化：短句和长句交替使用
"""
    return prompt


# ───────────────────────────── CLI ─────────────────────────────


def cmd_detect(args: argparse.Namespace) -> int:
    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    content = chapter_file.read_text(encoding="utf-8")
    result = detect(content, str(chapter_file))

    output = {
        "file": result.file_path,
        "word_count": result.word_count,
        "ai_score": result.ai_score,
        "adverb_density": result.adverb_density,
        "total_hits": len(result.hits),
        "summary": result.summary(),
        "hits": [
            {
                "category": h.category_name,
                "severity": h.severity,
                "line": h.line_number,
                "matched": h.matched_text,
                "suggestion": h.suggestion,
            }
            for h in result.hits
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    threshold = args.threshold
    return 0 if result.ai_score < threshold else 1


def cmd_report(args: argparse.Namespace) -> int:
    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    content = chapter_file.read_text(encoding="utf-8")
    result = detect(content, str(chapter_file))
    report = render_report(result)

    if args.output:
        Path(args.output).expanduser().write_text(report, encoding="utf-8")
        print(f"✅ 报告已写入: {args.output}", file=sys.stderr)
    else:
        print(report)

    print(f"AI 味指数: {result.ai_score}/100", file=sys.stderr)
    return 0 if result.ai_score < args.threshold else 1


def cmd_prompt(args: argparse.Namespace) -> int:
    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    content = chapter_file.read_text(encoding="utf-8")
    result = detect(content, str(chapter_file))
    prompt = render_prompt(content, result)
    print(prompt)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="去 AI 味检测与润色工具（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("detect", help="检测 AI 写作模式（JSON 输出）")
    pd.add_argument("--chapter-file", required=True, help="章节文件路径")
    pd.add_argument("--threshold", type=int, default=50, help="AI 味指数阈值（默认 50）")
    pd.set_defaults(func=cmd_detect)

    pr = sub.add_parser("report", help="生成 Markdown 检测报告")
    pr.add_argument("--chapter-file", required=True, help="章节文件路径")
    pr.add_argument("--output", default=None, help="输出文件路径")
    pr.add_argument("--threshold", type=int, default=50, help="AI 味指数阈值（默认 50）")
    pr.set_defaults(func=cmd_report)

    pp = sub.add_parser("prompt", help="输出两遍式润色 Prompt")
    pp.add_argument("--chapter-file", required=True, help="章节文件路径")
    pp.set_defaults(func=cmd_prompt)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
