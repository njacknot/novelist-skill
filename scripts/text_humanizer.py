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
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class RiskRule:
    """朱雀/项目专项风险规则。"""

    rule_id: str
    category: str
    severity: str
    pattern: str
    suggestion: str
    weight: float


@dataclass
class RiskIssue:
    file: str
    line: int
    text: str
    category: str
    severity: str
    suggestion: str
    rule_id: str
    weight: float = 0.0


@dataclass
class RiskReport:
    file: str
    title: str
    hanzi_count: int
    char_count: int
    ai_risk_score: float = 0.0
    gate_status: str = "pass"
    issues: List[RiskIssue] = field(default_factory=list)
    rule_hits: Dict[str, int] = field(default_factory=dict)
    category_hits: Dict[str, int] = field(default_factory=dict)
    tag_distribution: Dict[str, int] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)


FATAL_RISK_RULES: Sequence[RiskRule] = (
    RiskRule("fatal.voice.light", "致命模板", "high", r"声音很轻", "改成可见动作或语境反应，不直接写声音轻。", 18),
    RiskRule("fatal.voice.calm", "致命模板", "high", r"声音很平静", "用动作、停顿、表情压力替代抽象平静。", 18),
    RiskRule("fatal.eye.kind", "致命模板", "high", r"眼神里有一种", "删除抽象眼神，改成具体动作或物件反应。", 20),
    RiskRule("fatal.eye.flash", "致命模板", "high", r"眼神里闪过一丝", "避免模板化眼神描写，改成可观察反应。", 16),
    RiskRule("fatal.pause.dun", "致命模板", "high", r"顿了顿", "改成具体动作承接，例如放下杯子、扣住手机。", 12),
    RiskRule("fatal.silence.long", "致命模板", "high", r"沉默了很久|沉默了一会儿", "用现场声音、人物动作承载沉默。", 14),
    RiskRule("fatal.no_answer", "致命模板", "high", r"(?:宁远|他|她)?没有立刻回答|(?:宁远|他|她)?没有回答", "不要直接说明未回答，写他/她做了什么。", 14),
    RiskRule("fatal.no_speak", "致命模板", "high", r"(?:宁远|他|她)?没有说话", "不要直接说明沉默，改成动作或现场反应。", 14),
    RiskRule("fatal.deep_thing", "致命模板", "high", r"很深的东西|复杂的情绪|复杂的东西", "把抽象情绪拆成具体动作或选择。", 14),
    RiskRule("fatal.know", "致命模板", "high", r"他知道|她知道|他明白|她明白|终于明白", "减少解释性判断，改成证据、反应或动作。", 10),
    RiskRule("fatal.deep_eye", "致命模板", "high", r"眼神深邃", "删除空泛形容，改成具体注视对象和行为。", 12),
)


COMMON_CHINESE_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏窦章云苏潘葛范彭"
    "鲁韦昌马苗方俞任袁柳鲍史唐薛雷贺倪汤罗毕郝邬安常乐于傅齐康伍余顾孟黄穆萧尹姚邵汪祁"
    "毛米贝明成戴宋庞熊纪舒屈项祝董梁杜阮蓝闵季贾路江童颜郭梅盛林钟徐邱骆高夏蔡田胡凌霍"
    "虞万管卢莫房解应宗丁宣邓杭洪包左石崔吉龚程邢裴陆荣翁家靳段焦侯全班秋仲宫宁栾祖武刘"
    "景龙叶黎蒲索赖卓蔺蒙池乔闻党翟谭申冉桑桂牛边燕温庄晏柴阎连习艾容向古易慎戈廖居衡步"
    "耿满弘匡国文寇广东欧利蔚师巩聂辛阚简饶曾沙丰关查游竺权益桓"
)
BROKEN_QUOTE_NAME_PATTERN = (
    rf'(?:(?<=[\"”])[{COMMON_CHINESE_SURNAMES}][\u4e00-\u9fff]{{1,3}}\"'
    rf'(?=不是|是|的|说|道|开口|我们|我|你|他|她|马上|现在)|'
    rf'[，。！？；：\s][{COMMON_CHINESE_SURNAMES}][\u4e00-\u9fff]{{1,3}}\"'
    rf'(?=不是|是|的|说|道|开口|我们|我|你|他|她|马上|现在))'
)


