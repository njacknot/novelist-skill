#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
story_graph_query.py — 知识图谱读写工具（零外部依赖）

实现 references/advanced/million-word-roadmap.md §9「知识图谱 Schema 与回写」：
- init：创建空白图谱
- update：读取章节 → 输出增量提取 Prompt 或直接合并
- query：按角色/地点查询关联子图
- validate：校验状态冲突
- export：导出为 Mermaid 可视化

依赖：仅 Python 标准库（zero-dep）。
退出码：0 成功 / 1 校验失败 / 2 输入错误
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── Schema 常量 ─────────────────────────────

NODE_TYPES = {
    "character", "location", "faction", "item",
    "event", "foreshadow", "worldrule", "power_system",
}

EDGE_TYPES = {
    "ally", "enemy", "mentor", "subordinate", "romantic",
    "belongs_to", "located_at", "triggers", "foreshadows", "owns",
    "parent", "child", "sibling", "rival",
}

GRAPH_VERSION = "1.0"


# ───────────────────────────── 图谱数据结构 ─────────────────────────────


def _empty_graph() -> Dict[str, Any]:
    """创建空白图谱骨架。"""
    return {
        "version": GRAPH_VERSION,
        "last_updated_chapter": 0,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "nodes": [],
        "edges": [],
        "timeline": [],
    }


def _graph_path(project_root: Path) -> Path:
    """图谱文件的标准路径。"""
    # 优先 00_memory/story_graph.json
    p1 = project_root / "00_memory" / "story_graph.json"
    if p1.exists():
        return p1
    # 兼容平铺
    p2 = project_root / "story_graph.json"
    if p2.exists():
        return p2
    # 默认创建到 00_memory
    return p1


def load_graph(project_root: Path) -> Dict[str, Any]:
    """加载图谱，不存在则返回空白。"""
    path = _graph_path(project_root)
    if not path.exists():
        return _empty_graph()
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return _empty_graph()


def save_graph(project_root: Path, graph: Dict[str, Any]) -> Path:
    """保存图谱。"""
    path = _graph_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    return path


# ───────────────────────────── 节点/边操作 ─────────────────────────────


def find_node(graph: Dict, node_id: str) -> Optional[Dict]:
    """按 ID 查找节点。"""
    for n in graph.get("nodes", []):
        if n.get("id") == node_id:
            return n
    return None


def find_nodes_by_type(graph: Dict, node_type: str) -> List[Dict]:
    """按类型查找所有节点。"""
    return [n for n in graph.get("nodes", []) if n.get("type") == node_type]


def find_edges_for_node(graph: Dict, node_id: str) -> List[Dict]:
    """查找与指定节点相关的所有边。"""
    edges = []
    for e in graph.get("edges", []):
        if e.get("source") == node_id or e.get("target") == node_id:
            edges.append(e)
    return edges


def add_node(graph: Dict, node_id: str, node_type: str, properties: Optional[Dict] = None) -> bool:
    """添加节点，返回是否新增。"""
    if node_type not in NODE_TYPES:
        raise ValueError(f"无效节点类型: {node_type}，允许: {NODE_TYPES}")
    existing = find_node(graph, node_id)
    if existing:
        # 更新属性
        if properties:
            existing.setdefault("properties", {}).update(properties)
        return False
    node = {
        "id": node_id,
        "type": node_type,
        "properties": properties or {},
        "first_appearance": 0,
        "last_updated": 0,
    }
    graph.setdefault("nodes", []).append(node)
    return True


def add_edge(graph: Dict, source: str, target: str, edge_type: str,
             chapter: int = 0, properties: Optional[Dict] = None) -> bool:
    """添加边，返回是否新增。"""
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"无效边类型: {edge_type}，允许: {EDGE_TYPES}")
    # 检查重复
    for e in graph.get("edges", []):
        if (e.get("source") == source and e.get("target") == target
                and e.get("type") == edge_type):
            if properties:
                e.setdefault("properties", {}).update(properties)
            e["last_updated"] = chapter
            return False
    edge = {
        "source": source,
        "target": target,
        "type": edge_type,
        "since_chapter": chapter,
        "last_updated": chapter,
        "properties": properties or {},
    }
    graph.setdefault("edges", []).append(edge)
    return True


def add_timeline_event(graph: Dict, chapter: int, event_id: str, description: str) -> None:
    """添加时间线事件。"""
    graph.setdefault("timeline", []).append({
        "chapter": chapter,
        "event_id": event_id,
        "description": description,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })


# ───────────────────────────── 查询与渲染 ─────────────────────────────


