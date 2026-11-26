# Pedagogical Architecture

---

## Foundations

### Cognitive Load Theory

Instructional design minimises extraneous cognitive load while optimising germane load. Concepts are introduced in small, scaffolded steps. Worked examples precede independent practice. Dual coding (text + diagrams) is used wherever possible.

### Constructivism

Learners build new knowledge on existing mental models. The AI tutor probes prior understanding before introducing new content. Misconceptions are addressed as opportunities for restructuring knowledge, not as errors.

### Learner Agency

Students are active participants in their learning journey. The platform encourages self-explanation, goal-setting, and reflective practice. The AI tutor fades support as competence increases, following a gradual release of responsibility model.

### Culturally Responsive Education

All examples, analogies, and contexts are selected to be inclusive and representative. Learners from all backgrounds see themselves reflected in the material. Language complexity is monitored and adjusted.

### Metacognition

Students are prompted to think about their own thinking. Each learning block includes reflection questions that build metacognitive awareness: "What did I just learn?", "What was challenging?", "What strategy helped me understand?"

### Reflective Practice

Learning is not complete until it is reflected upon. The platform scaffolds reflection at multiple timescales: after each block, after each lesson, and after each assessment.

---

## Curriculum Hierarchy

```
Unit
  ↓
Chapter
  ↓
Lesson
  ↓
Learning Blocks
  ↓
Worksheet
  ↓
Practical Investigation
  ↓
Quiz
```

Specification Points support every layer but do not replace the learning hierarchy. They exist primarily for curriculum traceability.

### Canonical Domain Vocabulary

| Canonical Term | Scope & Boundary |
|---|---|
| **Learning Block** | One vertical, self-contained solo-student unit inside a Lesson (`4` blocks in Ch. 1 covering specs `1.3–1.10`). |
| **Self-Check** (`Mini Quiz`) | Low-stakes inline retrieval check at the close of a block; `<80%` opens a calm inline solo remediation card rather than hard-locking progress. |
| **Guided Practice** | Step-by-step `I Do / We Do / You Do` worked examples inside a Learning Block. |
| **Worksheet** | The PDF + OpenKB practice surface (`HybridDocumentViewer` tab), distinct from Guided Practice. |
| **Practical** | Curriculum/domain surface for required experimental investigations (e.g. Spec `1.5`). |
| **Simulation** | Interactive physics canvas/widget embedded inside a Practical or Learning Block. |
| **Examiner Alert** | Verbatim Edexcel examiner report warning surfaced on Guided Practice / Worksheet items and indexed into RAG. |
| **Resource** | Unified database/RAG parent spine (`resources` table typed by `resource_type`) backing `resource_chunks`. |

---

## Learning Blocks

Every lesson is divided into small blocks. Each block has:

1. **Objectives** — What the student will learn
2. **Explanation** — Clear, concise concept exposition
3. **Examples** — Concrete instances of the concept
4. **Analogy** — Familiar context to reduce cognitive load
5. **Mini Activity** — Active engagement with the content
6. **Reflection** — Metacognitive pause (1-line prompt)
7. **Self-Check (Mini Quiz)** — Low-stakes retrieval practice (with calm `<80%` solo remediation)
8. **Completion** — Soft-gated progress checkpoint

---

## Progress & Practical Debrief

- Students complete blocks freely (soft-gated — no hard locks, streaks, or confetti; see [ADR-0003](../adr/0003-calm-xp-on-student-block-progress.md))
- Quiet header tracking shows blocks completed, spec objectives, and flat per-block XP (`student_block_progress.xp_awarded`)
- Single-source Marp `.md` authoring rules are defined in [ADR-0001](../adr/0001-marp-single-authoring-source.md)
- **VMR Practical Debrief:** Every practical Simulation concludes with a structured **Vary, Measure, Repeat** Edexcel AO3 debrief coached by the AI Tutor ([ADR-0004](../adr/0004-client-side-physics-sim-and-vmr-debrief.md))

---

## AI Tutor

The AI should:

- **Teach** — Explain concepts clearly and accurately
- **Guide** — Scaffold understanding without giving answers
- **Question** — Probe understanding and surface misconceptions
- **Support** — Provide encouragement and build confidence

The AI must never simply give answers. Its role is to develop independent thinkers.

---

## Equity

Every learner should be supported regardless of:

- Background
- Culture
- Learning speed
- Language
- Prior knowledge
- Socioeconomic status

The platform adapts its language, pace, and examples to meet each learner where they are.

---

## Analogies

Complex ideas should be explained using:

- Everyday experiences
- Student interests
- Age-appropriate examples
- Sports
- Games
- Technology
- Daily life

Analogies should reduce cognitive load rather than distract. Each analogy is chosen to map cleanly onto the target concept with minimal extraneous detail.

---

## Assessment

Assessment is continuous. Every interaction can contribute evidence of learning.

Feedback should always include:

- **Strengths** — What the student did well
- **Misconceptions** — Specific misunderstandings identified
- **Next steps** — Clear guidance on what to focus on next
- **Confidence building** — Encouragement that supports motivation

---

## Learner Agency

Students should increasingly rely on:

- Self-explanation
- Reflection
- Independent practice
- AI guidance

rather than teacher intervention. The platform's goal is to develop self-regulated learners who can direct their own learning journey.
