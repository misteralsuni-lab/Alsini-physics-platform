"""Unit tests for backend/pipeline/marp_parser.py (ADR-0001 & Issue #13)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure backend/ is importable whether pytest is invoked from repo root or backend/
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.marp_parser import (  # noqa: E402
    CHAPTER_1_ALLOWED_SPECS,
    CHAPTER_1_EXCLUDED_SPECS,
    ParsedLesson,
    extract_directives,
    parse_gate_to_solo_remediation,
    parse_marp_lesson,
    parse_marp_markdown,
    strip_teacher_choreography,
)

CANONICAL_CH1_SLIDES = (
    REPO_ROOT / "content" / "lessons" / "G9-T1-W1-movement-and-position-slides.md"
)

# Strict blacklist of classroom/teacher choreography & authoring-meta tokens
# that MUST NEVER leak into student-facing text.
FORBIDDEN_TEACHER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hands down", re.compile(r"\bhands\s+down\b", re.IGNORECASE)),
    ("boards up", re.compile(r"\bboards?\s+up\b", re.IGNORECASE)),
    ("scan the room", re.compile(r"\bscan\s+the\s+room\b", re.IGNORECASE)),
    ("show your boards", re.compile(r"\bshow\s+your\s+boards?\b", re.IGNORECASE)),
    ("hold up", re.compile(r"\bhold\s+up\b", re.IGNORECASE)),
    ("partner", re.compile(r"\bpartner\b", re.IGNORECASE)),
    ("paired work", re.compile(r"\bpaired\s+work\b", re.IGNORECASE)),
    ("paired practice", re.compile(r"\bpaired\s+practice\b", re.IGNORECASE)),
    ("pair-reteach", re.compile(r"\bpair[-\s]?reteach\b", re.IGNORECASE)),
    ("cold-call", re.compile(r"\bcold[-\s]call\b", re.IGNORECASE)),
    ("turn and talk", re.compile(r"\bturn\s+and\s+talk\b", re.IGNORECASE)),
    ("think-pair-share", re.compile(r"\bthink[-\s]pair[-\s]share\b", re.IGNORECASE)),
    ("teacher models", re.compile(r"\bteacher\s+models\b", re.IGNORECASE)),
    ("teacher prompting", re.compile(r"\bteacher\s+prompting\b", re.IGNORECASE)),
    ("no teacher help", re.compile(r"\bno\s+teacher\s+help\b", re.IGNORECASE)),
    ("narrating every step", re.compile(r"\bnarrating\s+every\s+step\b", re.IGNORECASE)),
    ("class completes together", re.compile(r"\bclass\s+completes\s+together\b", re.IGNORECASE)),
    ("class counts", re.compile(r"\bclass\s+counts\b", re.IGNORECASE)),
    ("on the board", re.compile(r"\bon\s+the\s+board\b", re.IGNORECASE)),
    ("on boards", re.compile(r"\bon\s+boards\b", re.IGNORECASE)),
    ("peer marking", re.compile(r"\bpeer\s+marking\b", re.IGNORECASE)),
    ("from the lesson plan", re.compile(r"\bfrom\s+the\s+lesson\s+plan\b", re.IGNORECASE)),
    ("exemplar", re.compile(r"\bexemplar\b", re.IGNORECASE)),
    ("MWB", re.compile(r"\bmwb\b", re.IGNORECASE)),
    ("re-teach", re.compile(r"\bre[-\s]?teach\b", re.IGNORECASE)),
    ("re-run triggers", re.compile(r"\bre-run\s+triggers\b", re.IGNORECASE)),
    ("sources consulted", re.compile(r"\bsources\s+consulted\b", re.IGNORECASE)),
    ("groups collect", re.compile(r"\bgroups\s+collect\b", re.IGNORECASE)),
    ("demonstrate the", re.compile(r"\bdemonstrate\s+the\b", re.IGNORECASE)),
    ("require the", re.compile(r"\brequire\s+the\b", re.IGNORECASE)),
    ("raw Gate:", re.compile(r"(?:^|\n)\s*(?:[-*]\s+)?(?:\*\*)?(?:Decision\s+)?Gate(?:\*\*)?\s*:", re.IGNORECASE)),
    ("raw HTML comment", re.compile(r"<!--|-->")),
)


def _collect_all_student_facing_text(lesson: ParsedLesson) -> str:
    """Gather every student-facing string across blocks, practical, examples, and checks."""
    parts: list[str] = []
    for block in lesson.blocks:
        parts.append(block.title)
        parts.append(block.student_markdown)
        for sec in block.sections:
            parts.append(sec.heading)
            parts.append(sec.body)
        for ex in block.guided_practice:
            parts.extend([ex.title, ex.prompt, ex.solution, *ex.steps])
        for sc in block.self_check:
            parts.extend([sc.question, sc.answer])
            if sc.solo_remediation:
                parts.extend(
                    [
                        sc.solo_remediation.remediation_guidance,
                        sc.solo_remediation.next_step_guidance,
                    ]
                )
        for rem in block.solo_remediation:
            parts.extend([rem.remediation_guidance, rem.next_step_guidance])
        parts.extend(block.analogies)
        parts.extend(block.reflections)
    if lesson.practical:
        parts.append(lesson.practical.title)
        parts.append(lesson.practical.student_markdown)
        for method in lesson.practical.methods:
            parts.extend(
                [
                    method.name,
                    method.summary,
                    *method.procedure_steps,
                    *method.accuracy_notes,
                ]
            )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 1. Canonical Chapter 1 Lesson File Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ch1_lesson() -> ParsedLesson:
    assert CANONICAL_CH1_SLIDES.is_file(), f"Missing canonical lesson: {CANONICAL_CH1_SLIDES}"
    return parse_marp_lesson(CANONICAL_CH1_SLIDES)


def test_ch1_frontmatter_and_metadata(ch1_lesson: ParsedLesson) -> None:
    assert ch1_lesson.frontmatter["marp"] is True
    assert ch1_lesson.frontmatter["theme"] == "default"
    assert ch1_lesson.frontmatter["paginate"] is True
    assert ch1_lesson.frontmatter["size"] == "16:9"
    assert "Alsini" in ch1_lesson.frontmatter["header"]
    assert "4XPH1" in ch1_lesson.frontmatter["footer"]

    assert ch1_lesson.title == "Movement and Position"
    assert ch1_lesson.slug == "movement-and-position"
    assert ch1_lesson.chapter_number == 1
    assert ch1_lesson.duration_minutes == 60
    assert "4XPH1" in ch1_lesson.qualification


def test_ch1_curriculum_boundary_and_four_blocks(ch1_lesson: ParsedLesson) -> None:
    assert tuple(ch1_lesson.spec_refs) == CHAPTER_1_ALLOWED_SPECS
    for excluded in CHAPTER_1_EXCLUDED_SPECS:
        assert excluded not in ch1_lesson.spec_refs

    assert len(ch1_lesson.learning_objectives) == 8
    obj_refs = [o.spec_ref for o in ch1_lesson.learning_objectives]
    assert obj_refs == ["1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]
    assert "1.1" not in obj_refs

    assert len(ch1_lesson.blocks) == 4
    expected_specs = [
        ["1.3", "1.4"],
        ["1.5", "1.6"],
        ["1.7", "1.8", "1.9"],
        ["1.10"],
    ]
    for idx, (block, specs) in enumerate(zip(ch1_lesson.blocks, expected_specs), start=1):
        assert block.block_index == idx
        assert block.citation_id == f"BLK-{idx}"
        assert block.spec_refs == specs
        assert "1.1" not in block.spec_refs
        assert block.student_markdown.strip() != ""
        assert len(block.learning_objectives) == len(specs)
        assert len(block.sections) >= 1


def test_ch1_zero_leaked_teacher_choreography(ch1_lesson: ParsedLesson) -> None:
    student_text = _collect_all_student_facing_text(ch1_lesson)
    leaks: list[str] = []
    for label, pattern in FORBIDDEN_TEACHER_PATTERNS:
        match = pattern.search(student_text)
        if match:
            start = max(0, match.start() - 30)
            end = min(len(student_text), match.end() + 30)
            leaks.append(f"{label}: {student_text[start:end]!r}")
    assert not leaks, "Teacher choreography cues leaked into student copy:\n" + "\n".join(leaks)


def test_ch1_gate_lines_converted_to_solo_remediation(ch1_lesson: ParsedLesson) -> None:
    # Block 1: gradient reading gate
    b1 = ch1_lesson.blocks[0]
    assert len(b1.solo_remediation) >= 1
    assert b1.solo_remediation[0].threshold_percent == 80
    assert b1.solo_remediation[0].soft_gated is True
    assert "gradient reading" in b1.solo_remediation[0].remediation_guidance.lower()
    assert len(b1.self_check) >= 1
    assert any("4.5 m" in sc.question and "1.5" in sc.answer for sc in b1.self_check)

    # Block 2: formula triangle gate (pair-reteach converted to solo)
    b2 = ch1_lesson.blocks[1]
    assert len(b2.solo_remediation) >= 1
    assert b2.solo_remediation[0].threshold_percent == 80
    assert b2.solo_remediation[0].soft_gated is True
    assert "formula triangle" in b2.solo_remediation[0].remediation_guidance.lower()
    assert "pair" not in b2.solo_remediation[0].remediation_guidance.lower()
    assert any("6.0 m/s" in sc.question and "2.0" in sc.answer for sc in b2.self_check)

    # Block 3: v-t graph re-draw gate
    b3 = ch1_lesson.blocks[2]
    assert len(b3.solo_remediation) >= 1
    assert b3.solo_remediation[0].threshold_percent == 80
    assert b3.solo_remediation[0].soft_gated is True
    assert "re-draw both graph types" in b3.solo_remediation[0].remediation_guidance.lower()
    assert any("v-t graph" in sc.question.lower() for sc in b3.self_check)

    # Block 4: uniform acceleration self-check + solo remediation
    b4 = ch1_lesson.blocks[3]
    assert len(b4.solo_remediation) >= 1
    assert b4.solo_remediation[0].soft_gated is True
    assert len(b4.self_check) >= 1


def test_ch1_guided_practice_worked_examples(ch1_lesson: ParsedLesson) -> None:
    assert len(ch1_lesson.worked_examples) >= 5
    stages = {we.stage for we in ch1_lesson.worked_examples}
    assert {"i_do", "we_do", "you_do", "model"}.issubset(stages)
    assert all(we.example_id.startswith("WE-") for we in ch1_lesson.worked_examples)

    # Block 1 has runner 100 m / 12.5 s = 8.0 m/s worked example
    b1_examples = " ".join(
        f"{we.prompt} {we.solution}" for we in ch1_lesson.blocks[0].guided_practice
    )
    assert "100" in b1_examples and "12.5" in b1_examples and "8.0" in b1_examples

    # Block 4 has cyclist uniform acceleration worked example (a = 0.80 m/s^2)
    b4_examples = " ".join(
        f"{we.prompt} {we.solution}" for we in ch1_lesson.blocks[3].guided_practice
    )
    assert "80 m" in b4_examples and "0.80" in b4_examples


def test_ch1_all_three_verbatim_examiner_alerts(ch1_lesson: ParsedLesson) -> None:
    assert len(ch1_lesson.examiner_alerts) == 3
    by_session_q = {
        (a.exam_session, a.question_ref): a for a in ch1_lesson.examiner_alerts
    }

    # 1. June 2019 Q10 (Spec 1.6 -> Block 2)
    june = by_session_q[("June 2019", "Q10")]
    assert june.alert_id.startswith("EXM-")
    assert june.paper_code == "4PH1/1PR"
    assert june.spec_refs == ["1.6"]
    assert june.block_indices == [2]
    assert june.verbatim_text == (
        "About a third of candidates scored no marks, yet could have scored something "
        "by stating the correct formula relating acceleration, change in velocity and "
        "time taken and substituting in the given values."
    )

    # 2. January 2020 Q5 (Spec 1.7 / 1.8 -> Block 3)
    jan = by_session_q[("January 2020", "Q5")]
    assert jan.paper_code == "4PH1/1P"
    assert jan.spec_refs == ["1.7", "1.8"]
    assert jan.block_indices == [3]
    assert jan.verbatim_text == (
        "Students found the velocity-time graph plot in Q5(b) challenging and more "
        "than half failed to score at all."
    )

    # 3. October 2020 Q11 (Spec 1.10 -> Block 4)
    oct_alert = by_session_q[("October 2020", "Q11")]
    assert oct_alert.paper_code == "4PH1/1PR"
    assert oct_alert.spec_refs == ["1.10"]
    assert oct_alert.block_indices == [4]
    assert oct_alert.verbatim_text == (
        "If the candidate recognised the need to use a formula to link distance, "
        "initial speed, final speed and acceleration, then the following calculation "
        "usually went well."
    )

    # Alerts are also attached to their matching Learning Blocks
    assert len(ch1_lesson.blocks[1].examiner_alerts) == 1
    assert len(ch1_lesson.blocks[2].examiner_alerts) == 1
    assert len(ch1_lesson.blocks[3].examiner_alerts) == 1


def test_ch1_spec_1_5_practical_guide(ch1_lesson: ParsedLesson) -> None:
    practical = ch1_lesson.practical
    assert practical is not None
    assert practical.citation_id == "PRC-1.5"
    assert practical.spec_refs == ["1.5"]
    assert "toy cars or tennis balls" in practical.spec_statement
    assert len(practical.methods) == 2

    method_names = [m.name.lower() for m in practical.methods]
    assert any("ramp" in name for name in method_names)
    assert any("ticker-timer" in name for name in method_names)

    md_lower = practical.student_markdown.lower()
    assert "front" in md_lower and "car" in md_lower
    assert "50 hz" in md_lower
    assert "10-space" in md_lower
    assert "0.20" in md_lower
    assert "0.02" in md_lower


def test_ch1_json_serializable_dict(ch1_lesson: ParsedLesson) -> None:
    payload = ch1_lesson.to_dict()
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["title"] == "Movement and Position"
    assert len(decoded["blocks"]) == 4
    assert len(decoded["examiner_alerts"]) == 3
    assert decoded["practical"]["citation_id"] == "PRC-1.5"


# ---------------------------------------------------------------------------
# 2. Synthetic Tests — HTML Comment Directives (ADR-0001)
# ---------------------------------------------------------------------------


def test_synthetic_all_four_html_comment_directives() -> None:
    md = """---
