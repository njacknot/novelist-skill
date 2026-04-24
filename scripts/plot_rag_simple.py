#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_rag_simple.py — 纯 Python BM25 剧情检索引擎（零外部依赖）

实现 references/advanced/million-word-roadmap.md §10「长篇一致性 RAG」：
- build：扫描 03_manuscript/*.md，按段落切片 → 提取元数据 → 写入索引
- query：自然语言查询 → BM25 粗筛 → Top-K 精排 → 输出上下文
- 增量构建：只处理新增/修改的章节

依赖：仅 Python 标准库（zero-dep）。
退出码：0 成功 / 1 无结果 / 2 输入错误
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ───────────────────────────── 常量 ─────────────────────────────

DEFAULT_TOP_K = 4
DEFAULT_CANDIDATE_K = 12
MIN_SEGMENT_CHARS = 80
MAX_SEGMENT_CHARS = 600
BM25_K1 = 1.5
BM25_B = 0.75


# ───────────────────────────── 中文分词（N-gram，无依赖） ─────────────────────────────


def _extract_chinese(text: str) -> str:
    """保留中文字符和基本标点。"""
    return re.sub(r"[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", " ", text)


def tokenize(text: str) -> List[str]:
    """
    中文分词：2-gram + 3-gram + 4-gram + 完整命名实体（2-6 字连续汉字）。
    无 jieba 依赖，纯正则实现。
    """
    chinese = _extract_chinese(text)
    # 提取连续汉字块
    blocks = re.findall(r"[\u4e00-\u9fff]+", chinese)
    tokens: List[str] = []
    for block in blocks:
        # 完整块作为一个 token（适合人名、地名）
        if 2 <= len(block) <= 6:
            tokens.append(block)
        # N-gram 切分
        for n in (2, 3, 4):
            for i in range(len(block) - n + 1):
                tokens.append(block[i : i + n])
    return tokens


def _file_hash(path: Path) -> str:
    """计算文件内容的 MD5 hash。"""
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


# ───────────────────────────── 数据结构 ─────────────────────────────


@dataclass
class Segment:
    """一个检索片段。"""
    segment_id: str
    chapter_number: int
    chapter_title: str
    paragraph_index: int
    text: str
    char_count: int
    characters_mentioned: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class StoryIndex:
    """全书检索索引。"""
    version: str = "1.0"
    last_updated: str = ""
    total_segments: int = 0
    total_chapters: int = 0
    chapter_hashes: Dict[str, str] = field(default_factory=dict)  # filename -> md5
    segments: List[Dict] = field(default_factory=list)

    # BM25 运行时数据（不序列化）
    _df: Dict[str, int] = field(default_factory=dict, repr=False)
    _avgdl: float = field(default=0.0, repr=False)
    _seg_tokens: List[List[str]] = field(default_factory=list, repr=False)


# ───────────────────────────── 章节解析 ─────────────────────────────


def _count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _strip_markdown(text: str) -> str:
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text


def _extract_chapter_number(filename: str) -> int:
    """从文件名提取章节号，如 '第001章_xxx.md' -> 1。"""
    m = re.search(r"第\s*(\d+)\s*章", filename)
    if m:
        return int(m.group(1))
    # 尝试纯数字
    m = re.search(r"(\d+)", filename)
    if m:
        return int(m.group(1))
    return 0


def _extract_chapter_title(content: str, filename: str) -> str:
    """从正文标题行或文件名提取章名。"""
    for line in content.splitlines()[:5]:
        m = re.match(r"#\s*第\s*\d+\s*章[—\-_·\s]*(.*)", line)
        if m:
            return m.group(1).strip()
    return Path(filename).stem


def _extract_characters(text: str, known_chars: Optional[List[str]] = None) -> List[str]:
    """从文本中提取可能的角色名（2-4 字连续汉字 + 已知角色匹配）。"""
    found: List[str] = []
    if known_chars:
        for name in known_chars:
            if name in text:
                found.append(name)
    return list(dict.fromkeys(found))  # 去重保序


def parse_chapter(filepath: Path, known_chars: Optional[List[str]] = None) -> List[Segment]:
    """将一个章节文件切分为检索片段。"""
    raw = filepath.read_text(encoding="utf-8")
    stripped = _strip_markdown(raw)

    # 跳过标题行
    lines = stripped.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"第\s*\d+\s*章", line):
            start = i + 1
            break
    body = "\n".join(lines[start:])

    chapter_number = _extract_chapter_number(filepath.name)
    chapter_title = _extract_chapter_title(raw, filepath.name)

    # 按段落切分
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]

    segments: List[Segment] = []
    buffer = ""
    para_start = 0

    for i, para in enumerate(paragraphs):
        buffer += para + "\n\n"
        char_count = _count_chinese(buffer)

        # 当 buffer 足够大或是最后一段时，生成一个 segment
        if char_count >= MIN_SEGMENT_CHARS or i == len(paragraphs) - 1:
            if char_count < 20:  # 太短的忽略
                buffer = ""
                para_start = i + 1
                continue

            # 如果超长，截断
            text = buffer.strip()
            if _count_chinese(text) > MAX_SEGMENT_CHARS:
                # 按句号截断
                sentences = re.split(r"[。！？]", text)
                truncated = ""
                for s in sentences:
                    if _count_chinese(truncated + s) > MAX_SEGMENT_CHARS:
                        break
                    truncated += s + "。"
                text = truncated.strip() if truncated.strip() else text[:MAX_SEGMENT_CHARS * 2]

            seg_id = f"ch{chapter_number:03d}_p{para_start:03d}"
            chars = _extract_characters(text, known_chars)

            segments.append(Segment(
                segment_id=seg_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                paragraph_index=para_start,
                text=text,
                char_count=_count_chinese(text),
                characters_mentioned=chars,
                keywords=list(dict.fromkeys(tokenize(text)[:20])),
            ))
            buffer = ""
            para_start = i + 1

    return segments


# ───────────────────────────── BM25 引擎 ─────────────────────────────


class BM25:
    """纯 Python BM25 实现。"""

    def __init__(self, corpus: List[List[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / max(1, self.n)

        # 文档频率
        self.df: Dict[str, int] = {}
        for doc in corpus:
            seen = set(doc)
            for term in seen:
                self.df[term] = self.df.get(term, 0) + 1

        # 每个文档的词频
        self.tf: List[Dict[str, int]] = []
        for doc in corpus:
            counter: Dict[str, int] = {}
            for term in doc:
                counter[term] = counter.get(term, 0) + 1
            self.tf.append(counter)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query_tokens: List[str], doc_idx: int) -> float:
        doc_tf = self.tf[doc_idx]
        doc_len = len(self.corpus[doc_idx])
        s = 0.0
        for term in query_tokens:
            tf = doc_tf.get(term, 0)
            idf = self._idf(term)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            s += idf * numerator / denominator
        return s

    def top_k(self, query_tokens: List[str], k: int = DEFAULT_TOP_K, candidate_k: int = DEFAULT_CANDIDATE_K) -> List[Tuple[int, float]]:
        """返回 (doc_idx, score) 的 top-k 列表。"""
        scores = [(i, self.score(query_tokens, i)) for i in range(self.n)]
        scores.sort(key=lambda x: x[1], reverse=True)
        # 粗筛 candidate_k → 返回 top_k
        return scores[:k]


# ───────────────────────────── 索引构建 ─────────────────────────────


def _load_known_characters(project_root: Path) -> List[str]:
    """从人物档案中提取已知角色名。"""
    chars: List[str] = []
    for name in ("00-人物档案.md", "00_memory/character_tracker.md"):
        path = project_root / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            # 匹配 ## 角色名 / ### 角色名 / **角色名**
            for m in re.findall(r"(?:#{2,3}\s+|^\*\*)([\u4e00-\u9fff]{2,6})(?:\*\*)?", text, re.M):
                if m not in chars:
                    chars.append(m)
    return chars


def _find_manuscript_dir(project_root: Path) -> Path:
    """找到稿件目录。"""
    ms = project_root / "03_manuscript"
    if ms.is_dir():
        return ms
    # 兼容平铺模式
    return project_root


def build_index(project_root: Path, full_rebuild: bool = False) -> StoryIndex:
    """构建或增量更新检索索引。"""
    index_path = project_root / "00_memory" / "retrieval" / "story_index.json"
    existing = StoryIndex()

    if not full_rebuild and index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            existing.chapter_hashes = data.get("chapter_hashes", {})
            existing.segments = data.get("segments", [])
        except (json.JSONDecodeError, KeyError):
            pass

    ms_dir = _find_manuscript_dir(project_root)
    known_chars = _load_known_characters(project_root)

    # 收集所有章节文件
    chapter_files = sorted(ms_dir.glob("*.md"))
    chapter_files = [f for f in chapter_files if re.search(r"第\s*\d+\s*章", f.name)]

    new_hashes: Dict[str, str] = {}
    new_segments: List[Dict] = []
    unchanged_segments: List[Dict] = []

    for cf in chapter_files:
        file_hash = _file_hash(cf)
        fname = cf.name
        new_hashes[fname] = file_hash

        if not full_rebuild and existing.chapter_hashes.get(fname) == file_hash:
            # 未修改，保留旧片段
            for seg in existing.segments:
                if seg.get("chapter_number") == _extract_chapter_number(fname):
                    unchanged_segments.append(seg)
            continue

        # 需要重新解析
        segs = parse_chapter(cf, known_chars)
        for seg in segs:
            new_segments.append({
                "segment_id": seg.segment_id,
                "chapter_number": seg.chapter_number,
                "chapter_title": seg.chapter_title,
                "paragraph_index": seg.paragraph_index,
                "text": seg.text,
                "char_count": seg.char_count,
                "characters_mentioned": seg.characters_mentioned,
                "keywords": seg.keywords,
            })

    all_segments = unchanged_segments + new_segments
    # 按章号+段落排序
    all_segments.sort(key=lambda s: (s.get("chapter_number", 0), s.get("paragraph_index", 0)))

    index = StoryIndex(
        version="1.0",
        last_updated=datetime.now().isoformat(timespec="seconds"),
        total_segments=len(all_segments),
        total_chapters=len(chapter_files),
        chapter_hashes=new_hashes,
        segments=all_segments,
    )

    # 写入
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump({
            "version": index.version,
            "last_updated": index.last_updated,
            "total_segments": index.total_segments,
            "total_chapters": index.total_chapters,
            "chapter_hashes": index.chapter_hashes,
            "segments": index.segments,
        }, f, ensure_ascii=False, indent=2)

    return index


# ───────────────────────────── 查询 ─────────────────────────────


def query_index(
    project_root: Path,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    chapter_filter: Optional[int] = None,
    character_filter: Optional[str] = None,
    auto_build: bool = False,
) -> List[Dict]:
    """查询索引，返回 top-k 相关片段。"""
    index_path = project_root / "00_memory" / "retrieval" / "story_index.json"

    if not index_path.exists():
        if auto_build:
            print("索引不存在，自动构建...", file=sys.stderr)
            build_index(project_root)
        else:
            raise FileNotFoundError(f"索引文件不存在：{index_path}\n请先执行 build 命令。")

    with index_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        return []

    # 预过滤
    if chapter_filter is not None:
        segments = [s for s in segments if s.get("chapter_number") != chapter_filter]
    if character_filter:
        segments = [s for s in segments if character_filter in s.get("characters_mentioned", [])]

    if not segments:
        return []

    # 构建 BM25
    corpus = [tokenize(s.get("text", "")) for s in segments]
    bm25 = BM25(corpus)

    query_tokens = tokenize(query)
    results = bm25.top_k(query_tokens, k=top_k, candidate_k=candidate_k)

    hits: List[Dict] = []
    for idx, score in results:
        if score <= 0:
            continue
        seg = segments[idx].copy()
        seg["bm25_score"] = round(score, 4)
        hits.append(seg)

    return hits


def render_context(hits: List[Dict]) -> str:
    """将检索结果渲染为 Markdown 上下文。"""
    if not hits:
        return "# 剧情检索结果\n\n> 未找到相关片段。\n"

    lines: List[str] = []
    lines.append("# 剧情检索结果\n")
    lines.append(f"> 检索时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 命中 {len(hits)} 个相关片段\n")
    lines.append("---\n")

    for i, hit in enumerate(hits, 1):
        ch = hit.get("chapter_number", 0)
        title = hit.get("chapter_title", "")
        score = hit.get("bm25_score", 0)
        chars = ", ".join(hit.get("characters_mentioned", []))
        text = hit.get("text", "")

        lines.append(f"## 片段 {i}（第 {ch} 章 · {title}，相关度 {score:.2f}）\n")
        if chars:
            lines.append(f"**出场角色**：{chars}\n")
        lines.append(f"> {text.strip()}\n")
        lines.append("---\n")

    return "\n".join(lines)


# ───────────────────────────── CLI ─────────────────────────────


def cmd_build(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"错误：项目目录不存在 - {project_root}", file=sys.stderr)
        return 2

    index = build_index(project_root, full_rebuild=args.full_rebuild)
    print(f"✅ 索引构建完成", file=sys.stderr)
    print(f"   章节数：{index.total_chapters}", file=sys.stderr)
    print(f"   片段数：{index.total_segments}", file=sys.stderr)
    print(f"   写入：{project_root / '00_memory' / 'retrieval' / 'story_index.json'}", file=sys.stderr)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"错误：项目目录不存在 - {project_root}", file=sys.stderr)
        return 2

    try:
        hits = query_index(
            project_root,
            query=args.query,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            chapter_filter=args.exclude_chapter,
            character_filter=args.character,
            auto_build=args.auto_build,
        )
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2

    context = render_context(hits)

    if args.output:
        out_path = Path(args.output).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(context, encoding="utf-8")
        print(f"✅ 上下文已写入：{out_path}", file=sys.stderr)
    else:
        # 默认写入标准位置
        default_path = project_root / "00_memory" / "retrieval" / "next_plot_context.md"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        default_path.write_text(context, encoding="utf-8")
        print(f"✅ 上下文已写入：{default_path}", file=sys.stderr)

    print(f"   命中 {len(hits)} 个片段", file=sys.stderr)
    if hits:
        for h in hits:
            print(f"   - 第{h['chapter_number']}章 p{h['paragraph_index']} (score={h['bm25_score']:.2f})", file=sys.stderr)

    return 0 if hits else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="剧情检索引擎（novelist, 纯 Python BM25）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # build
    pb = sub.add_parser("build", help="构建/增量更新检索索引")
    pb.add_argument("--project-root", required=True, help="项目目录")
    pb.add_argument("--full-rebuild", action="store_true", help="全量重建（忽略增量缓存）")
    pb.set_defaults(func=cmd_build)

    # query
    pq = sub.add_parser("query", help="检索相关剧情片段")
    pq.add_argument("--project-root", required=True, help="项目目录")
    pq.add_argument("--query", required=True, help="查询文本")
    pq.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help=f"返回 Top-K 结果（默认 {DEFAULT_TOP_K}）")
    pq.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K, help=f"粗筛候选数（默认 {DEFAULT_CANDIDATE_K}）")
    pq.add_argument("--exclude-chapter", type=int, default=None, help="排除指定章节（通常排除当前章）")
    pq.add_argument("--character", default=None, help="按角色名过滤")
    pq.add_argument("--auto-build", action="store_true", help="索引不存在时自动构建")
    pq.add_argument("--output", default=None, help="输出路径（默认 00_memory/retrieval/next_plot_context.md）")
    pq.set_defaults(func=cmd_query)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
