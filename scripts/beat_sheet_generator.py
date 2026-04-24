#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat_sheet_generator.py — Beat Sheet 流水线工具（零外部依赖）

实现 references/advanced/million-word-roadmap.md §8「Beat Sheet 流水线」：
- generate：读取大纲 + 上一章摘要 → 输出 Beat Sheet Prompt 或骨架 JSON
- validate：校验 beat sheet 结构
- status：查看当前章节 beat 完成状态

依赖：仅 Python 标准库（zero-dep）。
退出码：0 成功/通过 / 1 校验失败 / 2 输入错误
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


# ───────────────────────────── Beat 类型与规则 ─────────────────────────────

BEAT_TYPES = {
    "conflict":    {"cn": "冲突型", "desc": "角色之间的对抗、争论、战斗或外部威胁"},
    "revelation":  {"cn": "揭示型", "desc": "新信息、秘密揭露、身份暴露、线索发现"},
    "decision":    {"cn": "抉择型", "desc": "角色做出重要选择，改变后续走向"},
    "bond":        {"cn": "羁绊型", "desc": "角色关系的深化、信任建立、情感连接"},
    "setup":       {"cn": "铺垫型", "desc": "为后续剧情埋下伏笔、介绍设定、世界观展开"},
    "escalation":  {"cn": "升级型", "desc": "紧张度升高，局势恶化，危机加深"},
    "relief":      {"cn": "缓冲型", "desc": "紧张后的放松，日常互动，幽默段落"},
    "climax":      {"cn": "高潮型", "desc": "本章的张力最高点，决定性时刻"},
    "cliffhanger": {"cn": "悬念型", "desc": "留下未解之谜，制造追读欲望"},
}

# 校验规则
RULES = {
    "min_beats": 3,
    "max_beats": 6,
    "must_have_conflict": True,      # 至少 1 个冲突型 beat
    "last_must_be_hook": True,       # 最后一个 beat 必须留悬念
    "no_consecutive_same_type": True, # 不得连续 2 个同类型
    "word_per_beat_min": 500,
    "word_per_beat_max": 1500,
}


# ───────────────────────────── Beat Sheet 骨架 ─────────────────────────────


def _empty_beat_sheet(chapter: int) -> Dict[str, Any]:
    return {
        "chapter": chapter,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "chapter_goal": "",
        "beats": [],
        "total_target_words": 0,
    }


def generate_beat_prompt(
    chapter: int,
    chapter_goal: str,
    outline_snippet: str,
    prev_summary: str,
    beat_count: int = 4,
) -> str:
    """生成让 Agent 填写的 Beat Sheet Prompt。"""
    type_list = "\n".join(f"  - `{k}` ({v['cn']}): {v['desc']}" for k, v in BEAT_TYPES.items())

    prompt = f"""请为第 {chapter} 章生成 Beat Sheet（{beat_count} 个 beat）。

## 本章目标
{chapter_goal or '（待填写）'}

## 大纲片段
{outline_snippet or '（无）'}

## 上一章摘要
{prev_summary or '（无）'}

## Beat 类型说明
{type_list}

## 输出格式

请输出以下 JSON 格式：

```json
{{
  "chapter": {chapter},
  "chapter_goal": "一句话描述本章目标",
  "beats": [
    {{
      "beat_id": 1,
      "type": "setup",
      "summary": "50-100 字描述这个 beat 要讲什么",
      "target_words": 800,
      "characters": ["角色A", "角色B"],
      "location": "场景地点",
      "tension_level": 3,
      "notes": "给扩写 Agent 的特别指示"
    }}
  ]
}}
```

## 规则（必须遵守）
1. beat 数量: {beat_count}（允许 {RULES['min_beats']}-{RULES['max_beats']}）
2. 至少 1 个 `conflict` 类型的 beat
3. 最后一个 beat 必须是 `cliffhanger` 或包含悬念元素
4. 不得连续 2 个同类型 beat
5. 每个 beat 的 target_words 在 {RULES['word_per_beat_min']}-{RULES['word_per_beat_max']} 之间
6. 不得在扩写时提前引入后续 beat 的冲突
7. tension_level 1-5 标记张力等级，全章应有波峰波谷
"""
    return prompt