def query_character_subgraph(graph: Dict, character_name: str) -> str:
    """查询角色的关联子图，输出 Markdown。"""
    node = find_node(graph, character_name)
    if not node:
        # 尝试模糊匹配
        candidates = [n for n in graph.get("nodes", [])
                      if character_name in n.get("id", "")]
        if not candidates:
            return f"未找到角色: {character_name}\n"
        node = candidates[0]

    node_id = node["id"]
    edges = find_edges_for_node(graph, node_id)
    props = node.get("properties", {})

    lines: List[str] = []
    lines.append(f"# 角色子图: {node_id}\n")
    lines.append(f"**类型**: {node.get('type', 'character')}")
    lines.append(f"**首次出场**: 第 {node.get('first_appearance', '?')} 章")
    lines.append(f"**最后更新**: 第 {node.get('last_updated', '?')} 章\n")

    if props:
        lines.append("## 属性\n")
        for k, v in props.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if edges:
        lines.append("## 关系\n")
        lines.append("| 关系类型 | 对象 | 起始章 | 备注 |")
        lines.append("|---------|------|:------:|------|")
        for e in edges:
            other = e["target"] if e["source"] == node_id else e["source"]
            etype = e.get("type", "?")
            since = e.get("since_chapter", "?")
            note = e.get("properties", {}).get("note", "")
            lines.append(f"| {etype} | {other} | {since} | {note} |")
        lines.append("")

    # 相关时间线事件
    timeline = graph.get("timeline", [])
    related_events = [t for t in timeline if node_id in t.get("description", "")]
    if related_events:
        lines.append("## 相关事件\n")
        for evt in related_events[-10:]:  # 最近 10 条
            lines.append(f"- 第 {evt.get('chapter', '?')} 章: {evt.get('description', '')}")
        lines.append("")

    return "\n".join(lines)