ARTIFACT_RISK_RULES: Sequence[RiskRule] = (
    RiskRule("artifact.broken_quote.pronoun", "替换事故", "critical", r"(?:(?<=[\"”])(?:他|她)\"|[，。！？；：\s](?:他|她)\")", "批量替换打断对白，改成“他说/她说”或删掉断裂标签。", 35),
    RiskRule("artifact.broken_quote.name", "替换事故", "critical", BROKEN_QUOTE_NAME_PATTERN, "中文姓名/称谓后直接接引号是断句事故，需要补动词。", 35),
    RiskRule("artifact.emotion_replace", "替换事故", "critical", r"的把情绪|开口时压着气|的开口时", "替换痕迹明显，需按上下文重写。", 35),
    RiskRule("artifact.double_pressure", "替换事故", "critical", r"目光里压着压住|视线里藏着压住|眼底掠过复杂", "替代表达叠加，需重写为自然动作。", 30),
    RiskRule("artifact.bad_merge", "替换事故", "critical", r"眼神脸上|轮子碾过地面的开口", "合并错误，需人工修复。", 30),
    RiskRule("artifact.english_leak", "替换事故", "critical", r"anyone can access", "中文正文中混入英文技术句，需按语境改写。", 25),
)


REPLACEMENT_RISK_TAGS: Sequence[str] = (
    "嗓音发沉", "语气压得很低", "语气稳住", "语速放慢", "声音不高", "声音发紧",
    "压低声音", "目光沉了下去", "目光里压着", "视线里藏着", "眼底掠过",
    "神色没变", "脸上看不出波澜", "嘴角微微上扬", "没接话",
)


EXPOSITION_RISK_PATTERNS: Sequence[str] = (
    "他很清楚", "她很清楚", "宁远很清楚", "这意味着", "这说明",
    "终于意识到", "已经意识到", "这才看清", "看得出来",
)


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


# ───────────────────────────── 朱雀/项目专项风险门禁 ─────────────────────────────


def _split_sentences(text: str) -> List[str]:
    return [m.group(0).strip() for m in re.finditer(r"[^。！？!?；;]+[。！？!?；;]?", text) if m.group(0).strip()]


def _normalize_title(content: str, filepath: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return re.sub(r"^第\d+章[-_]", "", filepath.stem)


def _collect_markdown_files(target: Path) -> List[Path]:
    if target.is_file():
        return [target]
    return sorted(path for path in target.glob("*.md") if path.is_file())


def _load_risk_rules(path: Optional[str]) -> Tuple[Sequence[RiskRule], Sequence[RiskRule]]:
    if not path:
        return FATAL_RISK_RULES, ARTIFACT_RISK_RULES
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))

    def parse(items: Iterable[Dict]) -> List[RiskRule]:
        return [
            RiskRule(
                rule_id=item["rule_id"],
                category=item["category"],
                severity=item["severity"],
                pattern=item["pattern"],
                suggestion=item.get("suggestion", "按上下文重写。"),
                weight=float(item.get("weight", 10)),
            )
            for item in items
        ]

    return parse(payload.get("fatal_rules", [])), parse(payload.get("artifact_rules", []))


