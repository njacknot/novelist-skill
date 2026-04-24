#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
command_alias.py — 命令别名路由与 lint 工具

用途：
1. 路由：将旧命令（/继续写 等）解析为新形式（/章 --续写）
2. Lint：扫描文档中残留的旧命令引用，防止回归

对应契约：references/advanced/command-contracts.md

使用示例：
    # 路由单条命令
    python3 scripts/command_alias.py resolve /继续写
    # → /章 --续写

    # 查看全部别名
    python3 scripts/command_alias.py list

    # Lint 扫描项目
    python3 scripts/command_alias.py lint
    # → 列出残留的旧命令 + 建议替换

    # Lint 排除特定文件（这些文件需要保留旧命令作为文档说明）
    python3 scripts/command_alias.py lint --allow-deprecated \\
        references/advanced/command-contracts.md \\
        references/advanced/command-playbook.md \\
        SKILL.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# 别名映射（与 command-contracts.md §四 保持同步）
# ---------------------------------------------------------------------------

ALIAS_MAP: dict[str, str] = {
    # /书
    "/一键开书": "/书 --开书",
    "/写全篇": "/书 --规划",
    "/改纲续写": "/书 --改纲",
    # /章
    "/继续写": "/章 --续写",
    "/写作": "/章 --写",
    "/续写": "/章 --续写",
    "/批量写作": "/章 --批量",
    "/修改章节": "/章 --修改",
    "/修复本章": "/章 --修复",
    # /检查
    "/更新记忆": "/检查 --记忆",
    "/检查一致性": "/检查 --一致性",
    "/风格校准": "/检查 --文风",
    "/节奏审查": "/检查 --节奏",
    # /门禁
    "/门禁检查": "/门禁 --运行",
    "/校稿": "/门禁 --校稿",  # 复合流程：含 --AI味 + publish_ready 生成
    # /检索
    "/剧情检索": "/检索 --剧情",
    "/更新剧情索引": "/检索 --索引重建",
    "/伏笔状态": "/检索 --伏笔",
    "/角色状态": "/检索 --角色",
    "/时间线": "/检索 --时间线",
    # /风格
    "/题材选风格": "/风格 --题材",
    "/风格提取": "/风格 --提取",
    "/仿写": "/风格 --仿写",
    "/拆书": "/风格 --拆书",
    "/风格迁移": "/风格 --迁移",
    "/风格库检索": "/风格 --查询",
    # /骚话
    "/骚话生成": "/骚话 --生成",
    "/骚话密度": "/骚话 --密度",
    "/骚话人设": "/骚话 --人设",
    # /骚话 单独（末尾放置，避免抢占 /骚话生成 等前缀匹配）
    "/骚话": "/骚话 --扫描",
    # /研究
    "/联网调研": "/研究 --搜索",
}

# 这些命令保留不变（不是被弃用的别名，而是独立命令或模式切换）
KEEP_AS_IS: set[str] = {
    "/简易模式",
    "/专业模式",
    "/新手模式",
    "/一键写书",
    "/建库",
    "/评测基线",
    "/安装到多工具",
}

# 主命令集（用于 lint 校验新形式命令格式合法性）
MAIN_COMMANDS: set[str] = {
    "/书", "/章", "/大纲", "/检查", "/门禁",
    "/检索", "/风格", "/骚话", "/研究",
}

# ---------------------------------------------------------------------------
# 核心 API
# ---------------------------------------------------------------------------

def resolve(command: str) -> str:
    """
    将旧命令解析为新形式。
    若是新形式或保留命令，原样返回。
    若无法识别，抛 KeyError。
    """
    command = command.strip()
    if not command.startswith("/"):
        raise ValueError(f"命令必须以 / 开头: {command!r}")

    # 保留命令
    if command in KEEP_AS_IS:
        return command

    # 新形式：/主 --子 ...
    parts = command.split()
    if parts[0] in MAIN_COMMANDS:
        return command

    # 旧形式：匹配别名（先完整匹配，再前缀匹配保留参数）
    if command in ALIAS_MAP:
        return ALIAS_MAP[command]

    # 带参数的旧命令，如 "/骚话生成 A7"
    head = parts[0]
    rest = parts[1:]
    if head in ALIAS_MAP:
        new_head = ALIAS_MAP[head]
        return f"{new_head} {' '.join(rest)}".strip()

    raise KeyError(f"未识别的命令: {command!r}。请查 command-contracts.md §四")