def query_subgraph_for_chapter(graph: Dict, character_names: List[str]) -> str:
    """为写前准备：提取多个角色的关联子图。"""
    lines: List[str] = []
    lines.append("# 本章出场角色关系上下文\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for name in character_names:
        lines.append(query_character_subgraph(graph, name))
        lines.append("---\n")

    return "\n".join(lines)


def export_mermaid(graph: Dict) -> str:
    """导出为 Mermaid 图表。"""
    lines: List[str] = ["graph LR"]
    node_ids: Set[str] = set()

    for n in graph.get("nodes", []):
        nid = n["id"]
        ntype = n.get("type", "unknown")
        # Mermaid 节点
        safe_id = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", nid)
        shape = {"character": f'{safe_id}["{nid}"]',
                 "location": f'{safe_id}("{nid}")',
                 "faction": f'{safe_id}{{"{nid}"}}',
                 "event": f'{safe_id}(["{nid}"])',
                 }.get(ntype, f'{safe_id}["{nid}"]')
        lines.append(f"    {shape}")
        node_ids.add(nid)

    for e in graph.get("edges", []):
        src = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", e.get("source", ""))
        tgt = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", e.get("target", ""))
        etype = e.get("type", "")
        lines.append(f"    {src} -->|{etype}| {tgt}")

    return "\n".join(lines)


# ───────────────────────────── 校验 ─────────────────────────────


def validate_graph(graph: Dict) -> List[Dict]:
    """校验图谱一致性，返回问题列表。"""
    issues: List[Dict] = []
    node_ids = {n["id"] for n in graph.get("nodes", [])}

    # 检查悬空边
    for e in graph.get("edges", []):
        if e.get("source") not in node_ids:
            issues.append({
                "type": "dangling_edge",
                "severity": "P1",
                "detail": f"边的源节点不存在: {e.get('source')} -> {e.get('target')}",
            })
        if e.get("target") not in node_ids:
            issues.append({
                "type": "dangling_edge",
                "severity": "P1",
                "detail": f"边的目标节点不存在: {e.get('source')} -> {e.get('target')}",
            })

    # 检查角色位置冲突（同一章出现在多个位置）
    characters = find_nodes_by_type(graph, "character")
    for char in characters:
        char_id = char["id"]
        location_edges = [e for e in graph.get("edges", [])
                          if e.get("source") == char_id and e.get("type") == "located_at"]
        if len(location_edges) > 1:
            chapters = [e.get("last_updated", 0) for e in location_edges]
            if len(set(chapters)) < len(chapters):
                locs = [e.get("target") for e in location_edges]
                issues.append({
                    "type": "location_conflict",
                    "severity": "P0",
                    "detail": f"角色 {char_id} 同时位于多个位置: {locs}",
                })

    # 检查互斥关系（同时是 ally 和 enemy）
    for char in characters:
        char_id = char["id"]
        edges = find_edges_for_node(graph, char_id)
        relations: Dict[str, Set[str]] = {}
        for e in edges:
            other = e["target"] if e["source"] == char_id else e["source"]
            relations.setdefault(other, set()).add(e.get("type", ""))
        for other, types in relations.items():
            if "ally" in types and "enemy" in types:
                issues.append({
                    "type": "relation_conflict",
                    "severity": "P0",
                    "detail": f"角色 {char_id} 与 {other} 同时标记为 ally 和 enemy",
                })

    # 检查伏笔超期（>50 章未回收）
    foreshadows = find_nodes_by_type(graph, "foreshadow")
    last_chapter = graph.get("last_updated_chapter", 0)
    for fs in foreshadows:
        planted = fs.get("first_appearance", 0)
        status = fs.get("properties", {}).get("status", "planted")
        if status == "planted" and last_chapter - planted > 50:
            issues.append({
                "type": "overdue_foreshadow",
                "severity": "P1",
                "detail": f"伏笔 {fs['id']} 已 {last_chapter - planted} 章未回收（第 {planted} 章埋设）",
            })

    return issues


# ───────────────────────────── 更新 Prompt 生成 ─────────────────────────────


def generate_update_prompt(project_root: Path, chapter_file: Path, graph: Dict) -> str:
    """生成让 Agent 填写的增量更新 Prompt。"""
    content = chapter_file.read_text(encoding="utf-8")
    ch_num = int(re.search(r"第\s*(\d+)\s*章", chapter_file.name).group(1)) if re.search(r"第\s*(\d+)\s*章", chapter_file.name) else 0

    existing_chars = [n["id"] for n in find_nodes_by_type(graph, "character")]
    existing_locs = [n["id"] for n in find_nodes_by_type(graph, "location")]

    prompt = f"""请根据以下章节正文，提取知识图谱的增量更新。

## 当前章节
- 章号: {ch_num}
- 文件: {chapter_file.name}

## 已有角色节点
{', '.join(existing_chars) if existing_chars else '（空）'}

## 已有地点节点
{', '.join(existing_locs) if existing_locs else '（空）'}

## 请输出以下 JSON 格式的增量更新

```json
{{
  "new_nodes": [
    {{"id": "角色名", "type": "character", "properties": {{"性格": "...", "身份": "...", "当前状态": "..."}}}}
  ],
  "new_edges": [
    {{"source": "角色A", "target": "角色B", "type": "ally", "properties": {{"note": "结盟原因"}}}}
  ],
  "updated_nodes": [
    {{"id": "已有角色名", "properties": {{"当前状态": "新状态", "位置": "新位置"}}}}
  ],
  "timeline_events": [
    {{"event_id": "evt_{ch_num:03d}_001", "description": "简短描述本章发生的关键事件"}}
  ]
}}
```

## 规则
1. 只提取本章新增或变更的信息
2. 节点 type 只允许: {', '.join(sorted(NODE_TYPES))}
3. 边 type 只允许: {', '.join(sorted(EDGE_TYPES))}
4. 不要重复已有节点（已有角色请放在 updated_nodes）
5. 时间线事件只记录关键剧情转折，不要记录日常
"""
    return prompt


def apply_incremental_update(graph: Dict, update: Dict, chapter: int) -> Tuple[int, int, int]:
    """应用增量更新，返回 (新增节点数, 新增边数, 更新节点数)。"""
    added_nodes = 0
    added_edges = 0
    updated_nodes = 0

    for n in update.get("new_nodes", []):
        if add_node(graph, n["id"], n.get("type", "character"), n.get("properties")):
            node = find_node(graph, n["id"])
            if node:
                node["first_appearance"] = chapter
                node["last_updated"] = chapter
            added_nodes += 1

    for n in update.get("updated_nodes", []):
        existing = find_node(graph, n.get("id", ""))
        if existing:
            existing.setdefault("properties", {}).update(n.get("properties", {}))
            existing["last_updated"] = chapter
            updated_nodes += 1

    for e in update.get("new_edges", []):
        if add_edge(graph, e["source"], e["target"], e.get("type", "ally"),
                     chapter=chapter, properties=e.get("properties")):
            added_edges += 1

    for evt in update.get("timeline_events", []):
        add_timeline_event(graph, chapter, evt.get("event_id", ""), evt.get("description", ""))

    graph["last_updated_chapter"] = chapter
    return added_nodes, added_edges, updated_nodes


# ───────────────────────────── CLI ─────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    graph = _empty_graph()
    path = save_graph(project_root, graph)
    print(f"✅ 空白图谱已创建: {path}", file=sys.stderr)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    graph = load_graph(project_root)

    if args.characters:
        names = [n.strip() for n in args.characters.split(",")]
        result = query_subgraph_for_chapter(graph, names)
    elif args.node_id:
        result = query_character_subgraph(graph, args.node_id)
    else:
        # 输出全图概览
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        result = f"# 图谱概览\n\n- 节点: {len(nodes)}\n- 边: {len(edges)}\n- 最后更新章: {graph.get('last_updated_chapter', 0)}\n"
        for ntype in sorted(NODE_TYPES):
            typed = find_nodes_by_type(graph, ntype)
            if typed:
                ids = ", ".join(n["id"] for n in typed)
                result += f"\n## {ntype} ({len(typed)})\n{ids}\n"

    if args.output:
        Path(args.output).expanduser().write_text(result, encoding="utf-8")
        print(f"✅ 已写入: {args.output}", file=sys.stderr)
    else:
        print(result)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    graph = load_graph(project_root)
    issues = validate_graph(graph)

    if not issues:
        print("✅ 图谱校验通过，无冲突", file=sys.stderr)
        return 0

    print(f"⚠ 发现 {len(issues)} 个问题：\n", file=sys.stderr)
    for iss in issues:
        sev = iss.get("severity", "P2")
        prefix = "🔴" if sev == "P0" else "🟡" if sev == "P1" else "🟢"
        print(f"  {prefix} [{sev}] {iss['type']}: {iss['detail']}", file=sys.stderr)
    return 1


def cmd_update(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    graph = load_graph(project_root)

    chapter_file = Path(args.chapter_file).expanduser().resolve()
    if not chapter_file.exists():
        print(f"错误: 章节文件不存在 - {chapter_file}", file=sys.stderr)
        return 2

    if args.prompt_only:
        prompt = generate_update_prompt(project_root, chapter_file, graph)
        print(prompt)
        return 0

    # 从 JSON 文件读取增量更新
    if args.incremental_json:
        inc_path = Path(args.incremental_json).expanduser()
        if not inc_path.exists():
            print(f"错误: 增量更新文件不存在 - {inc_path}", file=sys.stderr)
            return 2
        with inc_path.open("r", encoding="utf-8") as f:
            update = json.load(f)
        ch_num = int(re.search(r"\d+", chapter_file.stem).group()) if re.search(r"\d+", chapter_file.stem) else 0
        an, ae, un = apply_incremental_update(graph, update, ch_num)
        save_graph(project_root, graph)
        print(f"✅ 图谱已更新: +{an} 节点, +{ae} 边, ~{un} 更新", file=sys.stderr)
        return 0

    # 默认：输出 Prompt
    prompt = generate_update_prompt(project_root, chapter_file, graph)
    print(prompt)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    graph = load_graph(project_root)

    if args.format == "mermaid":
        result = export_mermaid(graph)
    else:
        result = json.dumps(graph, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).expanduser().write_text(result, encoding="utf-8")
        print(f"✅ 已导出: {args.output}", file=sys.stderr)
    else:
        print(result)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="知识图谱读写工具（novelist）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    pi = sub.add_parser("init", help="创建空白图谱")
    pi.add_argument("--project-root", required=True)
    pi.set_defaults(func=cmd_init)

    # query
    pq = sub.add_parser("query", help="查询图谱")
    pq.add_argument("--project-root", required=True)
    pq.add_argument("--node-id", default=None, help="查询指定节点 ID")
    pq.add_argument("--characters", default=None, help="查询多个角色（逗号分隔）")
    pq.add_argument("--output", default=None)
    pq.set_defaults(func=cmd_query)

    # validate
    pv = sub.add_parser("validate", help="校验图谱一致性")
    pv.add_argument("--project-root", required=True)
    pv.set_defaults(func=cmd_validate)

    # update
    pu = sub.add_parser("update", help="更新图谱（增量）")
    pu.add_argument("--project-root", required=True)
    pu.add_argument("--chapter-file", required=True, help="章节文件路径")
    pu.add_argument("--prompt-only", action="store_true", help="仅输出提取 Prompt")
    pu.add_argument("--incremental-json", default=None, help="增量更新 JSON 文件路径")
    pu.set_defaults(func=cmd_update)

    # export
    pe = sub.add_parser("export", help="导出图谱")
    pe.add_argument("--project-root", required=True)
    pe.add_argument("--format", choices=["mermaid", "json"], default="mermaid")
    pe.add_argument("--output", default=None)
    pe.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