marp: true
theme: default
---

# Movement and Position
## IGCSE Physics — Ch. 1
**Duration:** 45 min | **Spec:** Pearson Edexcel 4XPH1 objectives 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10

---

<!-- teacher-only -->
# Teacher Pacing & Lab Prep Notes
Secret teacher script: cold-call table 3 and hand out stopwatches.

---

# Theory Chunk 1 — Distance-time graphs and average speed (1.3, 1.4)

A horizontal line on a distance-time graph means the object is stationary.

<!-- student:analogy Think of the gradient of a distance-time graph like the steepness of a mountain trail: steeper means faster. -->

<!-- student:analogy -->
Average speed is like your overall trip speed on a highway, even if you slow down at toll booths.
<!-- /student:analogy -->

<!-- student:reflection In one sentence, how can you tell from a d-t graph when a cyclist stops moving? -->

<!-- student:reflection -->
Which step in v = s/t trips you up most often?
<!-- /student:reflection -->

<!-- widget:InteractiveKinematicsGraph mode="synced" specs="1.3,1.4" interactive=true -->
<!-- widget:FormulaCard {"formula_ref": "average_speed", "unit": "m/s"} -->

<!-- teacher-only -->
Differentiation prompt for teacher only: scaffold lower-attaining pairs with printed axes.
<!-- /teacher-only -->