# ---------------------------------------------------------------------------
# Lint 扫描
# ---------------------------------------------------------------------------

# 匹配 ` `/旧命令` ` 形式（反引号包裹的命令）
# 注意：按长度降序排列，避免 /骚话 抢占 /骚话生成 的匹配
_ALIAS_KEYS_DESC = sorted(ALIAS_MAP.keys(), key=len, reverse=True)
_LINT_PATTERN = re.compile(
    r"`(" + "|".join(re.escape(k) for k in _ALIAS_KEYS_DESC) + r")`"
)

# 默认允许保留旧命令的文件（文档说明用）
DEFAULT_ALLOWLIST = {
    "references/advanced/command-contracts.md",
    "references/advanced/command-playbook.md",
    "references/guides/saohua-README.md",  # §旧命令兼容 需保留旧名演示
    "scripts/command_alias.py",
    "SKILL.md",  # 只在 §别名速查小节保留
}


def lint_file(path: Path) -> list[tuple[int, str, str]]:
    """返回 [(行号, 旧命令, 建议新命令), ...]"""
    hits: list[tuple[int, str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return hits
    for lineno, line in enumerate(lines, 1):
        for m in _LINT_PATTERN.finditer(line):
            old = m.group(1)
            new = ALIAS_MAP[old]
            hits.append((lineno, old, new))
    return hits


def lint_project(
    project_root: Path,
    allowlist: set[str] | None = None,
) -> dict[Path, list[tuple[int, str, str]]]:
    allow = set(allowlist or DEFAULT_ALLOWLIST)
    results: dict[Path, list[tuple[int, str, str]]] = {}
    for md in project_root.rglob("*.md"):
        rel = md.relative_to(project_root).as_posix()
        if rel in allow:
            continue
        hits = lint_file(md)
        if hits:
            results[md] = hits
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        print(resolve(args.command))
        return 0
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _cmd_list(_: argparse.Namespace) -> int:
    width = max(len(k) for k in ALIAS_MAP)
    print(f"# 共 {len(ALIAS_MAP)} 条别名")
    for old, new in ALIAS_MAP.items():
        print(f"  {old:<{width}}  →  {new}")
    print(f"\n# 保留命令（不变） {len(KEEP_AS_IS)} 条")
    for cmd in sorted(KEEP_AS_IS):
        print(f"  {cmd}")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    allow = set(args.allow_deprecated) if args.allow_deprecated else set(DEFAULT_ALLOWLIST)
    results = lint_project(root, allow)
    if not results:
        print(f"✅ 无旧命令残留（扫描根目录：{root}）")
        return 0

    total = sum(len(v) for v in results.values())
    print(f"⚠ 发现 {total} 处残留旧命令，涉及 {len(results)} 个文件：\n")
    for path, hits in sorted(results.items()):
        rel = path.relative_to(root).as_posix()
        print(f"📄 {rel}")
        for lineno, old, new in hits:
            print(f"   L{lineno}: `{old}`  →  `{new}`")
        print()
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="命令别名路由与 lint 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("resolve", help="将旧命令解析为新形式")
    pr.add_argument("command", help="命令字符串，如 /继续写")
    pr.set_defaults(func=_cmd_resolve)

    pl = sub.add_parser("list", help="列出所有别名映射")
    pl.set_defaults(func=_cmd_list)

    pg = sub.add_parser("lint", help="扫描项目中残留的旧命令")
    pg.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="项目根目录（默认：脚本所在目录的上一级）",
    )
    pg.add_argument(
        "--allow-deprecated",
        nargs="*",
        help="允许保留旧命令的文件路径（相对项目根），不指定则使用默认 allowlist",
    )
    pg.set_defaults(func=_cmd_lint)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