class RiskDetector:
    """批量章节 AI 风险门禁；补充 7 大模式检测之外的项目专项规则。"""

    def __init__(
        self,
        min_hanzi: int = 0,
        fatal_rules: Sequence[RiskRule] = FATAL_RISK_RULES,
        artifact_rules: Sequence[RiskRule] = ARTIFACT_RISK_RULES,
        replacement_tags: Sequence[str] = REPLACEMENT_RISK_TAGS,
    ):
        self.min_hanzi = min_hanzi
        self.rules = list(fatal_rules) + list(artifact_rules)
        self.replacement_tags = list(replacement_tags)
        self._compiled_rules = [(rule, re.compile(rule.pattern)) for rule in self.rules]
        self._compiled_tags = [(tag, re.compile(re.escape(tag))) for tag in self.replacement_tags]

    def detect_file(self, filepath: str | Path) -> RiskReport:
        path = Path(filepath)
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        report = RiskReport(
            file=str(path),
            title=_normalize_title(content, path),
            hanzi_count=_count_chinese(content),
            char_count=len(content),
        )
        self._detect_rules(report, lines)
        self._detect_replacement_repetition(report, lines)
        self._detect_exposition(report, lines)
        self._calculate_metrics(report, content, lines)
        self._detect_word_count(report)
        self._score(report)
        self._decide_gate_status(report)
        return report

    def _detect_rules(self, report: RiskReport, lines: Sequence[str]) -> None:
        for line_no, line in enumerate(lines, 1):
            for rule, pattern in self._compiled_rules:
                for match in pattern.finditer(line):
                    text = match.group(0).strip()
                    report.issues.append(RiskIssue(
                        file=report.file,
                        line=line_no,
                        text=text,
                        category=rule.category,
                        severity=rule.severity,
                        suggestion=rule.suggestion,
                        rule_id=rule.rule_id,
                        weight=rule.weight,
                    ))
                    report.rule_hits[rule.rule_id] = report.rule_hits.get(rule.rule_id, 0) + 1
                    report.category_hits[rule.category] = report.category_hits.get(rule.category, 0) + 1

    def _detect_replacement_repetition(self, report: RiskReport, lines: Sequence[str]) -> None:
        joined = "\n".join(lines)
        for tag, pattern in self._compiled_tags:
            count = len(pattern.findall(joined))
            if count:
                report.tag_distribution[tag] = count
            if count >= 4:
                severity = "warning" if count >= 6 else "info"
                report.issues.append(RiskIssue(
                    file=report.file,
                    line=0,
                    text=f"{tag} x{count}",
                    category="替代表达重复",
                    severity=severity,
                    suggestion="同一替代表达重复过多，建议换成动作、物件或场景反应。",
                    rule_id=f"repeat.replacement.{tag}",
                    weight=8 if severity == "warning" else 4,
                ))
                report.category_hits["替代表达重复"] = report.category_hits.get("替代表达重复", 0) + 1

    def _detect_exposition(self, report: RiskReport, lines: Sequence[str]) -> None:
        consecutive = 0
        max_consecutive = 0
        total_hits = 0
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                consecutive = 0
                continue
            hit = next((pattern for pattern in EXPOSITION_RISK_PATTERNS if pattern in stripped), "")
            if hit:
                total_hits += 1
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
                report.issues.append(RiskIssue(
                    file=report.file,
                    line=line_no,
                    text=hit,
                    category="解释性句子",
                    severity="info",
                    suggestion="减少直接解释，用证据、动作或对话反应承载判断。",
                    rule_id="style.exposition",
                    weight=3,
                ))
            else:
                consecutive = 0

        report.metrics["exposition_hits"] = float(total_hits)
        report.metrics["max_consecutive_exposition"] = float(max_consecutive)
        if max_consecutive >= 3:
            report.issues.append(RiskIssue(
                file=report.file,
                line=0,
                text=f"连续解释性句子 {max_consecutive} 句",
                category="解释性句子",
                severity="warning",
                suggestion="连续解释超过3句，建议插入动作、冲突或现场噪音。",
                rule_id="style.exposition.chain",
                weight=10,
            ))
            report.category_hits["解释性句子"] = report.category_hits.get("解释性句子", 0) + 1

    def _calculate_metrics(self, report: RiskReport, content: str, lines: Sequence[str]) -> None:
        nonempty_lines = [line.strip() for line in lines if line.strip()]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        short_paragraphs = [p for p in paragraphs if 0 < _count_chinese(p) <= 18 and not p.startswith("#")]
        sentences = _split_sentences(content)
        sentence_lengths = [_count_chinese(sentence) for sentence in sentences if _count_chinese(sentence) > 0]
        dialogue_lines = [line for line in nonempty_lines if line.startswith('"') or line.startswith("“")]

        report.metrics["nonempty_lines"] = float(len(nonempty_lines))
        report.metrics["paragraph_count"] = float(len(paragraphs))
        report.metrics["short_paragraph_ratio"] = len(short_paragraphs) / max(len(paragraphs), 1)
        report.metrics["dialogue_line_ratio"] = len(dialogue_lines) / max(len(nonempty_lines), 1)
        report.metrics["avg_sentence_hanzi"] = statistics.mean(sentence_lengths) if sentence_lengths else 0.0
        report.metrics["sentence_length_stdev"] = statistics.pstdev(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
        report.metrics["avg_paragraph_hanzi"] = statistics.mean([_count_chinese(p) for p in paragraphs]) if paragraphs else 0.0

        if (
            report.hanzi_count >= 1000
            and report.metrics["paragraph_count"] >= 20
            and report.metrics["short_paragraph_ratio"] > 0.58
        ):
            report.issues.append(RiskIssue(
                file=report.file,
                line=0,
                text=f"短段占比 {report.metrics['short_paragraph_ratio']:.1%}",
                category="节奏风险",
                severity="warning",
                suggestion="短段过密会显得机械，但网文强节奏章节只作为提示，不作为硬失败。",
                rule_id="rhythm.short_paragraphs",
                weight=8,
            ))
            report.category_hits["节奏风险"] = report.category_hits.get("节奏风险", 0) + 1

        if 0 < report.metrics["sentence_length_stdev"] < 4.0 and len(sentence_lengths) >= 20:
            report.issues.append(RiskIssue(
                file=report.file,
                line=0,
                text=f"句长标准差 {report.metrics['sentence_length_stdev']:.1f}",
                category="节奏风险",
                severity="info",
                suggestion="句长变化偏小，容易显得平滑，可增加长短句错落。",
                rule_id="rhythm.low_burstiness",
                weight=4,
            ))

    def _detect_word_count(self, report: RiskReport) -> None:
        if self.min_hanzi and report.hanzi_count < self.min_hanzi:
            report.issues.append(RiskIssue(
                file=report.file,
                line=0,
                text=f"汉字数 {report.hanzi_count} < {self.min_hanzi}",
                category="字数门禁",
                severity="warning",
                suggestion="章节汉字数低于门槛；字数建议交给独立字数门禁最终判定。",
                rule_id="gate.min_hanzi",
                weight=10,
            ))
            report.category_hits["字数门禁"] = report.category_hits.get("字数门禁", 0) + 1

    def _score(self, report: RiskReport) -> None:
        weights = {
            "template": sum(issue.weight for issue in report.issues if issue.category == "致命模板"),
            "artifact": sum(issue.weight for issue in report.issues if issue.category == "替换事故"),
            "repetition": sum(issue.weight for issue in report.issues if issue.category == "替代表达重复"),
            "exposition": sum(issue.weight for issue in report.issues if issue.category == "解释性句子"),
            "rhythm": sum(issue.weight for issue in report.issues if issue.category in {"节奏风险", "字数门禁"}),
        }
        report.scores = {
            "template": round(min(weights["template"], 55), 1),
            "artifact": round(min(weights["artifact"], 70), 1),
            "repetition": round(min(weights["repetition"], 20), 1),
            "exposition": round(min(weights["exposition"], 20), 1),
            "rhythm": round(min(weights["rhythm"], 20), 1),
        }
        report.scores["hard_fail"] = round(min(report.scores["template"] + report.scores["artifact"], 100), 1)
        report.scores["advisory"] = round(
            min(report.scores["repetition"] + report.scores["exposition"] + report.scores["rhythm"], 100), 1
        )
        report.scores["total"] = round(min(report.scores["hard_fail"] + report.scores["advisory"], 100), 1)
        report.ai_risk_score = report.scores["total"]

    def _decide_gate_status(self, report: RiskReport) -> None:
        fatal_hits = report.category_hits.get("致命模板", 0)
        if any(issue.severity == "critical" for issue in report.issues):
            report.gate_status = "fail"
        elif fatal_hits >= 2 or report.scores.get("template", 0) >= 25:
            report.gate_status = "fail"
        elif fatal_hits > 0 or report.ai_risk_score >= 25:
            report.gate_status = "warn"
        elif any(issue.severity == "warning" for issue in report.issues):
            report.gate_status = "warn"
        else:
            report.gate_status = "pass"


def _risk_summary(reports: Sequence[RiskReport]) -> Dict[str, object]:
    statuses = Counter(report.gate_status for report in reports)
    categories = Counter()
    severities = Counter()
    for report in reports:
        categories.update(issue.category for issue in report.issues)
        severities.update(issue.severity for issue in report.issues)
    return {
        "chapter_count": len(reports),
        "total_hanzi": sum(report.hanzi_count for report in reports),
        "average_risk_score": round(sum(report.ai_risk_score for report in reports) / max(len(reports), 1), 1),
        "pass_count": statuses["pass"],
        "warn_count": statuses["warn"],
        "fail_count": statuses["fail"],
        "category_counts": dict(categories),
        "severity_counts": dict(severities),
    }


def _risk_report_to_dict(report: RiskReport) -> Dict[str, object]:
    return {
        "file": report.file,
        "title": report.title,
        "hanzi_count": report.hanzi_count,
        "word_count": report.hanzi_count,
        "char_count": report.char_count,
        "ai_risk_score": report.ai_risk_score,
        "gate_status": report.gate_status,
        "scores": report.scores,
        "metrics": report.metrics,
        "rule_hits": report.rule_hits,
        "category_hits": report.category_hits,
        "tag_distribution": report.tag_distribution,
        "issues": [issue.__dict__ for issue in report.issues],
    }


def _risk_issue_sort_key(issue: RiskIssue) -> Tuple[int, int, str]:
    order = {"critical": 0, "high": 1, "warning": 2, "info": 3}
    return (order.get(issue.severity, 9), issue.line, issue.rule_id)


def _risk_status_label(status: str) -> str:
    return {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(status, status.upper())


def render_risk_console_report(reports: Sequence[RiskReport]) -> str:
    summary = _risk_summary(reports)
    lines = ["=" * 76, "中文网文 AI 风险门禁报告", "=" * 76]
    lines.append(f"检测章节数: {summary['chapter_count']}")
    lines.append(f"总汉字数: {summary['total_hanzi']:,}")
    lines.append(f"平均风险分: {summary['average_risk_score']:.1f}/100")
    lines.append(f"通过/警告/失败: {summary['pass_count']}/{summary['warn_count']}/{summary['fail_count']}")
    lines.append("")
    for report in reports:
        lines.append("-" * 76)
        lines.append(f"{_risk_status_label(report.gate_status)} {report.title}")
        lines.append(f"文件: {Path(report.file).name}")
        lines.append(f"汉字数: {report.hanzi_count:,} | 风险分: {report.ai_risk_score:.1f}")
        lines.append("分项: " + ", ".join(f"{key}={value:.1f}" for key, value in report.scores.items() if key != "total"))
        if report.issues:
            for issue in sorted(report.issues, key=_risk_issue_sort_key):
                line_info = f"第{issue.line}行" if issue.line else "全文"
                lines.append(f"  - [{issue.severity}] {issue.category}/{issue.rule_id} ({line_info})")
                lines.append(f"    内容: {issue.text}")
                lines.append(f"    建议: {issue.suggestion}")
        else:
            lines.append("  无明显风险。")
        lines.append("")
    return "\n".join(lines)


def render_risk_markdown_report(reports: Sequence[RiskReport]) -> str:
    summary = _risk_summary(reports)
    lines = [
        "# 中文网文 AI 风险门禁报告",
        "",
        f"**检测章节数**：{summary['chapter_count']}",
        "",
        f"**总汉字数**：{summary['total_hanzi']:,}",
        "",
        f"**平均风险分**：{summary['average_risk_score']:.1f}/100",
        "",
        f"**通过/警告/失败**：{summary['pass_count']}/{summary['warn_count']}/{summary['fail_count']}",
        "",
        "## 逐章结果",
        "",
        "| 章节 | 汉字数 | 风险分 | 状态 | 严重 | 警告 | 提示 |",
        "|------|--------|--------|------|------|------|------|",
    ]
    for report in reports:
        counts = Counter(issue.severity for issue in report.issues)
        lines.append(
            f"| {report.title} | {report.hanzi_count:,} | {report.ai_risk_score:.1f} | "
            f"{_risk_status_label(report.gate_status)} | {counts['critical']} | "
            f"{counts['warning'] + counts['high']} | {counts['info']} |"
        )
    lines.extend(["", "## 详细问题", ""])
    for report in reports:
        lines.append(f"### {report.title}")
        lines.append("")
        lines.append(f"- 状态：{_risk_status_label(report.gate_status)}；汉字数：{report.hanzi_count:,}；风险分：{report.ai_risk_score:.1f}")
        lines.append("- 分项：" + "，".join(f"{key}={value:.1f}" for key, value in report.scores.items() if key != "total"))
        if not report.issues:
            lines.append("- 无明显风险。")
            lines.append("")
            continue
        for issue in sorted(report.issues, key=_risk_issue_sort_key):
            line_info = f"第{issue.line}行" if issue.line else "全文"
            lines.append(f"- [{issue.severity}] {issue.category} / `{issue.rule_id}`（{line_info}）")
            lines.append(f"  - 内容：`{issue.text}`")
            lines.append(f"  - 建议：{issue.suggestion}")
        lines.append("")
    return "\n".join(lines)


def render_risk_json_report(reports: Sequence[RiskReport]) -> str:
    return json.dumps(
        {"summary": _risk_summary(reports), "chapters": [_risk_report_to_dict(report) for report in reports]},
        ensure_ascii=False,
        indent=2,
    )


def _risk_exit_code(reports: Sequence[RiskReport], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    if fail_on == "fail":
        return 1 if any(report.gate_status == "fail" for report in reports) else 0
    if fail_on == "warn":
        return 1 if any(report.gate_status in {"warn", "fail"} for report in reports) else 0
    return 0


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


def cmd_risk(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f"错误: 路径不存在 - {target}", file=sys.stderr)
        return 2

    files = _collect_markdown_files(target)
    if not files:
        print(f"错误: 未找到 Markdown 文件 - {target}", file=sys.stderr)
        return 2

    fatal_rules, artifact_rules = _load_risk_rules(args.pattern_file)
    detector = RiskDetector(min_hanzi=args.min_hanzi, fatal_rules=fatal_rules, artifact_rules=artifact_rules)
    reports = [detector.detect_file(path) for path in files]

    if args.format == "json":
        output = render_risk_json_report(reports)
    elif args.format == "markdown":
        output = render_risk_markdown_report(reports)
    else:
        output = render_risk_console_report(reports)

    if args.output:
        Path(args.output).expanduser().write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return _risk_exit_code(reports, args.fail_on)


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

    pg = sub.add_parser("risk", help="批量执行朱雀/项目专项 AI 风险门禁")
    pg.add_argument("path", help="待检测的 Markdown 文件或目录")
    pg.add_argument("-o", "--output", default=None, help="输出报告路径")
    pg.add_argument("-f", "--format", choices=["console", "markdown", "json"], default="console")
    pg.add_argument("--fail-on", choices=["none", "warn", "fail"], default="none", help="门禁退出码策略")
    pg.add_argument("--min-hanzi", type=int, default=0, help="单章最低汉字数门槛，0 表示不检查")
    pg.add_argument("--pattern-file", default=None, help="自定义专项规则 JSON 文件")
    pg.set_defaults(func=cmd_risk)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