<!-- teacher-only: Remind TA to check mini-whiteboard pens before lesson. -->

---

# Theory Chunk 2 — Motion practical and acceleration (1.5, 1.6)

Acceleration is the rate of change of velocity: $a = (v - u)/t$.

<!-- widget:Spec15MotionLab -->

<!-- teacher-only -->
Trailing teacher-only section that must not appear in Block 2 student output.
"""

    lesson = parse_marp_markdown(md, source_path="synthetic.md")

    # Slide 2 (entirely teacher-only) is excluded and tracked
    assert 2 in lesson.excluded_teacher_slides

    b1 = lesson.blocks[0]
    b2 = lesson.blocks[1]

    # student:analogy (both inline and paired)
    assert len(b1.analogies) == 2
    assert "mountain trail" in b1.analogies[0]
    assert "highway" in b1.analogies[1]

    # student:reflection (both inline and paired)
    assert len(b1.reflections) == 2
    assert "cyclist stops moving" in b1.reflections[0]
    assert "v = s/t" in b1.reflections[1]

    # widget:... (key=value, JSON, and bare widget name)
    assert len(b1.widgets) == 2
    assert b1.widgets[0].widget_type == "InteractiveKinematicsGraph"
    assert b1.widgets[0].config == {
        "mode": "synced",
        "specs": "1.3,1.4",
        "interactive": True,
    }
    assert b1.widgets[1].widget_type == "FormulaCard"
    assert b1.widgets[1].config == {"formula_ref": "average_speed", "unit": "m/s"}

    assert len(b2.widgets) == 1
    assert b2.widgets[0].widget_type == "Spec15MotionLab"
    assert b2.widgets[0].config == {}

    # teacher-only content MUST NEVER appear in student copy (all 4 forms)
    all_student = _collect_all_student_facing_text(lesson)
    assert "Secret teacher script" not in all_student
    assert "Differentiation prompt for teacher only" not in all_student
    assert "Remind TA" not in all_student
    assert "Trailing teacher-only section" not in all_student
    assert "<!--" not in all_student
    assert "-->" not in all_student

    # Genuine student content on slides with partial teacher-only blocks is preserved
    assert "stationary" in b1.student_markdown
    assert "rate of change of velocity" in b2.student_markdown


def test_synthetic_spec_1_1_strictly_excluded_from_ch1() -> None:
    md = """---
