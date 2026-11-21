# Agent Guide — Alsini Physics Platform

## GitHub Issues & Backlog Workflow

GitHub Issues are the source of truth for queued work. Run `gh` commands from the repository root.

| Label | Meaning |
|---|---|
| `hitl` | Human-in-the-loop supervised task |
| `afk` | Autonomous loop task (requires passing tests) |
| `blocked` | Blocked by another issue |
| `qa` | Ready for QA verification |

### Finding work

- Human-in-the-loop queue: `gh issue list --state open --label hitl`
- Autonomous queue: `gh issue list --state open --label afk`
- Ignore issues labeled `blocked`, and issues whose body contains an unresolved
  `Blocked by #<id>` dependency. Check the referenced issue's state before starting.

### Loading issue context

At the start of every session, run `gh issue view <number> --comments` to read the
full specification, acceptance criteria, and prior discussion before changing code.

### Progress and handoff trace

Post implementation notes, test results, blockers, and QA findings directly on the issue:

```bash
gh issue comment <number> --body "..."
```

Treat the issue thread as the audit trail. A fresh session must be able to reconstruct
spec → implementation → verification from the issue alone.

### Closing issues

- Reference the issue in commits/PRs with `Closes #<number>` when the work is complete.
- Use `Refs #<number>` for partial work that should not close the issue.
- When implementation is complete but verification is pending, add the `qa` label
  instead of closing.
- Only close after the acceptance criteria are met and the verification path is
  recorded on the issue.

### Repo mirror for specs

Whenever a parent PRD or multi-slice spec is created, save a Markdown copy under
`docs/prd/` (for example `docs/prd/<slug>.md`) so repository-level reviewers can read
it alongside the codebase. Link the issue and the mirrored file to each other.
