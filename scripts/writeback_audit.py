#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目回写快照审计工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TRACKED_PATTERNS: tuple[str, ...] = (
    "02-写作计划.json",
    "00_memory/*.md",
    "00_memory/*.json",
    "01-大纲.md",
    "00-人物档案.md",
    "03_manuscript/*.md",
    "04_editing/control_cards/*.md",
)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tracked_files(project_root: Path) -> List[Path]:
    files: dict[str, Path] = {}
    for pattern in TRACKED_PATTERNS:
        for path in project_root.glob(pattern):
            if path.is_file():
                files[path.relative_to(project_root).as_posix()] = path
    return [files[key] for key in sorted(files)]


def snapshot_project(project_root: Path) -> Dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    files: Dict[str, Dict[str, Any]] = {}
    for path in _tracked_files(project_root):
        rel = path.relative_to(project_root).as_posix()
        stat = path.stat()
        files[rel] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": _file_digest(path),
        }
    return {
        "project_root": str(project_root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tracked_patterns": list(TRACKED_PATTERNS),
        "files": files,
    }


def changed_since(before: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    after = snapshot_project(project_root)
    before_files = before.get("files") or {}
    after_files = after.get("files") or {}
    changed_files: List[str] = []

    for rel in sorted(set(before_files) | set(after_files)):
        if before_files.get(rel) != after_files.get(rel):
            changed_files.append(rel)

    return {
        "changed": bool(changed_files),
        "changed_files": changed_files,
        "before_count": len(before_files),
        "after_count": len(after_files),
        "checked_at": after["created_at"],
    }


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="续写回写快照审计工具（novelist）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snapshot", help="保存项目关键文件快照")
    snap.add_argument("--project-root", required=True)
    snap.add_argument("--output", required=True)

    changed = sub.add_parser("changed", help="比较快照后项目是否发生回写")
    changed.add_argument("--project-root", required=True)
    changed.add_argument("--before", required=True)

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.cmd == "snapshot":
            payload = snapshot_project(Path(args.project_root))
            _write_json(Path(args.output).expanduser().resolve(), payload)
            print(f"回写快照已写入：{Path(args.output).expanduser().resolve()}")
            return 0

        before = _read_json(Path(args.before).expanduser().resolve())
        result = changed_since(before, Path(args.project_root))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["changed"] else 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