marp: true
---

# Movement and Position
## IGCSE Physics — Ch. 1
**Spec:** Pearson Edexcel 4XPH1 objectives 1.1, 1.3, 1.4

---

# Learning Objectives

| Ref | Spec text |
|---|---|
| **1.1** | use the following units: kilogram (kg), metre (m), metre/second (m/s), second (s) |
| **1.3** | plot and explain distance-time graphs |
| **1.4** | know and use average speed: $v = s/t$ |

---

# Legacy Units Intro (1.1)

This legacy 1.1 units slide must be excluded from Chapter 1 Block 1.

---

# Theory Chunk 1 — Distance-time graphs (1.1, 1.3, 1.4)

Gradient of a distance-time graph gives speed.
"""

    lesson = parse_marp_markdown(md, enforce_chapter1_boundary=True)
    assert "1.1" not in lesson.spec_refs
    assert all(obj.spec_ref != "1.1" for obj in lesson.learning_objectives)
    assert all("1.1" not in blk.spec_refs for blk in lesson.blocks)

    b1_text = lesson.blocks[0].student_markdown
    assert "legacy 1.1 units slide" not in b1_text.lower()
    assert "Gradient of a distance-time graph gives speed" in b1_text


def test_strip_teacher_choreography_and_gate_conversion_helpers() -> None:
    dirty = (
        "### Show your boards — quick check\n"
        "Turn and talk with your partner about velocity.\n"
        "Cold-call a student to define acceleration.\n"
        "Think-pair-share before writing.\n"
        "*Hands down, boards up — scan the room.*\n"
        "Average speed equals total distance divided by total time."
    )
    cleaned = strip_teacher_choreography(dirty)
    assert "Average speed equals total distance divided by total time." in cleaned
    for cue in ("hands down", "boards up", "scan the room", "cold-call", "turn and talk", "think-pair-share", "show your boards"):
        assert cue not in cleaned.lower()

    rem = parse_gate_to_solo_remediation(
        "**Gate:** <75% correct -> pair-reteach graph gradients; >=75% -> Chunk 3."
    )
    assert rem is not None
    assert rem.threshold_percent == 75
    assert rem.soft_gated is True
    assert "pair" not in rem.remediation_guidance.lower()
    assert "re-teach" not in rem.remediation_guidance.lower()
    assert "graph gradients" in rem.remediation_guidance.lower()
    assert "Block 3" in rem.next_step_guidance


def test_fenced_code_and_comment_delimiters_do_not_split_slides() -> None:
    md = """---
marp: true
---

# Theory Chunk 1 — Distance-time graphs (1.3, 1.4)

```markdown
---
not a slide break
---
```

<!-- student:analogy
Line one
---
Line two
-->

Real paragraph stays in Block 1.
"""
    lesson = parse_marp_markdown(md)
    b1 = lesson.blocks[0]
    assert "Real paragraph stays in Block 1." in b1.student_markdown
    assert len(b1.analogies) == 1
    assert "Line one" in b1.analogies[0] and "Line two" in b1.analogies[0]


def test_extract_directives_teacher_only_slide_with_heading_only() -> None:
    res = extract_directives("# Teacher Notes\n<!-- teacher-only -->\nInternal notes.", slide_number=5)
    assert res.is_teacher_only_slide is True
    assert res.cleaned_text == ""


def test_parse_marp_lesson_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        parse_marp_lesson(REPO_ROOT / "content" / "lessons" / "does-not-exist.md")
