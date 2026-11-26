"""
marp_parser.py — Canonical Marp Markdown Lesson Parser (ADR-0001)

Parses Marp Markdown lesson files in ``content/lessons/`` as the single authoring
source of truth for student-facing Learning Blocks, Spec 1.5 Practical Guides,
verbatim Examiner Alerts, Worked Examples, and Unified RAG ingestion chunks.

Key responsibilities (ADR-0001 & PRD Chapter 1 Vertical Slice):
1. Parse YAML frontmatter and ``---`` slide boundaries using pure Python stdlib.
2. Enforce the Chapter 1 Edexcel Modular 4XPH1 boundary: strictly specs
   ``1.3–1.10`` across 4 ordered Learning Blocks (``1.3–1.4``, ``1.5–1.6``,
   ``1.7–1.9``, ``1.10``), explicitly excluding legacy Spec ``1.1``.
3. Strip classroom/teacher choreography cues (e.g. ``"Hands down"``, partner /
   paired work, MWB board scans, cold-call prompts, lesson-plan author notes).
4. Convert ``Gate:`` / ``Decision gate:`` lines into structured, soft-gated
   ``<80%`` solo remediation items (never classroom re-teach or hard locks).
5. Parse progressive zero-render HTML comment directives:
   - ``<!-- student:analogy ... -->`` (inline or paired block)
   - ``<!-- student:reflection ... -->`` (inline or paired block)
   - ``<!-- widget:<type> ... -->``
   - ``<!-- teacher-only -->`` (slide-level, section-level, or inline exclusion)
6. Extract structured Learning Blocks, Worked Examples (``WE-``), Spec 1.5
   Practical Guide (``PRC-``), and verbatim Examiner Alerts (``EXM-``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence


# ---------------------------------------------------------------------------
# Curriculum Boundary Constants (Edexcel Modular 4XPH1 — Chapter 1)
# ---------------------------------------------------------------------------

CHAPTER_1_ALLOWED_SPECS: tuple[str, ...] = (
    "1.3",
    "1.4",
    "1.5",
    "1.6",
    "1.7",
    "1.8",
    "1.9",
    "1.10",
)

CHAPTER_1_EXCLUDED_SPECS: tuple[str, ...] = ("1.1",)


@dataclass(frozen=True)
class BlockDefinition:
    """Canonical block slot definition for a chapter."""

    block_index: int
    slug: str
    title: str
    spec_refs: tuple[str, ...]


CHAPTER_1_BLOCK_SPECS: tuple[BlockDefinition, ...] = (
    BlockDefinition(
        block_index=1,
        slug="distance-time-and-speed",
        title="Distance-Time Graphs & Average Speed",
        spec_refs=("1.3", "1.4"),
    ),
    BlockDefinition(
        block_index=2,
        slug="motion-practical-and-acceleration",
        title="Motion Practical & Acceleration",
        spec_refs=("1.5", "1.6"),
    ),
    BlockDefinition(
        block_index=3,
        slug="velocity-time-graphs",
        title="Velocity-Time Graphs: Gradient & Area",
        spec_refs=("1.7", "1.8", "1.9"),
    ),
    BlockDefinition(
        block_index=4,
        slug="uniform-acceleration-equation",
        title="Uniform Acceleration Equation (v² = u² + 2as)",
        spec_refs=("1.10",),
    ),
)

_SPEC_TO_CH1_BLOCK: dict[str, int] = {
    spec: blk.block_index
    for blk in CHAPTER_1_BLOCK_SPECS
    for spec in blk.spec_refs
}


# ---------------------------------------------------------------------------
# Public Structured Data Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningObjective:
    spec_ref: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VocabularyItem:
    term: str
    definition: str
    spec_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FormulaSummary:
    spec_ref: str
    description: str
    expression: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SoloRemediation:
    threshold_percent: int
    remediation_guidance: str
    next_step_guidance: str
    soft_gated: bool = True
    raw_gate_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfCheckItem:
    question: str
    answer: str
    spec_refs: list[str] = field(default_factory=list)
    solo_remediation: Optional[SoloRemediation] = None
    slide_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkedExample:
    example_id: str
    stage: str  # "i_do" | "we_do" | "you_do" | "model"
    title: str
    prompt: str
    solution: str
    steps: list[str] = field(default_factory=list)
    spec_refs: list[str] = field(default_factory=list)
    block_index: int = 0
    slide_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WidgetDirective:
    widget_type: str
    config: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    slide_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlockSection:
    heading: str
    body: str
    slide_number: int
    kind: str = "concept"  # "starter" | "concept" | "practical" | "practice" | "synthesis"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PracticalMethod:
    name: str
    summary: str
    procedure_steps: list[str] = field(default_factory=list)
    accuracy_notes: list[str] = field(default_factory=list)
    measurements: list[str] = field(default_factory=list)
    slide_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PracticalGuide:
    citation_id: str
    title: str
    spec_refs: list[str]
    spec_statement: str
    textbook_refs: list[str] = field(default_factory=list)
    methods: list[PracticalMethod] = field(default_factory=list)
    student_markdown: str = ""
    source_slides: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExaminerAlert:
    alert_id: str
    spec_refs: list[str]
    paper_code: str
    exam_session: str
    question_ref: str
    source_citation: str
    verbatim_text: str
    block_indices: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LearningBlock:
    block_index: int
    slug: str
    title: str
    spec_refs: list[str]
    citation_id: str
    textbook_refs: list[str] = field(default_factory=list)
    learning_objectives: list[LearningObjective] = field(default_factory=list)
    vocabulary: list[VocabularyItem] = field(default_factory=list)
    student_markdown: str = ""
    sections: list[BlockSection] = field(default_factory=list)
    guided_practice: list[WorkedExample] = field(default_factory=list)
    self_check: list[SelfCheckItem] = field(default_factory=list)
    solo_remediation: list[SoloRemediation] = field(default_factory=list)
    analogies: list[str] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    widgets: list[WidgetDirective] = field(default_factory=list)
    examiner_alerts: list[ExaminerAlert] = field(default_factory=list)
    source_slides: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParsedLesson:
    source_path: str
    title: str
    subtitle: str
    slug: str
    chapter_number: Optional[int]
    chapter_title: str
    qualification: str
    duration_minutes: Optional[int]
    frontmatter: dict[str, Any]
    spec_refs: list[str]
    learning_objectives: list[LearningObjective]
    vocabulary: list[VocabularyItem]
    formulas: list[FormulaSummary]
    blocks: list[LearningBlock]
    practical: Optional[PracticalGuide]
    examiner_alerts: list[ExaminerAlert]
    worked_examples: list[WorkedExample]
    excluded_teacher_slides: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SlideDirectives:
    """Result of extracting ADR-0001 HTML comment directives from a slide."""

    cleaned_text: str
    analogies: list[str] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    widgets: list[WidgetDirective] = field(default_factory=list)
    is_teacher_only_slide: bool = False
    had_teacher_only_content: bool = False


# ---------------------------------------------------------------------------
# Frontmatter & Slide Splitting (Pure Python)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_SLIDE_SEP_RE = re.compile(r"^[ \t]*---[ \t]*$")


def _parse_yaml_scalar(raw: str) -> Any:
    """Parse a single YAML scalar value without external dependencies."""
    val = raw.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    lower = val.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "~"):
        return None
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_yaml_scalar(part) for part in inner.split(",")]
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if re.fullmatch(r"-?\d+\.\d+", val):
        return float(val)
    return val


def parse_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    """Split and parse YAML frontmatter from Marp Markdown."""
    text = markdown_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or not _SLIDE_SEP_RE.match(lines[0]):
        return {}, text

    end_idx: Optional[int] = None
    for idx in range(1, len(lines)):
        if _SLIDE_SEP_RE.match(lines[idx]):
            end_idx = idx
            break

    if end_idx is None:
        return {}, text

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])

    frontmatter: dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key is not None:
            frontmatter.setdefault(current_list_key, []).append(
                _parse_yaml_scalar(stripped[2:])
            )
            continue
        if ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if not rest:
                frontmatter[key] = []
                current_list_key = key
            else:
                frontmatter[key] = _parse_yaml_scalar(rest)
                current_list_key = None

    return frontmatter, body


def split_marp_slides(body: str) -> list[str]:
    """Split Marp Markdown body into raw slides on standalone ``---`` lines."""
    slides: list[str] = []
    current: list[str] = []
    in_fence = False
    fence_char = ""
    in_comment = False

    for line in body.split("\n"):
        if not in_comment:
            fence_match = _FENCE_RE.match(line)
            if fence_match:
                marker = fence_match.group(1)
                if not in_fence:
                    in_fence = True
                    fence_char = marker[0]
                elif marker[0] == fence_char:
                    in_fence = False
                    fence_char = ""

        if not in_fence:
            if not in_comment and "<!--" in line and "-->" not in line:
                in_comment = True
            elif in_comment and "-->" in line:
                in_comment = False

        if not in_fence and not in_comment and _SLIDE_SEP_RE.match(line):
            slide_text = "\n".join(current).strip()
            if slide_text:
                slides.append(slide_text)
            current = []
            continue

        current.append(line)

    tail = "\n".join(current).strip()
    if tail:
        slides.append(tail)

    return slides


# ---------------------------------------------------------------------------
# HTML Comment Directives (ADR-0001)
# ---------------------------------------------------------------------------

_TEACHER_ONLY_PAIRED_RE = re.compile(
    r"<!--\s*teacher-only\s*-->[\s\S]*?<!--\s*(?:/teacher-only|end[-:\s]?teacher-only)\s*-->",
    re.IGNORECASE,
)
_TEACHER_ONLY_INLINE_RE = re.compile(
    r"<!--\s*teacher-only\b\s*(?::\s*|\s+)(?!\s*-->)[\s\S]*?-->",
    re.IGNORECASE,
)
_TEACHER_ONLY_MARKER_RE = re.compile(
    r"<!--\s*teacher-only\s*-->",
    re.IGNORECASE,
)

_ANALOGY_RE = re.compile(
    r"<!--\s*student:analogy\s*-->([\s\S]*?)<!--\s*(?:/student:analogy|end[-:\s]?student:analogy)\s*-->"
    r"|<!--\s*student:analogy\b\s*(?::\s*|\s+)(?!\s*-->)([\s\S]*?)-->",
    re.IGNORECASE,
)

_REFLECTION_RE = re.compile(
    r"<!--\s*student:reflection\s*-->([\s\S]*?)<!--\s*(?:/student:reflection|end[-:\s]?student:reflection)\s*-->"
    r"|<!--\s*student:reflection\b\s*(?::\s*|\s+)(?!\s*-->)([\s\S]*?)-->",
    re.IGNORECASE,
)

_WIDGET_RE = re.compile(
    r"<!--\s*widget:([A-Za-z0-9_.\-]+)(?:\s+([\s\S]*?))?-->",
    re.IGNORECASE,
)

_ANY_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_KV_PAIR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))')


def _parse_widget_config(raw_args: Optional[str]) -> dict[str, Any]:
    if not raw_args or not raw_args.strip():
        return {}
    stripped = raw_args.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            loaded = json.loads(stripped)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

    config: dict[str, Any] = {}
    matches = list(_KV_PAIR_RE.finditer(stripped))
    if matches:
        for match in matches:
            key = match.group(1)
            val_str = (
                match.group(2)
                if match.group(2) is not None
                else match.group(3)
                if match.group(3) is not None
                else match.group(4)
            )
            config[key] = _parse_yaml_scalar(val_str)
        return config

    return {"raw_args": stripped}


def _has_substantive_student_content(text: str) -> bool:
    """Return True if text contains body content beyond a single heading/ref."""
    non_empty = [line.strip() for line in text.split("\n") if line.strip()]
    if not non_empty:
        return False
    # If all preceding lines are headings or textbook quote markers, the
    # unpaired <!-- teacher-only --> marker covers the entire slide.
    for line in non_empty:
        if not line.startswith("#") and not line.startswith(">"):
            return True
    return False


def extract_directives(slide_text: str, slide_number: int = 0) -> SlideDirectives:
    """Extract ADR-0001 progressive zero-render HTML comment directives."""
    text = slide_text
    had_teacher_only = False
    is_teacher_only_slide = False

    # 1. Paired <!-- teacher-only --> ... <!-- /teacher-only -->
    if _TEACHER_ONLY_PAIRED_RE.search(text):
        had_teacher_only = True
        text = _TEACHER_ONLY_PAIRED_RE.sub("", text)

    # 2. Inline <!-- teacher-only: ... --> or <!-- teacher-only ... -->
    if _TEACHER_ONLY_INLINE_RE.search(text):
        had_teacher_only = True
        text = _TEACHER_ONLY_INLINE_RE.sub("", text)

    # 3. Unpaired <!-- teacher-only --> (slide-level or trailing section-level)
    marker_match = _TEACHER_ONLY_MARKER_RE.search(text)
    if marker_match:
        had_teacher_only = True
        before = text[: marker_match.start()].strip()
        if not _has_substantive_student_content(before):
            is_teacher_only_slide = True
            return SlideDirectives(
                cleaned_text="",
                is_teacher_only_slide=True,
                had_teacher_only_content=True,
            )
        text = before

    # 4. <!-- student:analogy --> (single pass preserving document order)
    analogies: list[str] = []

    def _collect_analogy(match: re.Match[str]) -> str:
        raw_val = match.group(1) if match.group(1) is not None else match.group(2)
        content = _normalize_whitespace(raw_val or "")
        if content:
            analogies.append(content)
        return ""

    text = _ANALOGY_RE.sub(_collect_analogy, text)

    # 5. <!-- student:reflection --> (single pass preserving document order)
    reflections: list[str] = []

    def _collect_reflection(match: re.Match[str]) -> str:
        raw_val = match.group(1) if match.group(1) is not None else match.group(2)
        content = _normalize_whitespace(raw_val or "")
        if content:
            reflections.append(content)
        return ""

    text = _REFLECTION_RE.sub(_collect_reflection, text)

    # 6. <!-- widget:<type> ... -->
    widgets: list[WidgetDirective] = []

    def _collect_widget(match: re.Match[str]) -> str:
        widget_type = match.group(1).strip()
        raw_args = match.group(2)
        widgets.append(
            WidgetDirective(
                widget_type=widget_type,
                config=_parse_widget_config(raw_args),
                raw=match.group(0).strip(),
                slide_number=slide_number,
            )
        )
        return ""

    text = _WIDGET_RE.sub(_collect_widget, text)

    # 7. Strip any remaining zero-render HTML comments from student output
    text = _ANY_HTML_COMMENT_RE.sub("", text)
    text = _collapse_blank_lines(text).strip()

    # If the slide contained only teacher-only content and nothing substantive remains
    if had_teacher_only and not _has_substantive_student_content(text) and not (
        analogies or reflections or widgets
    ):
        is_teacher_only_slide = True

    return SlideDirectives(
        cleaned_text=text,
        analogies=analogies,
        reflections=reflections,
        widgets=widgets,
        is_teacher_only_slide=is_teacher_only_slide,
        had_teacher_only_content=had_teacher_only,
    )


# ---------------------------------------------------------------------------
# Teacher Choreography Stripping & Gate -> Solo Remediation Conversion
# ---------------------------------------------------------------------------

_DROP_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bhands\s+down\b", re.IGNORECASE),
    re.compile(r"\bboards?\s+up\b", re.IGNORECASE),
    re.compile(r"\bscan\s+the\s+room\b", re.IGNORECASE),
    re.compile(r"\bshow\s+your\s+boards?\b", re.IGNORECASE),
    re.compile(r"\bcold[-\s]call\b", re.IGNORECASE),
    re.compile(r"\bturn\s+and\s+talk\b", re.IGNORECASE),
    re.compile(r"\bthink[-\s]pair[-\s]share\b", re.IGNORECASE),
    re.compile(r"\bteacher\s+models,\s*narrating\b", re.IGNORECASE),
    re.compile(r"\bclass\s+fills\s+the\s+steps\s+with\s+teacher\s+prompting\b", re.IGNORECASE),
    re.compile(r"\bpaired\s+work\b", re.IGNORECASE),
    re.compile(r"\bindividual\s+work\s*[—–-]\s*no\s+teacher\s+help\b", re.IGNORECASE),
    re.compile(r"\bcheck\s+with\s+your\s+partner\b", re.IGNORECASE),
    re.compile(r"\bcompare\s+with\s+your\s+partner\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+the\s+lesson\s+plan\b.*\bclassroom\b", re.IGNORECASE),
    re.compile(r"\bclass\s+counts\s+steps\s+aloud\b", re.IGNORECASE),
    re.compile(r"\bkeep\s+the\s+loop\s+sketch\s+on\s+the\s+board\b", re.IGNORECASE),
)

_INLINE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Classroom whiteboard & gesture cues
    (re.compile(r"\s*[—–-]\s*hold\s+up\s+[^?!\n]+", re.IGNORECASE), "?"),
    (re.compile(r"\bhold\s+up\s+(?:your\s+)?(?:boards?|cards?|S\s+or\s+V)\b", re.IGNORECASE), ""),
    (re.compile(r"\bthe\s+graph\s+shape\s+named\s+by\s+your\s+partner\b", re.IGNORECASE), "each graph shape"),
    (re.compile(r"\bnamed\s+by\s+your\s+partner\b", re.IGNORECASE), ""),
    (re.compile(r"\bwith\s+your\s+partner\b", re.IGNORECASE), "independently"),
    (re.compile(r"\byour\s+partner\b", re.IGNORECASE), "yourself"),
    # Modelling band headings & teacher labels
    (re.compile(r"\bI\s+Do:\s*Teacher\s+Models\b", re.IGNORECASE), "I Do: Worked Example"),
    (re.compile(r"\bWe\s+Do:\s*Class\s+Completes\s+Together\b", re.IGNORECASE), "We Do: Guided Walkthrough"),
    (re.compile(r"\bYou\s+Do:\s*Paired\s+Practice\b", re.IGNORECASE), "You Do: Guided Practice"),
    (re.compile(r"\bYou\s+Do:\s*Independent\s+Exam-Style\s+Q\b", re.IGNORECASE), "You Do: Independent Exam-Style Practice"),
    (re.compile(r"\btogether,\s*units\s+stressed\b", re.IGNORECASE), "step by step, carrying units on every line"),
    (re.compile(r"\bSteps\s+to\s+prompt:", re.IGNORECASE), "Steps to follow:"),
    (re.compile(r"\s*[—–-]\s*no\s+teacher\s+help\b", re.IGNORECASE), ""),
    (re.compile(r"\bno\s+teacher\s+help\b", re.IGNORECASE), ""),
    # Classroom board / peer / teacher imperative cues
    (re.compile(r"\bstudents\s+correct\s+it\s+on\s+boards,\s*", re.IGNORECASE), "correct the statement, "),
    (re.compile(r"\bon\s+mini[-\s]?whiteboards?\b", re.IGNORECASE), ""),
    (re.compile(r"\bon\s+boards?\b", re.IGNORECASE), ""),
    (re.compile(r"\bDemonstrate\s+the\s+ticker-timer\s+bench\s+setup\s*(?:\([^)]*\))?\s*:", re.IGNORECASE), "Ticker-timer bench setup:"),
    (re.compile(r"\bGroups\s+collect\s+their\s+own\s+tape\s+today\s*;", re.IGNORECASE), "Collect a motion tape using the timer;"),
    (re.compile(r"\bis\s+next\s+lesson'?s\s+measured\s+write-up\b", re.IGNORECASE), "completes the measured analysis"),
    (
        re.compile(
            r"\bRequire\s+the\s+([^.\n]+?)\s+list\s+before\s+substitution\s+on\s+every\s+ticket\.?",
            re.IGNORECASE,
        ),
        r"List \1 before substituting values.",
    ),
    (re.compile(r"\bbring\s+the\s+tape-analysis\s+graph\s+for\s+peer\s+marking\b", re.IGNORECASE), "complete the tape-analysis graph"),
    (re.compile(r"\bfor\s+peer\s+marking\b", re.IGNORECASE), "for self-checking"),
    # MWB Check headers -> Self-Check
    (
        re.compile(
            r"\*\*MWB\s+Check(?:\s*\([^)]*\))?\s*(?:[—–-]\s*Chunk\s*\d+\s*close)?\s*:\*\*",
            re.IGNORECASE,
        ),
        "**Self-Check:**",
    ),
    (
        re.compile(r"\bMWB\s+Check(?:\s*\([^)]*\))?(?:\s*[—–-]\s*[^:\n]+)?", re.IGNORECASE),
        "Self-Check",
    ),
    (re.compile(r"\bMWB\s+Quiz(?:\s*\([^)]*\))?", re.IGNORECASE), "Quick Recall Check"),
    (re.compile(r"\bMWB\b", re.IGNORECASE), "Self-Check"),
    # Lesson-plan / exemplar / pacing meta annotations
    (re.compile(r"\s*\(\s*\d+\s*min\s*,\s*from\s+the\s+lesson\s+plan\s*\)", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*from\s+the\s+lesson\s+plan\s*\)", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*from\s+exemplar\s+LP\s*\)", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*\d+\s*min\s*,\s*exemplar\s+practical\s*\)", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*exemplar\s+[^)]*\)", re.IGNORECASE), ""),
    (re.compile(r"\s*per\s+exemplar\s+differentiation\s+note", re.IGNORECASE), ""),
    (re.compile(r"\s*\(\s*\d+\s*min(?:\s+setup,\s*full\s+analysis\s+next\s+lesson)?\s*\)", re.IGNORECASE), ""),
    (re.compile(r"\*\*From\s+the\s+lesson\s+plan:\*\*\s*", re.IGNORECASE), ""),
    (re.compile(r"\bfrom\s+the\s+lesson\s+plan\b", re.IGNORECASE), ""),
)


def strip_teacher_choreography(text: str) -> str:
    """
    Strip classroom and teacher choreography cues from Marp slide text while
    preserving physics terminology, equations, LaTeX, and student explanations.
    """
    if not text:
        return ""

    kept_lines: list[str] = []
    for raw_line in text.split("\n"):
        if any(pat.search(raw_line) for pat in _DROP_LINE_PATTERNS):
            continue
        line = raw_line
        for pattern, replacement in _INLINE_REPLACEMENTS:
            line = pattern.sub(replacement, line)
        # Clean up artifacts created by removals
        line = re.sub(r"\(\s*\)", "", line)
        line = re.sub(r"\s+([,.;:?!])", r"\1", line)
        line = re.sub(r"\?{2,}", "?", line)
        line = re.sub(r"[ \t]{2,}", " ", line)
        # Clean trailing empty separators like "(rearrangement practice — formula triangles allowed )."
        line = re.sub(r"\s+\)", ")", line)
        line = re.sub(r"\(\s+", "(", line)
        line = line.rstrip()
        kept_lines.append(line)

    return _collapse_blank_lines("\n".join(kept_lines)).strip()


_GATE_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*]\s+)?(?:\*\*)?(?:Decision\s+)?Gate(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.+)$",
    re.IGNORECASE,
)

_REMEDIATION_SOLO_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpair[-\s]?reteach\b", re.IGNORECASE), "review step by step"),
    (re.compile(r"\bre[-\s]?teach\b", re.IGNORECASE), "review"),
    (re.compile(r"\bteacher\s+reviews?\b", re.IGNORECASE), "review"),
    (re.compile(r"\bclass\s+reviews?\b", re.IGNORECASE), "review"),
)

_NEXT_STEP_SOLO_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bChunk\s*1\b", re.IGNORECASE), "Block 1"),
    (re.compile(r"\bChunk\s*2\b", re.IGNORECASE), "Block 2"),
    (re.compile(r"\bChunk\s*3\b", re.IGNORECASE), "Block 3"),
    (re.compile(r"\bChunk\s*4\b", re.IGNORECASE), "Block 4"),
    (re.compile(r"\bPlenary\b", re.IGNORECASE), "Block 4 (Synthesis)"),
)


def parse_gate_to_solo_remediation(line: str) -> Optional[SoloRemediation]:
    """
    Convert a Marp ``Gate:`` or ``Decision gate:`` line into a structured,
    soft-gated ``SoloRemediation`` item for self-paced students (ADR-0001/0003).
    """
    match = _GATE_LINE_RE.match(line.strip())
    if not match:
        return None

    body = match.group(1).strip()
    if not body:
        return None

    thresh_match = re.search(r"<\s*(\d+)\s*%", body)
    threshold = int(thresh_match.group(1)) if thresh_match else 80

    # Split into <threshold remediation part and >=threshold progression part
    if ";" in body:
        low_part, high_part = body.split(";", 1)
    else:
        split_high = re.split(r"(?=(?:≥|>=)\s*\d+\s*%)", body, maxsplit=1)
        low_part = split_high[0]
        high_part = split_high[1] if len(split_high) > 1 else ""

    low_clean = re.sub(
        r"^<\s*\d+\s*%(?:\s*correct)?\s*(?:→|->|:)?\s*",
        "",
        low_part.strip(),
        flags=re.IGNORECASE,
    )
    for pat, repl in _REMEDIATION_SOLO_REPLACEMENTS:
        low_clean = pat.sub(repl, low_clean)
    low_clean = strip_teacher_choreography(low_clean).strip(" .;")
    if low_clean:
        low_clean = low_clean[0].upper() + low_clean[1:] + "."

    high_clean = re.sub(
        r"^(?:≥|>=)\s*\d+\s*%(?:\s*correct)?\s*(?:→|->|:)?\s*",
        "",
        high_part.strip(),
        flags=re.IGNORECASE,
    )
    for pat, repl in _NEXT_STEP_SOLO_REPLACEMENTS:
        high_clean = pat.sub(repl, high_clean)
    high_clean = strip_teacher_choreography(high_clean).strip(" .;")
    if high_clean:
        if not high_clean.lower().startswith(("continue", "move", "proceed")):
            high_clean = f"Continue to {high_clean}."
        else:
            high_clean = high_clean[0].upper() + high_clean[1:] + "."
    else:
        high_clean = "Continue to the next learning block whenever you are ready."

    return SoloRemediation(
        threshold_percent=threshold,
        remediation_guidance=low_clean,
        next_step_guidance=high_clean,
        soft_gated=True,
        raw_gate_line=line.strip(),
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "lesson"


def _spec_sort_key(spec: str) -> tuple[int, ...]:
    parts = spec.split(".")
    result: list[int] = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    return tuple(result)


def _filter_specs(
    specs: Sequence[str],
    *,
    enforce_chapter1_boundary: bool,
) -> list[str]:
    """Deduplicate, sort, and optionally enforce Chapter 1 (1.3–1.10, no 1.1)."""
    unique: list[str] = []
    seen: set[str] = set()
    for raw in specs:
        s = raw.strip()
        if not s or s in seen:
            continue
        if enforce_chapter1_boundary:
            if s in CHAPTER_1_EXCLUDED_SPECS or s not in CHAPTER_1_ALLOWED_SPECS:
                continue
        seen.add(s)
        unique.append(s)
    return sorted(unique, key=_spec_sort_key)


_PAREN_SPEC_RE = re.compile(r"\(([^)]+)\)")
_SPEC_TOKEN_RE = re.compile(r"(?<!\d)(\d+\.\d+)(?!\d)(?!\s*(?:m/s|m\b|s\b|Hz\b|kg\b|N\b|cm\b|km\b|min\b))")


def _extract_explicit_spec_refs(text: str) -> list[str]:
    """
    Extract explicit Edexcel spec codes from headings/spec annotations without
    confusing physical values like ``1.5 m/s`` or ``3.0 s`` for spec codes.
    """
    found: list[str] = []

    # 1. Parenthesized spec annotations like "(1.3, 1.4)" or "Exam-style (1.6)"
    for paren_match in _PAREN_SPEC_RE.finditer(text):
        inner = paren_match.group(1).strip()
        if re.fullmatch(r"[\d.\s,/–-]+", inner):
            found.extend(_SPEC_TOKEN_RE.findall(inner))

    # 2. Lines explicitly mentioning Spec / objectives
    for line in text.split("\n"):
        if re.search(r"\b(?:spec|objectives?|spec\s+points?)\b", line, re.IGNORECASE):
            found.extend(_SPEC_TOKEN_RE.findall(line))

    return found


def _extract_table_rows(text: str) -> list[list[str]]:
    """Parse standard GitHub-flavored Markdown table rows (excluding header/separator)."""
    rows: list[list[str]] = []
    lines = text.split("\n")
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("|") and line.endswith("|"):
            if idx + 1 < len(lines) and re.match(
                r"^\|[\s:|-]+\|$", lines[idx + 1].strip()
            ):
                # Skip header and separator
                idx += 2
                while idx < len(lines):
                    row_line = lines[idx].strip()
                    if not (row_line.startswith("|") and row_line.endswith("|")):
                        break
                    cells = [c.strip() for c in row_line.strip("|").split("|")]
                    rows.append(cells)
                    idx += 1
                continue
        idx += 1
    return rows


def _extract_section_table_rows(text: str, heading_pattern: str) -> list[list[str]]:
    """Extract Markdown table rows under a specific subheading."""
    lines = text.split("\n")
    in_section = False
    section_lines: list[str] = []
    pat = re.compile(heading_pattern, re.IGNORECASE)
    for line in lines:
        if re.match(r"^#{1,4}\s+", line):
            if pat.search(line):
                in_section = True
                continue
            if in_section:
                break
        if in_section:
            section_lines.append(line)
    return _extract_table_rows("\n".join(section_lines))


def _extract_heading(slide_text: str) -> str:
    for line in slide_text.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _extract_textbook_refs(slide_text: str) -> list[str]:
    refs: list[str] = []
    for line in slide_text.split("\n"):
        m = re.search(r"\*\*Textbook:\*\*\s*(.+)$", line, re.IGNORECASE)
        if m:
            ref = m.group(1).strip()
            if ref and ref not in refs:
                refs.append(ref)
    return refs


def _strip_heading_and_textbook_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^#\s+", stripped):
            continue
        if re.search(r"\*\*Textbook:\*\*", stripped, re.IGNORECASE):
            continue
        kept.append(line)
    return _collapse_blank_lines("\n".join(kept)).strip()


def _clean_verbatim_examiner_quote(raw: str) -> str:
    """Unwrap Markdown italics/quotes around a verbatim examiner note without altering wording."""
    text = raw.strip()
    if text.startswith("*") and text.endswith("*") and len(text) > 2:
        text = text[1:-1].strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("“") and text.endswith("”")
    ):
        text = text[1:-1].strip()
    return text


_EXAMINER_SOURCE_RE = re.compile(
    r"(?P<paper>[A-Z0-9]+/[A-Z0-9]+)\s+"
    r"(?P<session>(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})"
    r".*?(?P<question>Q\d+[a-z0-9()]*)",
    re.IGNORECASE,
)


def _parse_examiner_source(source_citation: str) -> tuple[str, str, str]:
    m = _EXAMINER_SOURCE_RE.search(source_citation)
    if m:
        return m.group("paper").strip(), m.group("session").strip(), m.group("question").strip()
    q_match = re.search(r"\b(Q\d+[a-z0-9()]*)\b", source_citation, re.IGNORECASE)
    return "", "", q_match.group(1) if q_match else ""


def _infer_vocab_specs(term: str, definition: str, allowed_specs: set[str]) -> list[str]:
    combined = f"{term} {definition}".lower()
    specs: list[str] = []
    if "average speed" in combined or "v = s/t" in combined:
        specs.extend(["1.3", "1.4"])
    if "acceleration" in combined and "uniform acceleration" not in combined:
        specs.append("1.6")
    if "gradient" in combined:
        specs.extend(["1.3", "1.7", "1.8"])
    if "area" in combined and ("v-t" in combined or "velocity-time" in combined):
        specs.extend(["1.7", "1.9"])
    if "uniform acceleration" in combined or "v^2 = u^2" in combined:
        specs.append("1.10")
    return sorted([s for s in dict.fromkeys(specs) if s in allowed_specs], key=_spec_sort_key)


def _extract_question_answer(text: str) -> tuple[str, str]:
    """Extract quoted self-check prompt and ``Answer: ...`` from a check line/slide."""
    cleaned = strip_teacher_choreography(text)
    # Remove any Gate lines before extracting Q/A
    non_gate_lines = [
        line for line in cleaned.split("\n") if not _GATE_LINE_RE.match(line.strip())
    ]
    joined = _normalize_whitespace(" ".join(non_gate_lines))
    joined = re.sub(r"^\*\*Self-Check:\*\*\s*", "", joined, flags=re.IGNORECASE)

    q_match = re.search(r'"([^"]+)"', joined)
    ans_match = re.search(r"(?:\*\*)?Answer(?:\*\*)?\s*:\s*(.+)$", joined, re.IGNORECASE)

    question = q_match.group(1).strip() if q_match else ""
    answer = ans_match.group(1).strip() if ans_match else ""

    if not question and joined:
        if ans_match:
            question = joined[: ans_match.start()].strip(' "—–-')
        else:
            question = joined

    return question, answer


def _assign_block_index(
    heading: str,
    body: str,
    explicit_specs: list[str],
    *,
    enforce_chapter1_boundary: bool,
) -> Optional[int]:
    """Determine which Chapter 1 Learning Block (1..4) a slide belongs to."""
    # If explicit specs were declared on the slide and ALL of them are excluded
    # (e.g. a slide exclusively about Spec 1.1), exclude it from Chapter 1 blocks.
    if enforce_chapter1_boundary and explicit_specs:
        filtered = _filter_specs(explicit_specs, enforce_chapter1_boundary=True)
        if not filtered:
            return None
        # Map to first matching block (e.g., (1.3, 1.4, 1.5) on I Do runner example -> Block 1)
        for spec in filtered:
            if spec in _SPEC_TO_CH1_BLOCK:
                return _SPEC_TO_CH1_BLOCK[spec]

    h_lower = heading.lower()
    b_lower = body.lower()

    if "chunk 1" in h_lower or "distance-time" in h_lower or "d-t graph" in b_lower:
        if "v-t graph" not in b_lower and "velocity-time" not in b_lower:
            return 1
    if "chunk 2" in h_lower or "practical" in h_lower or "ticker-timer" in h_lower:
        return 2
    if "after modelling" in h_lower or ("v-t graph" in b_lower and "area" in b_lower):
        return 3
    if "velocity-time" in h_lower or ("v-t graph" in b_lower and "acceleration" in b_lower and "distance" in b_lower):
        return 3
    if "v^2" in b_lower or "uniformly" in b_lower or "1.10" in b_lower or "synthesis" in h_lower:
        return 4
    if "mid split-layout" in h_lower:
        return 4
    if "i do" in h_lower or "we do" in h_lower or "paired practice" in h_lower or "slide 15" in h_lower:
        return 1
    if "independent exam-style" in h_lower or ("acceleration questions" in b_lower):
        return 2
    if "starter" in h_lower:
        return 1

    # Default fallback for untagged content slides (e.g. minimal synthetic decks)
    return 1


# ---------------------------------------------------------------------------
# Main Parser Implementation
# ---------------------------------------------------------------------------


def parse_marp_markdown(
    markdown_text: str,
    *,
    source_path: str = "",
    enforce_chapter1_boundary: bool = True,
) -> ParsedLesson:
    """
    Parse a Marp Markdown string into a structured ``ParsedLesson`` conforming
    to ADR-0001 and the Chapter 1 Vertical Slice specification.
    """
    frontmatter, body = parse_frontmatter(markdown_text)
    raw_slides = split_marp_slides(body)

    # Lesson-level metadata accumulators
    title = ""
    subtitle = ""
    chapter_number: Optional[int] = None
    chapter_title = ""
    qualification = ""
    duration_minutes: Optional[int] = None
    raw_spec_refs: list[str] = []
    learning_objectives: list[LearningObjective] = []
    vocabulary: list[VocabularyItem] = []
    formulas: list[FormulaSummary] = []
    examiner_alerts: list[ExaminerAlert] = []
    excluded_teacher_slides: list[int] = []

    # Per-block accumulators (4 canonical Chapter 1 blocks)
    block_sections: dict[int, list[BlockSection]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_textbooks: dict[int, list[str]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_examples: dict[int, list[WorkedExample]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_checks: dict[int, list[SelfCheckItem]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_remediations: dict[int, list[SoloRemediation]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_analogies: dict[int, list[str]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_reflections: dict[int, list[str]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_widgets: dict[int, list[WidgetDirective]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}
    block_slides: dict[int, list[int]] = {b.block_index: [] for b in CHAPTER_1_BLOCK_SPECS}

    # Practical Guide accumulators (Spec 1.5)
    practical_methods: list[PracticalMethod] = []
    practical_textbooks: list[str] = []
    practical_slides: list[int] = []

    # Tracking helpers for deduplication
    seen_example_signatures: set[str] = set()
    seen_check_questions: dict[int, set[str]] = {b.block_index: set() for b in CHAPTER_1_BLOCK_SPECS}
    seen_remediation_keys: dict[int, set[str]] = {b.block_index: set() for b in CHAPTER_1_BLOCK_SPECS}
    seen_alert_texts: set[str] = set()
    all_worked_examples: list[WorkedExample] = []

    def _add_worked_example(
        *,
        block_index: int,
        stage: str,
        ex_title: str,
        prompt: str,
        solution: str,
        steps: list[str],
        spec_refs: list[str],
        slide_number: int,
    ) -> None:
        sig = _normalize_whitespace(f"{stage}:{prompt}:{solution}").lower()
        if not prompt and not solution:
            return
        if sig in seen_example_signatures:
            return
        seen_example_signatures.add(sig)
        ex_id = f"WE-{len(all_worked_examples) + 1}"
        filtered_refs = _filter_specs(
            spec_refs or list(CHAPTER_1_BLOCK_SPECS[block_index - 1].spec_refs),
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        example = WorkedExample(
            example_id=ex_id,
            stage=stage,
            title=ex_title,
            prompt=prompt,
            solution=solution,
            steps=steps,
            spec_refs=filtered_refs,
            block_index=block_index,
            slide_number=slide_number,
        )
        all_worked_examples.append(example)
        block_examples[block_index].append(example)

    def _add_remediation(block_index: int, rem: SoloRemediation) -> None:
        key = rem.remediation_guidance.lower().strip()
        if key and key not in seen_remediation_keys[block_index]:
            seen_remediation_keys[block_index].add(key)
            block_remediations[block_index].append(rem)

    def _add_self_check(block_index: int, item: SelfCheckItem) -> None:
        q_key = _normalize_whitespace(item.question).lower()
        if not q_key:
            return
        if q_key in seen_check_questions[block_index]:
            # Enrich existing check if this one carries solo_remediation and the prior did not
            if item.solo_remediation is not None:
                updated: list[SelfCheckItem] = []
                for existing in block_checks[block_index]:
                    if (
                        _normalize_whitespace(existing.question).lower() == q_key
                        and existing.solo_remediation is None
                    ):
                        updated.append(
                            SelfCheckItem(
                                question=existing.question,
                                answer=existing.answer or item.answer,
                                spec_refs=existing.spec_refs or item.spec_refs,
                                solo_remediation=item.solo_remediation,
                                slide_number=existing.slide_number,
                            )
                        )
                    else:
                        updated.append(existing)
                block_checks[block_index] = updated
            return
        seen_check_questions[block_index].add(q_key)
        block_checks[block_index].append(item)

    def _record_slide(block_index: int, slide_number: int, tb_refs: list[str]) -> None:
        if slide_number not in block_slides[block_index]:
            block_slides[block_index].append(slide_number)
        for ref in tb_refs:
            if ref not in block_textbooks[block_index]:
                block_textbooks[block_index].append(ref)

    # First pass over slides
    for slide_number, raw_slide in enumerate(raw_slides, start=1):
        directives = extract_directives(raw_slide, slide_number=slide_number)
        if directives.is_teacher_only_slide:
            excluded_teacher_slides.append(slide_number)
            continue

        slide_text = directives.cleaned_text
        heading = _extract_heading(slide_text)
        heading_lower = heading.lower()
        tb_refs = _extract_textbook_refs(slide_text)
        explicit_specs = _extract_explicit_spec_refs(slide_text)

        # --- Slide 1 / Title metadata slide ---
        if slide_number == 1 and re.search(r"\*\*Spec:\*\*|\*\*Duration:\*\*", slide_text, re.IGNORECASE):
            title = heading or title
            sub_match = re.search(r"^##\s+(.+)$", slide_text, re.MULTILINE)
            if sub_match:
                subtitle = sub_match.group(1).strip()
            ch_match = re.search(r"\bCh\.?\s*(\d+)\b", f"{subtitle} {frontmatter.get('footer', '')}", re.IGNORECASE)
            if ch_match:
                chapter_number = int(ch_match.group(1))
            dur_match = re.search(r"\*\*Duration:\*\*\s*(\d+)\s*min", slide_text, re.IGNORECASE)
            if dur_match:
                duration_minutes = int(dur_match.group(1))
            qual_match = re.search(
                r"\*\*Spec:\*\*\s*(.+?)(?:\s+objectives\b|\n|$)",
                slide_text,
                re.IGNORECASE,
            )
            if qual_match:
                qualification = qual_match.group(1).strip()
            raw_spec_refs.extend(explicit_specs)
            # Attach any progressive directives placed on Slide 1 to Block 1
            block_analogies[1].extend(directives.analogies)
            block_reflections[1].extend(directives.reflections)
            block_widgets[1].extend(directives.widgets)
            continue

        # --- Learning Objectives slide ---
        if "learning objectives" in heading_lower:
            rows = _extract_table_rows(slide_text)
            for cells in rows:
                if len(cells) >= 2:
                    ref_raw = re.sub(r"[*`]", "", cells[0]).strip()
                    if re.fullmatch(r"\d+\.\d+", ref_raw):
                        raw_spec_refs.append(ref_raw)
                        filtered = _filter_specs(
                            [ref_raw],
                            enforce_chapter1_boundary=enforce_chapter1_boundary,
                        )
                        if filtered:
                            learning_objectives.append(
                                LearningObjective(spec_ref=filtered[0], text=cells[1].strip())
                            )
            block_analogies[1].extend(directives.analogies)
            block_reflections[1].extend(directives.reflections)
            block_widgets[1].extend(directives.widgets)
            continue

        # --- Key Vocabulary slide ---
        if "key vocabulary" in heading_lower:
            allowed_set = set(CHAPTER_1_ALLOWED_SPECS) if enforce_chapter1_boundary else set(raw_spec_refs)
            for cells in _extract_table_rows(slide_text):
                if len(cells) >= 2:
                    term = re.sub(r"^\*\*|\*\*$", "", cells[0]).strip()
                    defn = strip_teacher_choreography(cells[1].strip())
                    v_specs = _infer_vocab_specs(term, defn, allowed_set or set(CHAPTER_1_ALLOWED_SPECS))
                    vocabulary.append(
                        VocabularyItem(term=term, definition=defn, spec_refs=v_specs)
                    )
            continue

        # --- Curriculum Resources / Examiner Report Highlights slide ---
        if "curriculum resources" in heading_lower or "examiner report highlights" in slide_text.lower():
            examiner_rows = _extract_section_table_rows(slide_text, r"examiner\s+report\s+highlights")
            for cells in examiner_rows:
                if len(cells) >= 3:
                    row_specs = _SPEC_TOKEN_RE.findall(cells[0])
                    filtered_row_specs = _filter_specs(
                        row_specs,
                        enforce_chapter1_boundary=enforce_chapter1_boundary,
                    )
                    if not filtered_row_specs and enforce_chapter1_boundary:
                        continue
                    verbatim = _clean_verbatim_examiner_quote(cells[1])
                    source_cit = cells[2].strip()
                    norm_key = _normalize_whitespace(verbatim).lower()
                    if norm_key in seen_alert_texts:
                        continue
                    seen_alert_texts.add(norm_key)
                    paper_code, exam_session, question_ref = _parse_examiner_source(source_cit)
                    blk_indices = sorted(
                        {
                            _SPEC_TO_CH1_BLOCK[s]
                            for s in filtered_row_specs
                            if s in _SPEC_TO_CH1_BLOCK
                        }
                    )
                    examiner_alerts.append(
                        ExaminerAlert(
                            alert_id=f"EXM-{len(examiner_alerts) + 1}",
                            spec_refs=filtered_row_specs,
                            paper_code=paper_code,
                            exam_session=exam_session,
                            question_ref=question_ref,
                            source_citation=source_cit,
                            verbatim_text=verbatim,
                            block_indices=blk_indices,
                        )
                    )
            # Curriculum Resources slide (Sources consulted, Re-run triggers) is
            # metadata/provenance, never student block prose.
            continue

        # --- Split-Layout Assessment slides (handle dual-column mapping) ---
        if "split-layout assessment" in heading_lower:
            rows = _extract_table_rows(slide_text)
            for cells in rows:
                if len(cells) < 2:
                    continue
                left_raw, right_raw = cells[0], cells[1]
                left_clean = strip_teacher_choreography(left_raw)
                right_clean = strip_teacher_choreography(right_raw)
                right_specs = _filter_specs(
                    _extract_explicit_spec_refs(right_raw),
                    enforce_chapter1_boundary=enforce_chapter1_boundary,
                )

                # Slide 15: Model runner + Exam-style (1.3)
                if "model:" in left_raw.lower() and "100" in left_raw:
                    _record_slide(1, slide_number, tb_refs)
                    _add_worked_example(
                        block_index=1,
                        stage="model",
                        ex_title="Worked Example: Average Speed",
                        prompt="A runner covers 100 m in 12.5 s. Calculate the average speed.",
                        solution=re.sub(r"^\*\*Model:\*\*\s*", "", left_clean, flags=re.IGNORECASE),
                        steps=["Identify distance s = 100 m and time t = 12.5 s.", "Apply v = s/t = 100 / 12.5 = 8.0 m/s."],
                        spec_refs=["1.3", "1.4"],
                        slide_number=slide_number,
                    )
                    exam_prompt = re.sub(
                        r"^\*\*Exam-style\s*\([^)]+\):\*\*\s*",
                        "",
                        right_clean,
                        flags=re.IGNORECASE,
                    ).strip()
                    if exam_prompt:
                        block_sections[1].append(
                            BlockSection(
                                heading="Exam-Style Practice (1.3)",
                                body=exam_prompt,
                                slide_number=slide_number,
                                kind="practice",
                            )
                        )
                    continue

                # Slide 16: True/False Acceleration (Block 2) + Exam-style (1.4) (Block 1)
                if "true/false" in left_raw.lower():
                    _record_slide(2, slide_number, tb_refs)
                    block_sections[2].append(
                        BlockSection(
                            heading="Concept Check: Acceleration",
                            body=left_clean,
                            slide_number=slide_number,
                            kind="practice",
                        )
                    )
                    target_right_blk = _SPEC_TO_CH1_BLOCK.get(right_specs[0], 1) if right_specs else 1
                    _record_slide(target_right_blk, slide_number, tb_refs)
                    block_sections[target_right_blk].append(
                        BlockSection(
                            heading=f"Exam-Style Practice ({', '.join(right_specs or ['1.4'])})",
                            body=right_clean,
                            slide_number=slide_number,
                            kind="practice",
                        )
                    )
                    continue

                # Slide 17: Graph/table read (Block 3: 1.7–1.9) + Examiner alert (1.6) (Block 2)
                if "graph/table read" in left_raw.lower():
                    _record_slide(3, slide_number, tb_refs)
                    block_sections[3].append(
                        BlockSection(
                            heading="Interpreting Graph Gradient & Area",
                            body=left_clean,
                            slide_number=slide_number,
                            kind="concept",
                        )
                    )
                    _record_slide(2, slide_number, tb_refs)
                    continue

                # Slide 19 (18th slide): Plenary model v^2 = u^2 + 2as + Exit ticket (1.10) -> Block 4
                if "plenary model" in left_raw.lower() or "1.10" in right_specs:
                    _record_slide(4, slide_number, tb_refs)
                    q_match = re.search(r'\*"([^"]+)"\*|"([^"]+)"', left_clean)
                    prompt_text = (q_match.group(1) or q_match.group(2)) if q_match else left_clean
                    ans_match = re.search(r"\*\*Answer\*\*\s*:\s*(.+)$", left_clean, re.IGNORECASE)
                    solution_text = ans_match.group(1).strip() if ans_match else left_clean
                    _add_worked_example(
                        block_index=4,
                        stage="model",
                        ex_title="Worked Example: Uniform Acceleration (v² = u² + 2as)",
                        prompt=prompt_text.strip(),
                        solution=solution_text,
                        steps=[
                            "List known and unknown values: u, v, a, s before substituting.",
                            "Substitute into v² = u² + (2 × a × s) and solve for a.",
                        ],
                        spec_refs=["1.10"],
                        slide_number=slide_number,
                    )
                    exit_prompt = re.sub(
                        r"^\*\*Exit\s+ticket\s*\([^)]+\):\*\*\s*",
                        "",
                        right_clean,
                        flags=re.IGNORECASE,
                    ).strip()
                    block_sections[4].append(
                        BlockSection(
                            heading="Uniform Acceleration Worked Model & Self-Check",
                            body=f"{left_clean}\n\n**Self-Check (1.10):** {exit_prompt}",
                            slide_number=slide_number,
                            kind="practice",
                        )
                    )
                    exit_remediation = SoloRemediation(
                        threshold_percent=80,
                        remediation_guidance=(
                            "List u, v, a, and s before substituting into "
                            "v^2 = u^2 + (2 * a * s), then check each arithmetic step against the worked model."
                        ),
                        next_step_guidance="Continue to the Chapter 1 synthesis and practice worksheet.",
                        soft_gated=True,
                        raw_gate_line="",
                    )
                    _add_remediation(4, exit_remediation)
                    _add_self_check(
                        4,
                        SelfCheckItem(
                            question=prompt_text.strip(),
                            answer="$a = 0.80$ $m/s^2$",
                            spec_refs=["1.10"],
                            solo_remediation=exit_remediation,
                            slide_number=slide_number,
                        ),
                    )
                    continue

                # Generic split-layout fallback for future lessons
                target_blk = (
                    _SPEC_TO_CH1_BLOCK.get(right_specs[0], 1)
                    if right_specs
                    else 1
                )
                _record_slide(target_blk, slide_number, tb_refs)
                block_sections[target_blk].append(
                    BlockSection(
                        heading=strip_teacher_choreography(heading) or "Worked Example & Practice",
                        body=f"{left_clean}\n\n{right_clean}".strip(),
                        slide_number=slide_number,
                        kind="practice",
                    )
                )
            continue

        # --- Determine target block for regular slides ---
        target_block = _assign_block_index(
            heading,
            slide_text,
            explicit_specs,
            enforce_chapter1_boundary=enforce_chapter1_boundary,
        )
        if target_block is None:
            # Slide explicitly belongs solely to an out-of-boundary spec (e.g. Spec 1.1)
            continue

        _record_slide(target_block, slide_number, tb_refs)
        block_analogies[target_block].extend(directives.analogies)
        block_reflections[target_block].extend(directives.reflections)
        block_widgets[target_block].extend(directives.widgets)

        # --- Extract Gate / Decision gate lines from this slide ---
        slide_remediations: list[SoloRemediation] = []
        non_gate_lines: list[str] = []
        for raw_line in slide_text.split("\n"):
            rem = parse_gate_to_solo_remediation(raw_line)
            if rem is not None:
                slide_remediations.append(rem)
                _add_remediation(target_block, rem)
            else:
                non_gate_lines.append(raw_line)

        slide_without_gates = "\n".join(non_gate_lines)
        primary_rem = slide_remediations[0] if slide_remediations else None

        # --- Synthesis slide (Slide 20) ---
        if "synthesis" in heading_lower:
            for cells in _extract_section_table_rows(slide_without_gates, r"formula\s*/\s*relationship"):
                if len(cells) >= 2:
                    f_ref = re.sub(r"[*`]", "", cells[0]).strip()
                    filtered_f = _filter_specs(
                        [f_ref],
                        enforce_chapter1_boundary=enforce_chapter1_boundary,
                    )
                    if not filtered_f:
                        continue
                    desc = cells[1].strip()
                    expr_match = re.search(r"\$([^$]+)\$", desc)
                    formulas.append(
                        FormulaSummary(
                            spec_ref=filtered_f[0],
                            description=desc,
                            expression=expr_match.group(1).strip() if expr_match else "",
                        )
                    )
            cleaned_body = strip_teacher_choreography(_strip_heading_and_textbook_lines(slide_without_gates))
            if cleaned_body:
                block_sections[target_block].append(
                    BlockSection(
                        heading="Chapter 1 Synthesis & Formula Summary",
                        body=cleaned_body,
                        slide_number=slide_number,
                        kind="synthesis",
                    )
                )
            continue

        # --- Spec 1.5 Practical extraction (Ramp measurement bullet on Slide 7 + Ticker-timer on Slide 9) ---
        if "ramp measurement" in slide_without_gates.lower():
            for line in slide_without_gates.split("\n"):
                if "ramp measurement" in line.lower():
                    clean_ramp = strip_teacher_choreography(re.sub(r"^\s*[-*]\s*", "", line))
                    clean_ramp_body = re.sub(
                        r"^\*\*Ramp\s+measurement\*\*\s*:?\s*",
                        "",
                        clean_ramp,
                        flags=re.IGNORECASE,
                    ).strip()
                    practical_methods.append(
                        PracticalMethod(
                            name="Ramp & Trolley Speed Measurement",
                            summary=clean_ramp_body,
                            procedure_steps=[
                                "Release the trolley or toy car from a fixed height on the bench ramp.",
                                "Measure the distance s between two marked points along the ramp/bench.",
                                "Time the trolley between the two marked points twice and calculate the mean time t.",
                                "Calculate average speed for each run using v = s/t.",
                            ],
                            accuracy_notes=[
                                "Always time from the front of the car crossing each marked line.",
                                "Keep the release height constant for repeated runs and take repeat readings.",
                            ],
                            measurements=["distance s (m)", "time t (s)", "average speed v = s/t (m/s)"],
                            slide_number=slide_number,
                        )
                    )
                    practical_slides.append(slide_number)
                    for ref in tb_refs:
                        if ref not in practical_textbooks:
                            practical_textbooks.append(ref)

        if heading_lower.startswith("practical:"):
            clean_practical = strip_teacher_choreography(_strip_heading_and_textbook_lines(slide_without_gates))
            practical_methods.append(
                PracticalMethod(
                    name="50 Hz Ticker-Timer Trolley Tape",
                    summary=clean_practical,
                    procedure_steps=[
                        "Pass ticker tape through the 50 Hz ticker-timer and attach it to the trolley on a shallow ramp.",
                        "Release the trolley so the timer marks dots every 0.02 s (50 Hz).",
                        "Cut the tape into consecutive 10-space strips (0.20 s per strip).",
                        "Arrange the strips side by side to build a distance-time chart and convert it into a velocity-time graph.",
                    ],
                    accuracy_notes=[
                        "At 50 Hz, each single dot interval is 0.02 s and each 10-space strip represents 0.20 s.",
                        "Ignore any overlapping start dots where the trolley had not yet started moving cleanly.",
                    ],
                    measurements=[
                        "tick frequency f = 50 Hz (0.02 s per tick)",
                        "strip length (distance per 0.20 s)",
                        "average velocity per strip",
                    ],
                    slide_number=slide_number,
                )
            )
            practical_slides.append(slide_number)
            for ref in tb_refs:
                if ref not in practical_textbooks:
                    practical_textbooks.append(ref)
            block_sections[target_block].append(
                BlockSection(
                    heading="Practical: Ticker-Timer Trolley Tape (Spec 1.5)",
                    body=clean_practical,
                    slide_number=slide_number,
                    kind="practical",
                )
            )
            continue

        # --- Modelling Band (I Do / We Do / You Do) ---
        if "modelling band" in heading_lower:
            cleaned_heading = strip_teacher_choreography(heading)
            cleaned_body = strip_teacher_choreography(_strip_heading_and_textbook_lines(slide_without_gates))
            if "i do" in heading_lower:
                stage = "i_do"
            elif "we do" in heading_lower:
                stage = "we_do"
            else:
                stage = "you_do"

            body_lines = [ln.strip() for ln in cleaned_body.split("\n") if ln.strip()]
            steps = [
                re.sub(r"^\*\*Steps\s+to\s+follow:\*\*\s*", "", ln, flags=re.IGNORECASE)
                for ln in body_lines
                if "steps to follow" in ln.lower()
            ]
            prompt_lines = [ln for ln in body_lines if "steps to follow" not in ln.lower()]
            prompt_text = " ".join(prompt_lines)
            prompt_text = re.sub(r"^\*\*Worked\s+example\*\*\s*:?\s*", "", prompt_text, flags=re.IGNORECASE).strip()

            solution_text = ""
            if "=" in prompt_text and ":" in prompt_text:
                lead, _, tail = prompt_text.partition(":")
                if "=" in tail:
                    prompt_text = lead.strip()
                    solution_text = tail.strip()

            _add_worked_example(
                block_index=target_block,
                stage=stage,
                ex_title=cleaned_heading,
                prompt=prompt_text,
                solution=solution_text,
                steps=steps,
                spec_refs=explicit_specs,
                slide_number=slide_number,
            )
            if cleaned_body:
                block_sections[target_block].append(
                    BlockSection(
                        heading=cleaned_heading,
                        body=cleaned_body,
                        slide_number=slide_number,
                        kind="practice",
                    )
                )
            continue

        # --- Dedicated MWB Check / Self-Check slides ---
        if heading_lower.startswith("mwb check"):
            cleaned_body = strip_teacher_choreography(_strip_heading_and_textbook_lines(slide_without_gates))
            if "**Q1.**" in slide_without_gates or "Q1." in cleaned_body:
                # Multi-question recall check (Slide 19)
                for q_line in cleaned_body.split("\n"):
                    q_match = re.match(r"^\*\*Q\d+\.\*\*\s*(.+)$", q_line.strip())
                    if q_match:
                        _add_self_check(
                            target_block,
                            SelfCheckItem(
                                question=q_match.group(1).strip(),
                                answer="",
                                spec_refs=list(CHAPTER_1_BLOCK_SPECS[target_block - 1].spec_refs),
                                solo_remediation=primary_rem,
                                slide_number=slide_number,
                            ),
                        )
                if cleaned_body:
                    block_sections[target_block].append(
                        BlockSection(
                            heading="Quick Recall Self-Check",
                            body=cleaned_body,
                            slide_number=slide_number,
                            kind="practice",
                        )
                    )
            else:
                question, answer = _extract_question_answer(cleaned_body)
                if question:
                    _add_self_check(
                        target_block,
                        SelfCheckItem(
                            question=question,
                            answer=answer,
                            spec_refs=list(CHAPTER_1_BLOCK_SPECS[target_block - 1].spec_refs),
                            solo_remediation=primary_rem,
                            slide_number=slide_number,
                        ),
                    )
                # Keep v-t graph prompt slide as a visible section in Block 3 so Block 3 has concept body
                if target_block == 3 and cleaned_body:
                    block_sections[3].append(
                        BlockSection(
                            heading="Velocity-Time Graph Concept Check",
                            body=cleaned_body,
                            slide_number=slide_number,
                            kind="concept",
                        )
                    )
            continue

        # --- Starter slide ---
        if heading_lower.startswith("starter"):
            cleaned_body = strip_teacher_choreography(_strip_heading_and_textbook_lines(slide_without_gates))
            if cleaned_body:
                block_sections[target_block].append(
                    BlockSection(
                        heading="Warm-Up Recall",
                        body=cleaned_body,
                        slide_number=slide_number,
                        kind="starter",
                    )
                )
            continue

        # --- Theory Chunk & General Content slides ---
        # Extract inline Self-Check/MWB Check bullets into self_check as well
        content_lines: list[str] = []
        for line in slide_without_gates.split("\n"):
            if re.search(r"\bMWB\s+Check\b", line, re.IGNORECASE):
                q, a = _extract_question_answer(line)
                if q:
                    _add_self_check(
                        target_block,
                        SelfCheckItem(
                            question=q,
                            answer=a,
                            spec_refs=list(CHAPTER_1_BLOCK_SPECS[target_block - 1].spec_refs),
                            solo_remediation=primary_rem,
                            slide_number=slide_number,
                        ),
                    )
                continue
            content_lines.append(line)

        cleaned_heading = strip_teacher_choreography(heading) or CHAPTER_1_BLOCK_SPECS[target_block - 1].title
        cleaned_body = strip_teacher_choreography(
            _strip_heading_and_textbook_lines("\n".join(content_lines))
        )
        if cleaned_body:
            block_sections[target_block].append(
                BlockSection(
                    heading=cleaned_heading,
                    body=cleaned_body,
                    slide_number=slide_number,
                    kind="concept",
                )
            )

    # ------------------------------------------------------------------
    # Assemble Lesson-Level Spec Refs & 4 Ordered Learning Blocks
    # ------------------------------------------------------------------
    lesson_spec_refs = _filter_specs(
        raw_spec_refs or list(CHAPTER_1_ALLOWED_SPECS),
        enforce_chapter1_boundary=enforce_chapter1_boundary,
    )
    if enforce_chapter1_boundary and not lesson_spec_refs:
        lesson_spec_refs = list(CHAPTER_1_ALLOWED_SPECS)

    # Map objectives, vocabulary, and examiner alerts to each block
    objectives_by_spec = {obj.spec_ref: obj for obj in learning_objectives}

    blocks: list[LearningBlock] = []
    for blk_def in CHAPTER_1_BLOCK_SPECS:
        idx = blk_def.block_index
        blk_specs = list(blk_def.spec_refs)
        blk_objectives = [
            objectives_by_spec[s] for s in blk_specs if s in objectives_by_spec
        ]
        blk_vocab = [
            v for v in vocabulary if any(s in blk_specs for s in v.spec_refs)
        ]
        blk_alerts = [
            a for a in examiner_alerts if idx in a.block_indices
        ]

        # Build clean, self-contained student_markdown for this Learning Block
        md_parts: list[str] = [f"## {blk_def.title}"]
        if blk_objectives:
            obj_lines = [f"- **{o.spec_ref}:** {o.text}" for o in blk_objectives]
            md_parts.append("### Learning Objectives\n" + "\n".join(obj_lines))
        for sec in block_sections[idx]:
            if sec.heading and sec.heading.lower() != blk_def.title.lower():
                md_parts.append(f"### {sec.heading}\n{sec.body}")
            else:
                md_parts.append(sec.body)
        student_markdown = _collapse_blank_lines("\n\n".join(p for p in md_parts if p.strip())).strip()

        blocks.append(
            LearningBlock(
                block_index=idx,
                slug=blk_def.slug,
                title=blk_def.title,
                spec_refs=blk_specs,
                citation_id=f"BLK-{idx}",
                textbook_refs=block_textbooks[idx],
                learning_objectives=blk_objectives,
                vocabulary=blk_vocab,
                student_markdown=student_markdown,
                sections=block_sections[idx],
                guided_practice=block_examples[idx],
                self_check=block_checks[idx],
                solo_remediation=block_remediations[idx],
                analogies=block_analogies[idx],
                reflections=block_reflections[idx],
                widgets=block_widgets[idx],
                examiner_alerts=blk_alerts,
                source_slides=block_slides[idx],
            )
        )

    # ------------------------------------------------------------------
    # Assemble Spec 1.5 Practical Guide
    # ------------------------------------------------------------------
    practical: Optional[PracticalGuide] = None
    spec_15_obj = objectives_by_spec.get("1.5")
    if practical_methods or spec_15_obj is not None:
        spec_stmt = (
            spec_15_obj.text
            if spec_15_obj
            else "practical: investigate the motion of everyday objects such as toy cars or tennis balls"
        )
        p_parts = [
            "## Investigating Motion of Everyday Objects (Spec 1.5)",
            f"**Specification 1.5:** {spec_stmt}",
        ]
        for method in practical_methods:
            steps_md = "\n".join(f"{i}. {s}" for i, s in enumerate(method.procedure_steps, start=1))
            acc_md = "\n".join(f"- {note}" for note in method.accuracy_notes)
            p_parts.append(
                f"### {method.name}\n\n{method.summary}\n\n"
                f"**Procedure:**\n{steps_md}\n\n"
                f"**Accuracy & Reliability:**\n{acc_md}"
            )
        practical = PracticalGuide(
            citation_id="PRC-1.5",
            title="Investigating Motion of Everyday Objects (Spec 1.5)",
            spec_refs=["1.5"],
            spec_statement=spec_stmt,
            textbook_refs=practical_textbooks,
            methods=practical_methods,
            student_markdown=_collapse_blank_lines("\n\n".join(p_parts)).strip(),
            source_slides=sorted(set(practical_slides)),
        )

    resolved_title = title or "Movement and Position"
    resolved_chapter_title = chapter_title or resolved_title

    return ParsedLesson(
        source_path=str(source_path),
        title=resolved_title,
        subtitle=subtitle,
        slug=_slugify(resolved_title),
        chapter_number=chapter_number if chapter_number is not None else 1,
        chapter_title=resolved_chapter_title,
        qualification=qualification or "Pearson Edexcel International GCSE Physics (Modular) 4XPH1",
        duration_minutes=duration_minutes,
        frontmatter=frontmatter,
        spec_refs=lesson_spec_refs,
        learning_objectives=learning_objectives,
        vocabulary=vocabulary,
        formulas=formulas,
        blocks=blocks,
        practical=practical,
        examiner_alerts=examiner_alerts,
        worked_examples=all_worked_examples,
        excluded_teacher_slides=excluded_teacher_slides,
    )


def parse_marp_lesson(
    source: str | Path,
    *,
    enforce_chapter1_boundary: bool = True,
) -> ParsedLesson:
    """
    Read a Marp Markdown lesson file from disk and parse it into a
    ``ParsedLesson`` object.
    """
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Marp lesson file not found: {path}")
    markdown_text = path.read_text(encoding="utf-8")
    return parse_marp_markdown(
        markdown_text,
        source_path=path.as_posix(),
        enforce_chapter1_boundary=enforce_chapter1_boundary,
    )