def generate_skeleton(chapter: int, beat_count: int = 4) -> Dict[str, Any]:
    """生成空白 beat sheet 骨架。"""
    sheet = _empty_beat_sheet(chapter)

    # 默认分配模板
    if beat_count == 3:
        template = ["setup", "conflict", "cliffhanger"]
    elif beat_count == 4:
        template = ["setup", "conflict", "bond", "cliffhanger"]
    elif beat_count == 5:
        template = ["setup", "escalation", "conflict", "relief", "cliffhanger"]
    else:
        template = ["setup"] + ["conflict"] * (beat_count - 2) + ["cliffhanger"]
        # 插入变化
        if beat_count >= 4:
            template[2] = "bond"
        if beat_count >= 5:
            template[3] = "revelation"

    target_per_beat = 3500 // beat_count

    for i, btype in enumerate(template, 1):
        sheet["beats"].append({
            "beat_id": i,
            "type": btype,
            "summary": f"（待填写：{BEAT_TYPES.get(btype, {}).get('cn', btype)}）",
            "target_words": target_per_beat,
            "characters": [],
            "location": "",
            "tension_level": 3,
            "notes": "",
        })

    sheet["total_target_words"] = target_per_beat * beat_count
    return sheet


# ───────────────────────────── 校验 ─────────────────────────────


def validate_beat_sheet(sheet: Dict) -> List[Dict]:
    """校验 beat sheet 结构。返回问题列表。"""
    issues: List[Dict] = []
    beats = sheet.get("beats", [])

    # 数量检查
    if len(beats) < RULES["min_beats"]:
        issues.append({
            "severity": "P0",
            "detail": f"beat 数量不足: {len(beats)} < {RULES['min_beats']}",
        })
    if len(beats) > RULES["max_beats"]:
        issues.append({
            "severity": "P1",
            "detail": f"beat 数量过多: {len(beats)} > {RULES['max_beats']}",
        })

    # 类型检查
    types = [b.get("type", "") for b in beats]

    # 至少 1 个冲突型
    if RULES["must_have_conflict"]:
        conflict_count = sum(1 for t in types if t in ("conflict", "climax"))
        if conflict_count == 0:
            issues.append({
                "severity": "P0",
                "detail": "缺少冲突型 beat（至少需要 1 个 conflict 或 climax）",
            })

    # 最后一个必须留悬念
    if RULES["last_must_be_hook"] and beats:
        last_type = types[-1]
        if last_type not in ("cliffhanger", "revelation", "escalation"):
            issues.append({
                "severity": "P0",
                "detail": f"最后一个 beat 类型为 '{last_type}'，应为 cliffhanger/revelation/escalation",
            })

    # 不得连续同类型
    if RULES["no_consecutive_same_type"]:
        for i in range(1, len(types)):
            if types[i] == types[i - 1]:
                issues.append({
                    "severity": "P1",
                    "detail": f"beat {i} 和 {i + 1} 类型相同: '{types[i]}'",
                })

    # 字数检查
    for b in beats:
        tw = b.get("target_words", 0)
        if tw < RULES["word_per_beat_min"]:
            issues.append({
                "severity": "P1",
                "detail": f"beat {b.get('beat_id', '?')} 目标字数过少: {tw} < {RULES['word_per_beat_min']}",
            })
        if tw > RULES["word_per_beat_max"]:
            issues.append({
                "severity": "P1",
                "detail": f"beat {b.get('beat_id', '?')} 目标字数过多: {tw} > {RULES['word_per_beat_max']}",
            })

    # 张力曲线：应有波峰
    tensions = [b.get("tension_level", 3) for b in beats]
    if tensions and max(tensions) <= min(tensions):
        issues.append({
            "severity": "P1",
            "detail": "张力曲线过于平坦（所有 beat 的 tension_level 相同）",
        })

    # 摘要不能为空
    empty_summaries = [b for b in beats if not b.get("summary", "").strip() or "待填写" in b.get("summary", "")]
    if empty_summaries:
        issues.append({
            "severity": "P1",
            "detail": f"{len(empty_summaries)} 个 beat 的 summary 未填写",
        })

    return issues


