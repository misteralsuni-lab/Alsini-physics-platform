"""
Unit tests for `backend/pipeline/chapter1_unified_ingestion.py`.

Validates:
  - Chunk generation across all 4 Learning Blocks (`1.3–1.4`, `1.5–1.6`, `1.7–1.9`, `1.10`),
    Worked Examples (`WE-` anchors), Spec 1.5 Practical Guide (`PRC-1.5`), and all 3
    verbatim Edexcel Examiner Alerts (`June 2019 Q10`, `Jan 2020 Q5`, `Oct 2020 Q11`).
  - Strict `embedding_model = 'nvidia/nemotron-3.5-embed-1b'` tagging & `1024`-dim validation.
  - Exclusion of Spec `1.1` (`5729d034-a6c7-4f35-b81c-fcac447289c7`) from Block 1 and chunks.
  - 100% idempotent re-run behavior against an in-memory PostgREST fake.
  - Complete preservation of all 21 pre-existing Chapter 1 `worksheet` chunks.
  - CLI `--dry-run` and `--source` execution without live Supabase/NVIDIA calls.
  - Dynamic import resolution of `pipeline.marp_parser.parse_marp_lesson`.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import types
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import pytest

# Ensure `backend/` is importable whether pytest runs from repo root or `backend/`.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from pipeline import chapter1_unified_ingestion as ing


@pytest.fixture(autouse=True)
def _clean_embed_model_env(monkeypatch):
    """Ensure host NVIDIA_EMBED_MODEL env vars do not affect deterministic unit tests."""
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)


# ---------------------------------------------------------------------------
# Contract-Exact Marp Parser Fixture Models (matching marp-parser contract)
# ---------------------------------------------------------------------------

@dataclass
class _ContractModel:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearningObjective(_ContractModel):
    spec_ref: str
    text: str


@dataclass
class VocabularyItem(_ContractModel):
    term: str
    definition: str
    spec_refs: list[str] = field(default_factory=list)


@dataclass
class FormulaSummary(_ContractModel):
    spec_ref: str
    description: str
    expression: str


@dataclass
class BlockSection(_ContractModel):
    heading: str
    body: str
    slide_number: int
    kind: str


@dataclass
class SoloRemediation(_ContractModel):
    threshold_percent: int
    remediation_guidance: str
    next_step_guidance: str
    soft_gated: bool
    raw_gate_line: str


@dataclass
class SelfCheckItem(_ContractModel):
    question: str
    answer: str
    spec_refs: list[str]
    solo_remediation: Optional[SoloRemediation]
    slide_number: int


@dataclass
class WorkedExample(_ContractModel):
    example_id: str
    stage: str
    title: str
    prompt: str
    solution: str
    steps: list[str]
    spec_refs: list[str]
    block_index: int
    slide_number: int


@dataclass
class WidgetDirective(_ContractModel):
    widget_type: str
    config: dict[str, Any]
    raw: str
    slide_number: int


@dataclass
class ExaminerAlert(_ContractModel):
    alert_id: str
    spec_refs: list[str]
    paper_code: str
    exam_session: str
    question_ref: str
    source_citation: str
    verbatim_text: str
    block_indices: list[int]


@dataclass
class PracticalMethod(_ContractModel):
    name: str
    summary: str
    procedure_steps: list[str]
    accuracy_notes: list[str]
    measurements: list[str]
    slide_number: int


@dataclass
class PracticalGuide(_ContractModel):
    citation_id: str
    title: str
    spec_refs: list[str]
    spec_statement: str
    textbook_refs: list[str]
    methods: list[PracticalMethod]
    student_markdown: str
    source_slides: list[int]


@dataclass
class LearningBlock(_ContractModel):
    block_index: int
    slug: str
    title: str
    spec_refs: list[str]
    citation_id: str
    textbook_refs: list[str]
    learning_objectives: list[LearningObjective]
    vocabulary: list[VocabularyItem]
    student_markdown: str
    sections: list[BlockSection]
    guided_practice: list[WorkedExample]
    self_check: list[SelfCheckItem]
    solo_remediation: list[SoloRemediation]
    analogies: list[str]
    reflections: list[str]
    widgets: list[WidgetDirective]
    examiner_alerts: list[ExaminerAlert]
    source_slides: list[int]


@dataclass
class ParsedLesson(_ContractModel):
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
    excluded_teacher_slides: list[int]


# Exact verbatim Examiner Report alerts from content/lessons/G9-T1-W1-movement-and-position-slides.md
VERBATIM_ALERT_JUNE_2019 = (
    "About a third of candidates scored no marks, yet could have scored something by "
    "stating the correct formula relating acceleration, change in velocity and time "
    "taken and substituting in the given values."
)
VERBATIM_ALERT_JAN_2020 = (
    "Students found the velocity-time graph plot in Q5(b) challenging and more than "
    "half failed to score at all."
)
VERBATIM_ALERT_OCT_2020 = (
    "If the candidate recognised the need to use a formula to link distance, initial "
    "speed, final speed and acceleration, then the following calculation usually went well."
)


def make_canonical_chapter1_lesson() -> ParsedLesson:
    """Build a canonical Chapter 1 ParsedLesson matching the Marp deck & parser contract."""
    alerts = [
        ExaminerAlert(
            alert_id="EXM-1",
            spec_refs=["1.6"],
            paper_code="4PH1/1PR",
            exam_session="June 2019",
            question_ref="Q10",
            source_citation="4PH1/1PR June 2019 Examiner Report, Q10",
            verbatim_text=VERBATIM_ALERT_JUNE_2019,
            block_indices=[2],
        ),
        ExaminerAlert(
            alert_id="EXM-2",
            spec_refs=["1.7", "1.8"],
            paper_code="4PH1/1P",
            exam_session="January 2020",
            question_ref="Q5",
            source_citation="4PH1/1P January 2020 Examiner Report, Q5",
            verbatim_text=VERBATIM_ALERT_JAN_2020,
            block_indices=[3],
        ),
        ExaminerAlert(
            alert_id="EXM-3",
            spec_refs=["1.10"],
            paper_code="4PH1/1PR",
            exam_session="October 2020",
            question_ref="Q11",
            source_citation="4PH1/1PR October 2020 Examiner Report, Q11",
            verbatim_text=VERBATIM_ALERT_OCT_2020,
            block_indices=[4],
        ),
    ]

    we_1 = WorkedExample(
        example_id="WE-1",
        stage="i_do",
        title="Average speed calculation for a 100 m runner",
        prompt="A runner covers 100 m in 12.5 s. Calculate the average speed.",
        solution="v = s / t = 100 / 12.5 = 8.0 m/s",
        steps=["Identify distance s = 100 m and time t = 12.5 s", "Substitute into v = s / t"],
        spec_refs=["1.3", "1.4"],
        block_index=1,
        slide_number=10,
    )
    we_2 = WorkedExample(
        example_id="WE-2",
        stage="we_do",
        title="Distance-time graph gradient",
        prompt="Read two points off a distance-time graph and compute the gradient with units.",
        solution="gradient = delta_s / delta_t (m/s)",
        steps=["List givens before substituting", "Carry units through every line"],
        spec_refs=["1.3", "1.4"],
        block_index=1,
        slide_number=11,
    )
    we_3 = WorkedExample(
        example_id="WE-3",
        stage="you_do",
        title="Rearranging acceleration for time",
        prompt="Calculate acceleration and rearrange a = (v - u) / t for time t.",
        solution="t = (v - u) / a",
        steps=["List u, v, a, t", "Rearrange before substituting"],
        spec_refs=["1.6"],
        block_index=2,
        slide_number=13,
    )
    we_4 = WorkedExample(
        example_id="WE-4",
        stage="model",
        title="Uniform acceleration cyclist problem",
        prompt=(
            "A cyclist accelerates uniformly from 4.0 m/s to 12.0 m/s over a distance of 80 m. "
            "Calculate her acceleration."
        ),
        solution="v^2 = u^2 + (2 * a * s) -> 144 = 16 + 160a, so a = 0.80 m/s^2",
        steps=["List u = 4.0 m/s, v = 12.0 m/s, s = 80 m, a = ?", "Substitute into v^2 = u^2 + 2as"],
        spec_refs=["1.10"],
        block_index=4,
        slide_number=19,
    )

    rem_1 = SoloRemediation(
        threshold_percent=80,
        remediation_guidance="Review how to read the gradient of a distance-time graph with a second example.",
        next_step_guidance="Proceed to Block 2.",
        soft_gated=True,
        raw_gate_line="**Gate:** <80% correct -> re-teach gradient reading with a second graph; >=80% -> Chunk 2.",
    )
    rem_2 = SoloRemediation(
        threshold_percent=80,
        remediation_guidance="Revisit the formula triangle for a = (v - u) / t before moving on.",
        next_step_guidance="Proceed to Block 3.",
        soft_gated=True,
        raw_gate_line="**Gate:** <80% -> pair-reteach using the formula triangle; >=80% -> Chunk 3.",
    )
    rem_3 = SoloRemediation(
        threshold_percent=80,
        remediation_guidance="Compare distance-time and velocity-time graph features side by side.",
        next_step_guidance="Proceed to Block 4.",
        soft_gated=True,
        raw_gate_line="**Gate:** <80% -> re-draw both graph types side by side and re-label; >=80% -> Plenary.",
    )

    blocks = [
        LearningBlock(
            block_index=1,
            slug="distance-time-graphs-and-average-speed",
            title="Distance-time graphs and average speed",
            spec_refs=["1.3", "1.4"],
            citation_id="BLK-1",
            textbook_refs=["ch. 1, pp. 5–8"],
            learning_objectives=[
                LearningObjective("1.3", "plot and explain distance-time graphs"),
                LearningObjective("1.4", "know and use the relationship between average speed, distance moved and time taken: v = s/t"),
            ],
            vocabulary=[
                VocabularyItem("Average speed, v", "Distance moved divided by time taken: v = s/t; unit m/s. A scalar.", ["1.4"]),
                VocabularyItem("Gradient", "Steepness of a graph: distance-time gradient = speed.", ["1.3"]),
            ],
            student_markdown="Sketch four d-t story shapes (rest, constant speed, speeding up, returning) and interpret gradient.",
            sections=[BlockSection("Distance-time graphs", "Gradient equals speed.", 5, "theory")],
            guided_practice=[we_1, we_2],
            self_check=[
                SelfCheckItem(
                    question="A toy car moves 4.5 m in 3.0 s at steady speed. Write its average speed.",
                    answer="1.5 m/s",
                    spec_refs=["1.4"],
                    solo_remediation=rem_1,
                    slide_number=6,
                )
            ],
            solo_remediation=[rem_1],
            analogies=["Think of a steeper hill on a d-t graph as a faster runner."],
            reflections=["What does a horizontal line on a distance-time graph tell you?"],
            widgets=[WidgetDirective("kinematics-graph", {"mode": "d-t"}, "<!-- widget:kinematics-graph -->", 5)],
            examiner_alerts=[],
            source_slides=[5, 6, 10, 11, 15],
        ),
        LearningBlock(
            block_index=2,
            slug="motion-practical-and-acceleration",
            title="Motion practical and acceleration",
            spec_refs=["1.5", "1.6"],
            citation_id="BLK-2",
            textbook_refs=["ch. 1, pp. 9–12"],
            learning_objectives=[
                LearningObjective("1.5", "practical: investigate the motion of everyday objects such as toy cars or tennis balls"),
                LearningObjective("1.6", "know and use the relationship between acceleration, change in velocity and time taken: a = (v - u)/t"),
            ],
            vocabulary=[
                VocabularyItem("Acceleration, a", "Change in velocity divided by time taken: a = (v - u)/t; unit m/s^2.", ["1.6"]),
            ],
            student_markdown="Investigate trolley motion down a ramp timing from the front of the car, and compute acceleration a = (v - u)/t.",
            sections=[BlockSection("Acceleration", "Rate of change of velocity.", 7, "theory")],
            guided_practice=[we_3],
            self_check=[
                SelfCheckItem(
                    question="A ball rolling down a slope gains speed from 1.0 m/s to 6.0 m/s in 2.5 s. Write its acceleration.",
                    answer="2.0 m/s^2",
                    spec_refs=["1.6"],
                    solo_remediation=rem_2,
                    slide_number=8,
                )
            ],
            solo_remediation=[rem_2],
            analogies=[],
            reflections=["Why must we time from the front of the car crossing each mark?"],
            widgets=[],
            examiner_alerts=[alerts[0]],
            source_slides=[7, 8, 9, 13, 17],
        ),
        LearningBlock(
            block_index=3,
            slug="velocity-time-graphs-gradient-and-area",
            title="Velocity-time graphs: gradient and area",
            spec_refs=["1.7", "1.8", "1.9"],
            citation_id="BLK-3",
            textbook_refs=["ch. 1, pp. 13–17"],
            learning_objectives=[
                LearningObjective("1.7", "plot and explain velocity-time graphs"),
                LearningObjective("1.8", "determine acceleration from the gradient of a velocity-time graph"),
                LearningObjective("1.9", "determine the distance travelled from the area between a velocity-time graph and the time axis"),
            ],
            vocabulary=[
                VocabularyItem("Area under a v-t graph", "The distance travelled between the curve and the time axis.", ["1.9"]),
            ],
            student_markdown="On a velocity-time graph, the gradient gives acceleration and the area under the graph gives distance travelled.",
            sections=[BlockSection("Velocity-time graphs", "Gradient = acceleration, Area = distance.", 14, "theory")],
            guided_practice=[],
            self_check=[
                SelfCheckItem(
                    question="Sketch a v-t graph for a cyclist who speeds up steadily then cruises. Mark acceleration and distance.",
                    answer="Sloping line then horizontal line; gradient is acceleration; area is distance.",
                    spec_refs=["1.7", "1.8", "1.9"],
                    solo_remediation=rem_3,
                    slide_number=14,
                )
            ],
            solo_remediation=[rem_3],
            analogies=[],
            reflections=["How do you tell acceleration apart from distance on a v-t graph?"],
            widgets=[],
            examiner_alerts=[alerts[1]],
            source_slides=[14, 17],
        ),
        LearningBlock(
            block_index=4,
            slug="uniform-acceleration-equation",
            title="Uniform acceleration equation",
            spec_refs=["1.10"],
            citation_id="BLK-4",
            textbook_refs=["ch. 1, pp. 13–17"],
            learning_objectives=[
                LearningObjective("1.10", "use the relationship between final speed, initial speed, acceleration and distance moved: v^2 = u^2 + (2 * a * s)"),
            ],
            vocabulary=[
                VocabularyItem("Uniform acceleration", "Constant acceleration — the condition in which v^2 = u^2 + (2 * a * s) applies.", ["1.10"]),
            ],
            student_markdown="Apply v^2 = u^2 + (2 * a * s) when acceleration is uniform and time is not given. Always list u, v, a, s first.",
            sections=[BlockSection("Uniform acceleration", "List u, v, a, s before substituting.", 19, "theory")],
            guided_practice=[we_4],
            self_check=[],
            solo_remediation=[],
            analogies=[],
            reflections=["When should you choose v^2 = u^2 + 2as instead of a = (v - u)/t?"],
            widgets=[],
            examiner_alerts=[alerts[2]],
            source_slides=[19, 20],
        ),
    ]

    practical = PracticalGuide(
        citation_id="PRC-1.5",
        title="Spec 1.5 Practical: Investigate the Motion of Everyday Objects",
        spec_refs=["1.5"],
        spec_statement="practical: investigate the motion of everyday objects such as toy cars or tennis balls",
        textbook_refs=["ch. 1, pp. 9–12"],
        methods=[
            PracticalMethod(
                name="Ramp & Toy Car / Trolley Measurement",
                summary="Release a trolley or toy car from a fixed height on a bench ramp and measure time between two marked points twice.",
                procedure_steps=[
                    "Release trolley from a fixed height on the bench ramp.",
                    "Measure time between two marked points at least twice.",
                    "Compute average speed v = s/t for each run.",
                ],
                accuracy_notes=[
                    "Always time from the front of the car crossing each mark.",
                    "Repeat runs and discard anomalies to reduce reaction-time error.",
                ],
                measurements=["distance s (m)", "time t (s)", "average speed v (m/s)"],
                slide_number=7,
            ),
            PracticalMethod(
                name="50 Hz Ticker-Timer Trolley Tape",
                summary="Attach paper tape through a 50 Hz ticker-timer to a trolley running down a shallow ramp.",
                procedure_steps=[
                    "Thread tape through the 50 Hz ticker-timer and attach to trolley.",
                    "Cut tape into 10-space strips (0.02 s per dot space; 0.20 s per 10-space strip).",
                    "Build a distance-time chart and convert to a velocity-time bar chart.",
                ],
                accuracy_notes=["Verify 50 Hz mains frequency so each dot interval equals 0.02 s."],
                measurements=["10-space strip length (cm or m)", "time interval 0.20 s per strip"],
                slide_number=9,
            ),
        ],
        student_markdown=(
            "Investigate motion using a bench ramp with a toy car or trolley (timing from the front of the car) "
            "and a 50 Hz ticker-timer producing 10-space strips (0.02 s per space)."
        ),
        source_slides=[7, 9],
    )

    return ParsedLesson(
        source_path="content/lessons/G9-T1-W1-movement-and-position-slides.md",
        title="Movement and Position",
        subtitle="IGCSE Physics — Ch. 1 — Grade 9, Term 1 Week 1",
        slug="movement-and-position",
        chapter_number=1,
        chapter_title="Movement and position",
        qualification="Pearson Edexcel International GCSE Physics (Modular) 4XPH1",
        duration_minutes=60,
        frontmatter={"marp": True, "theme": "default", "paginate": True},
        spec_refs=["1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"],
        learning_objectives=[obj for b in blocks for obj in b.learning_objectives],
        vocabulary=[v for b in blocks for v in b.vocabulary],
        formulas=[
            FormulaSummary("1.4", "average speed", "v = s/t"),
            FormulaSummary("1.6", "acceleration", "a = (v - u)/t"),
            FormulaSummary("1.10", "uniform acceleration", "v^2 = u^2 + (2 * a * s)"),
        ],
        blocks=blocks,
        practical=practical,
        examiner_alerts=alerts,
        worked_examples=[we_1, we_2, we_3, we_4],
        excluded_teacher_slides=[18],
    )


def make_unit_vector(dim: int = 1024, seed_offset: int = 0) -> list[float]:
    """Create a deterministic finite non-zero vector of length `dim`."""
    raw = [math.sin((i + 1 + seed_offset) * 0.07) + 0.1 for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


# ---------------------------------------------------------------------------
# In-Memory PostgREST Fake for Idempotency & Worksheet-Preservation Testing
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self) -> Any:
        return copy.deepcopy(self._payload)


class FakeSupabasePostgREST:
    """Simulates Supabase PostgREST tables with 21 pre-existing Ch. 1 worksheet chunks."""

    def __init__(self) -> None:
        self.tables: dict[str, dict[str, dict[str, Any]]] = {
            "resources": {
                ing.LEGACY_WORKSHEET_RESOURCE_ID: {
                    "id": ing.LEGACY_WORKSHEET_RESOURCE_ID,
                    "chapter_id": ing.CHAPTER_1_ID,
                    "resource_type": "worksheet",
                    "title": "Chapter 1 TRP worksheet",
                    "spec_refs": ["1.1"],
                }
            },
            "lessons": {},
            "learning_blocks": {},
            "resource_chunks": {},
        }
        # Seed the 21 existing Chapter 1 worksheet chunks.
        for idx in range(21):
            cid = str(uuid.uuid5(uuid.NAMESPACE_OID, f"legacy-worksheet-chunk-{idx}"))
            self.tables["resource_chunks"][cid] = {
                "id": cid,
                "resource_id": ing.LEGACY_WORKSHEET_RESOURCE_ID,
                "chapter_id": ing.CHAPTER_1_ID,
                "source_type": "worksheet",
                "block_id": None,
                "chunk_index": idx,
                "chunk_text": f"Legacy Worksheet 1 chunk {idx}",
                "chunk_type": "concept",
                "embedding": "[0.1,0.2,0.3]",
                "embedding_model": "nvidia/nemotron-3.5-embed-1b",
                "spec_refs": ["1.1"],
                "source_refs": {"concept": f"Worksheet concept {idx}"},
                "token_count": 5,
            }

        self.request_log: list[dict[str, Any]] = []

    def _table_from_url(self, url: str) -> str:
        return url.rstrip("/").split("/rest/v1/")[-1].split("?")[0]

    def post(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        json: Any = None,
        timeout: int = 30,
    ) -> _FakeResponse:
        table = self._table_from_url(url)
        self.request_log.append({"method": "POST", "table": table, "params": params})
        rows = json if isinstance(json, list) else [json]
        stored: list[dict[str, Any]] = []
        for row in rows:
            row_copy = copy.deepcopy(row)
            self.tables[table][row_copy["id"]] = row_copy
            stored.append(row_copy)
        return _FakeResponse(201, stored)

    def delete(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        timeout: int = 30,
    ) -> _FakeResponse:
        table = self._table_from_url(url)
        self.request_log.append({"method": "DELETE", "table": table, "params": params})
        params = params or {}

        chapter_filter = (params.get("chapter_id") or "").removeprefix("eq.")
        source_filter_raw = params.get("source_type") or ""
        allowed_sources: set[str] = set()
        if source_filter_raw.startswith("in.(") and source_filter_raw.endswith(")"):
            allowed_sources = set(source_filter_raw[4:-1].split(","))

        to_delete = [
            rid
            for rid, row in self.tables[table].items()
            if (not chapter_filter or row.get("chapter_id") == chapter_filter)
            and (not allowed_sources or row.get("source_type") in allowed_sources)
        ]
        for rid in to_delete:
            del self.tables[table][rid]
        return _FakeResponse(204, None)


# ---------------------------------------------------------------------------
# Tests: Bundle Construction, Metadata, Practical, Examiner Alerts, Spec 1.1
# ---------------------------------------------------------------------------

def test_bundle_builds_resources_lesson_4_blocks_and_all_chunk_types():
    lesson = make_canonical_chapter1_lesson()
    bundle = ing.build_chapter1_ingestion_bundle(lesson)

    assert bundle.chapter_id == ing.CHAPTER_1_ID
    assert bundle.embedding_model == "nvidia/nemotron-3.5-embed-1b"
    assert bundle.embedding_dim == 1024

    # 3 resources: lesson, practical, examiner_note (never worksheet)
    assert [r["resource_type"] for r in bundle.resources] == [
        "lesson",
        "practical",
        "examiner_note",
    ]
    for r in bundle.resources:
        assert r["chapter_id"] == ing.CHAPTER_1_ID
        assert r["id"] != ing.LEGACY_WORKSHEET_RESOURCE_ID
        assert "1.1" not in r["spec_refs"]

    # 1 lesson + 4 learning blocks covering 1.3–1.4, 1.5–1.6, 1.7–1.9, 1.10
    assert bundle.lesson["chapter_id"] == ing.CHAPTER_1_ID
    assert bundle.lesson["spec_refs"] == ["1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]
    assert len(bundle.learning_blocks) == 4
    assert [b["block_index"] for b in bundle.learning_blocks] == [1, 2, 3, 4]
    assert [b["spec_refs"] for b in bundle.learning_blocks] == [
        ["1.3", "1.4"],
        ["1.5", "1.6"],
        ["1.7", "1.8", "1.9"],
        ["1.10"],
    ]

    # Chunks cover lesson_block (blocks + WE-), practical (PRC-1.5), examiner_note (EXM-1..3)
    source_types = {c["source_type"] for c in bundle.chunks}
    assert source_types == {"lesson_block", "practical", "examiner_note"}
    assert "worksheet" not in source_types

    block_chunks = [c for c in bundle.chunks if c["chunk_type"] == "lesson_block"]
    we_chunks = [c for c in bundle.chunks if c["chunk_type"] == "worked_example"]
    prc_chunks = [c for c in bundle.chunks if c["source_type"] == "practical"]
    exm_chunks = [c for c in bundle.chunks if c["source_type"] == "examiner_note"]

    assert {c["source_refs"]["citation_id"] for c in block_chunks} == {
        "BLK-1",
        "BLK-2",
        "BLK-3",
        "BLK-4",
    }
    assert {c["source_refs"]["citation_id"] for c in we_chunks} == {
        "WE-1",
        "WE-2",
        "WE-3",
        "WE-4",
    }
    assert all(c["source_refs"]["citation_prefix"] == "WE" for c in we_chunks)
    assert all(c["source_type"] == "lesson_block" for c in we_chunks)
    assert all(c["block_id"] is not None for c in block_chunks + we_chunks)

    # Every chunk is tagged with chapter_id and embedding_model
    for chunk in bundle.chunks:
        assert chunk["chapter_id"] == ing.CHAPTER_1_ID
        assert chunk["embedding_model"] == "nvidia/nemotron-3.5-embed-1b"
        assert chunk["token_count"] > 0
        assert "1.1" not in chunk["spec_refs"]
        assert chunk["resource_id"] != ing.LEGACY_WORKSHEET_RESOURCE_ID

    # Spec 1.5 Practical Guide content included
    assert len(prc_chunks) >= 3  # overview + 2 methods (ramp + 50 Hz ticker-timer)
    combined_prc_text = "\n".join(c["chunk_text"] for c in prc_chunks)
    assert "PRC-1.5" in combined_prc_text
    assert "front of the car" in combined_prc_text.lower()
    assert "50 hz" in combined_prc_text.lower()
    assert "10-space" in combined_prc_text.lower()
    assert all(c["spec_refs"] == ["1.5"] for c in prc_chunks)

    # All 3 Verbatim Examiner Alerts included untouched
    assert len(exm_chunks) == 3
    exm_texts = "\n".join(c["chunk_text"] for c in exm_chunks)
    assert VERBATIM_ALERT_JUNE_2019 in exm_texts
    assert VERBATIM_ALERT_JAN_2020 in exm_texts
    assert VERBATIM_ALERT_OCT_2020 in exm_texts
    sessions_questions = {
        (c["source_refs"]["exam_session"], c["source_refs"]["question_ref"])
        for c in exm_chunks
    }
    assert sessions_questions == {
        ("June 2019", "Q10"),
        ("January 2020", "Q5"),
        ("October 2020", "Q11"),
    }


def test_spec_1_1_is_explicitly_rejected_in_block_1_and_lesson():
    lesson = make_canonical_chapter1_lesson()
    lesson.blocks[0].spec_refs = ["1.1", "1.3", "1.4"]

    with pytest.raises(ValueError, match="1.1"):
        ing.build_chapter1_ingestion_bundle(lesson)

    lesson2 = make_canonical_chapter1_lesson()
    lesson2.spec_refs = ["1.1", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]
    with pytest.raises(ValueError, match="1.1"):
        ing.build_chapter1_ingestion_bundle(lesson2)


def test_out_of_chapter_spec_ref_is_rejected():
    lesson = make_canonical_chapter1_lesson()
    lesson.blocks[3].spec_refs = ["1.10", "1.11"]

    with pytest.raises(ValueError, match="1.11"):
        ing.build_chapter1_ingestion_bundle(lesson)


# ---------------------------------------------------------------------------
# Tests: 1024-dim Vector Validation & Model Tagging
# ---------------------------------------------------------------------------

def test_embedding_vector_validation_enforces_1024_dim_finite_nonzero():
    valid_vec = make_unit_vector(1024)
    validated = ing.validate_embedding_vector(valid_vec, expected_dim=1024)
    assert len(validated) == 1024

    # Wrong dimension (e.g., 768 or 1536)
    with pytest.raises(ValueError, match="dimension mismatch"):
        ing.validate_embedding_vector(make_unit_vector(768), expected_dim=1024)

    # NaN / Inf coordinate
    bad_nan = list(valid_vec)
    bad_nan[10] = float("nan")
    with pytest.raises(ValueError, match="Non-finite"):
        ing.validate_embedding_vector(bad_nan, expected_dim=1024)

    # Zero vector
    with pytest.raises(ValueError, match="Zero-norm"):
        ing.validate_embedding_vector([0.0] * 1024, expected_dim=1024)

    # Bool disguised as int
    bad_bool: list[Any] = list(valid_vec)
    bad_bool[0] = True
    with pytest.raises(ValueError, match="Invalid embedding coordinate"):
        ing.validate_embedding_vector(bad_bool, expected_dim=1024)


def test_attach_validated_embeddings_formats_pgvector_and_checks_count():
    lesson = make_canonical_chapter1_lesson()
    bundle = ing.build_chapter1_ingestion_bundle(lesson)

    vectors = [make_unit_vector(1024, i) for i in range(len(bundle.chunks))]
    attached = ing.attach_validated_embeddings(bundle.chunks, vectors)
    assert len(attached) == len(bundle.chunks)
    for row in attached:
        assert row["embedding"].startswith("[") and row["embedding"].endswith("]")
        assert len(row["embedding"][1:-1].split(",")) == 1024
        assert row["embedding_model"] == "nvidia/nemotron-3.5-embed-1b"

    # Count mismatch rejected
    with pytest.raises(ValueError, match="count mismatch"):
        ing.attach_validated_embeddings(bundle.chunks, vectors[:-1])


# ---------------------------------------------------------------------------
# Tests: Idempotent Re-run & 21 Existing Worksheet Chunks Preservation
# ---------------------------------------------------------------------------

def test_idempotent_rerun_and_preservation_of_21_existing_worksheet_chunks():
    fake_db = FakeSupabasePostgREST()
    lesson = make_canonical_chapter1_lesson()

    # Snapshot the 21 existing worksheet chunks before ingestion.
    initial_worksheet_chunks = {
        cid: copy.deepcopy(row)
        for cid, row in fake_db.tables["resource_chunks"].items()
        if row["source_type"] == "worksheet"
    }
    assert len(initial_worksheet_chunks) == 21

    def fake_embed(texts: list[str], nvidia_key: str, *, model: Optional[str] = None) -> list[list[float]]:
        assert model == "nvidia/nemotron-3.5-embed-1b"
        return [make_unit_vector(1024, i) for i in range(len(texts))]

    # First run
    res1 = ing.ingest_chapter1(
        parsed_lesson=lesson,
        supabase_url="https://example.supabase.co",
        supabase_key="test-service-role-key",
        nvidia_key="test-nvidia-key",
        embed_fn=fake_embed,
        http_session=fake_db,
    )
    snapshot_after_run1 = copy.deepcopy(fake_db.tables)

    assert res1["dry_run"] is False
    assert res1["resources_upserted"] == 3
    assert res1["lessons_upserted"] == 1
    assert res1["learning_blocks_upserted"] == 4
    assert res1["chunks_stored"] == res1["chunks_count"] == res1["embedded"]

    # Second run (idempotency check)
    res2 = ing.ingest_chapter1(
        parsed_lesson=lesson,
        supabase_url="https://example.supabase.co",
        supabase_key="test-service-role-key",
        nvidia_key="test-nvidia-key",
        embed_fn=fake_embed,
        http_session=fake_db,
    )
    snapshot_after_run2 = copy.deepcopy(fake_db.tables)

    # Identical state across re-runs: no duplicate rows, identical UUIDs, identical payloads
    assert res1 == res2
    assert snapshot_after_run1 == snapshot_after_run2
    assert len(fake_db.tables["resources"]) == 4  # 1 legacy worksheet + 3 new resources
    assert len(fake_db.tables["lessons"]) == 1
    assert len(fake_db.tables["learning_blocks"]) == 4

    # All 21 existing Chapter 1 worksheet chunks are 100% untouched!
    final_worksheet_chunks = {
        cid: row
        for cid, row in fake_db.tables["resource_chunks"].items()
        if row["source_type"] == "worksheet"
    }
    assert len(final_worksheet_chunks) == 21
    assert final_worksheet_chunks == initial_worksheet_chunks

    # Verify DELETE filter never includes 'worksheet'
    delete_calls = [r for r in fake_db.request_log if r["method"] == "DELETE"]
    assert len(delete_calls) == 2
    for call in delete_calls:
        assert call["table"] == "resource_chunks"
        assert call["params"]["chapter_id"] == f"eq.{ing.CHAPTER_1_ID}"
        assert call["params"]["source_type"] == "in.(lesson_block,practical,examiner_note)"
        assert "worksheet" not in call["params"]["source_type"]


def test_deterministic_bundle_is_identical_across_repeated_builds():
    lesson = make_canonical_chapter1_lesson()
    b1 = ing.build_chapter1_ingestion_bundle(lesson)
    b2 = ing.build_chapter1_ingestion_bundle(lesson)

    assert b1.resources == b2.resources
    assert b1.lesson == b2.lesson
    assert b1.learning_blocks == b2.learning_blocks
    assert b1.chunks == b2.chunks


# ---------------------------------------------------------------------------
# Tests: CLI `--dry-run`, `--source`, and Dynamic `marp_parser` Resolution
# ---------------------------------------------------------------------------

def test_dry_run_requires_no_api_keys_or_network(monkeypatch, capsys):
    lesson = make_canonical_chapter1_lesson()

    # Clear all credentials to prove dry-run works offline with zero secrets.
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    # Provide a fake `pipeline.marp_parser` module to verify real import resolution too.
    fake_mod = types.ModuleType("pipeline.marp_parser")
    called_paths: list[Path] = []

    def _fake_parse(source: str | Path, *, enforce_chapter1_boundary: bool = True) -> ParsedLesson:
        called_paths.append(Path(source))
        assert enforce_chapter1_boundary is True
        return lesson

    fake_mod.parse_marp_lesson = _fake_parse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pipeline.marp_parser", fake_mod)

    # Also block any accidental HTTP request during dry-run.
    def _fail_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("HTTP call must not happen during --dry-run")

    monkeypatch.setattr(ing.requests, "post", _fail_http)
    monkeypatch.setattr(ing.requests, "delete", _fail_http)
    monkeypatch.setattr(ing.requests, "get", _fail_http)

    exit_code = ing.main(
        [
            "--dry-run",
            "--json",
            "--source",
            "content/lessons/G9-T1-W1-movement-and-position-slides.md",
        ]
    )
    assert exit_code == 0
    assert len(called_paths) == 1
    assert called_paths[0].name == "G9-T1-W1-movement-and-position-slides.md"

    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["chapter_id"] == ing.CHAPTER_1_ID
    assert output["embedding_model"] == "nvidia/nemotron-3.5-embed-1b"
    assert output["embedding_dim"] == 1024
    assert output["resources_count"] == 3
    assert output["learning_blocks_count"] == 4
    assert output["chunks_stored"] == 0
    assert output["chunks_by_source_type"]["examiner_note"] == 3
    assert output["chunks_by_source_type"]["practical"] >= 3
    assert output["chunks_by_source_type"]["lesson_block"] >= 8  # 4 blocks + 4 WE- examples


def test_secret_redaction_on_embedding_failure():
    lesson = make_canonical_chapter1_lesson()
    secret = "nvapi-super-secret-token-12345"

    def _boom(texts: list[str], nvidia_key: str, *, model: Optional[str] = None) -> list[list[float]]:
        raise RuntimeError(f"Auth failed using {nvidia_key}")

    with pytest.raises(RuntimeError) as exc_info:
        ing.ingest_chapter1(
            parsed_lesson=lesson,
            supabase_url="https://example.supabase.co",
            supabase_key="sb-secret-key",
            nvidia_key=secret,
            embed_fn=_boom,
        )
    assert secret not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_real_marp_deck_bundle_includes_foundation_dfrac_and_strict_spec_boundary():
    from pipeline.marp_parser import parse_marp_lesson

    slides_path = _REPO_ROOT / "content" / "lessons" / "G9-T1-W1-movement-and-position-slides.md"
    parsed = parse_marp_lesson(slides_path, enforce_chapter1_boundary=True)
    bundle = ing.build_chapter1_ingestion_bundle(parsed)

    assert bundle.lesson["spec_refs"] == ["1.3", "1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]
    assert "1.1" not in bundle.lesson["spec_refs"]
    assert "1.13" not in bundle.lesson["spec_refs"]

    b1 = bundle.learning_blocks[0]
    assert b1["spec_refs"] == ["1.3", "1.4"]
    assert b1["metadata"]["has_foundation"] is True
    assert "displacement" in (b1["metadata"]["foundation"] or "").lower()
    assert b1["sections"][0]["kind"] == "foundation"
    assert any(w["widget_type"] == "scalar-vector-demo" for w in b1["widgets"])

    combined_chunks = "\n".join(c["chunk_text"] for c in bundle.chunks)
    assert r"\dfrac{s}{t}" in combined_chunks
    assert r"\dfrac{v - u}{t}" in combined_chunks
    assert r"\dfrac{100}{12.5}" in combined_chunks
    assert "0.20" in combined_chunks