# ───────────────────────────── CLI ─────────────────────────────


def cmd_generate(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else None
    chapter = args.chapter
    beat_count = args.beat_count

    # 尝试读取大纲片段
    outline_snippet = ""
    prev_summary = ""
    if project_root:
        outline_path = project_root / "01-大纲.md"
        if outline_path.exists():
            text = outline_path.read_text(encoding="utf-8")
            # 提取当前章的大纲片段
            pattern = rf"第\s*{chapter}\s*章"
            match = re.search(pattern, text)
            if match:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 500)
                outline_snippet = text[start:end].strip()

    if args.prompt_only:
        prompt = generate_beat_prompt(
            chapter, args.chapter_goal or "", outline_snippet, prev_summary, beat_count
        )
        print(prompt)
    else:
        skeleton = generate_skeleton(chapter, beat_count)
        skeleton["chapter_goal"] = args.chapter_goal or ""
        print(json.dumps(skeleton, ensure_ascii=False, indent=2))

        if args.output:
            Path(args.output).expanduser().write_text(
                json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"✅ Beat sheet 骨架已写入: {args.output}", file=sys.stderr)

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    beat_file = Path(args.beat_file).expanduser().resolve()
    if not beat_file.exists():
        print(f"错误: 文件不存在 - {beat_file}", file=sys.stderr)
        return 2

    with beat_file.open("r", encoding="utf-8") as f:
        sheet = json.load(f)

    issues = validate_beat_sheet(sheet)

    if not issues:
        print("✅ Beat sheet 校验通过", file=sys.stderr)
        return 0

    p0 = [i for i in issues if i["severity"] == "P0"]
    p1 = [i for i in issues if i["severity"] == "P1"]
    print(f"⚠ 发现 {len(issues)} 个问题（P0: {len(p0)}, P1: {len(p1)}）：", file=sys.stderr)
    for iss in issues:
        prefix = "🔴" if iss["severity"] == "P0" else "🟡"
        print(f"  {prefix} [{iss['severity']}] {iss['detail']}", file=sys.stderr)

    return 1 if p0 else 0


def cmd_status(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    beats_dir = project_root / "00_memory" / "beat_sheets"
    if not beats_dir.exists():
        print("  （无 beat sheet 文件）")
        return 0

    files = sorted(beats_dir.glob("*.json"))
    print(f"\n📋 Beat Sheet 状态（共 {len(files)} 个）\n")
    for f in files:
        try:
            with f.open("r", encoding="utf-8") as fh:
                sheet = json.load(fh)
            ch = sheet.get("chapter", "?")
            beats = sheet.get("beats", [])
            goal = sheet.get("chapter_goal", "")[:40]
            issues = validate_beat_sheet(sheet)
            status = "✅" if not issues else "⚠"
            print(f"  {status} 第 {ch} 章: {len(beats)} beats · {goal}")
        except (json.JSONDecodeError, IOError):
            print(f"  ❌ {f.name}: 读取失败")
    print()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Beat Sheet 流水线工具（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("generate", help="生成 beat sheet")
    pg.add_argument("--project-root", default=None)
    pg.add_argument("--chapter", type=int, required=True)
    pg.add_argument("--beat-count", type=int, default=4)
    pg.add_argument("--chapter-goal", default=None, help="本章目标（一句话）")
    pg.add_argument("--prompt-only", action="store_true", help="仅输出 Prompt")
    pg.add_argument("--output", default=None)
    pg.set_defaults(func=cmd_generate)

    pv = sub.add_parser("validate", help="校验 beat sheet")
    pv.add_argument("--beat-file", required=True, help="beat sheet JSON 文件")
    pv.set_defaults(func=cmd_validate)

    ps = sub.add_parser("status", help="查看 beat sheet 状态")
    ps.add_argument("--project-root", required=True)
    ps.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
