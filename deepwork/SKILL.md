---
name: deepwork
description: High-cost orchestrator workflow for large, high-risk, multi-phase coding efforts with meaningful dependencies and review gates. Do not activate for routine multi-file changes.
---

# Deepwork

Deepwork is an orchestrator workflow for heavy coding sessions. Use it only
when the work is clearly large or high-risk: multiple dependent phases,
cross-cutting architectural change, unsafe-to-partially-ship migration, or
sustained coordination across several specialist lanes.

Do not infer Deepwork merely because a task touches multiple files. Do not use
it for trivial edits, quick docs changes, simple bug fixes, or routine bounded
features.

## Core Contract

When deepwork is active, the orchestrator must manage the work as a scheduler,
not as the default implementation worker.

## Setup and Deepwork State

- create and maintain a local markdown progress file under `.slim/deepwork/`;
- save code/doc deliverables to project paths (e.g. `src/`, `docs/`); reserve
  `.slim/deepwork/` strictly for progress files;

### Deepwork File

Create a task-specific file such as:

```text
.slim/deepwork/<short-task-slug>.md
```

Before creating this file—and before planning or delegation—inspect the existing
`.gitignore` and `.ignore`. Add only missing entries and do not add duplicates:

```gitignore
# .gitignore
.slim/deepwork/
```

```gitignore
# .ignore
!.slim/deepwork/
!.slim/deepwork/**
```

These rules keep deepwork state git-local while allowing OpenCode to read it.

Do not follow a rigid template. Choose whatever markdown structure best fits the
work. The file only needs to remain useful as persistent session state and should
capture, as applicable:

- current goal and understanding;
- researched, factual context from `@librarian` to avoid oracle doing its own
  research;
- plan drafts, Oracle review budget/gates, and review notes;
- implementation phases and status;
- validation results;
- unresolved questions, blockers, and follow-ups.

Update this file after major decisions, accepted research, reviews, phase
completions, validation results, and scope changes. Record accepted findings and
reference local files by path rather than copying their contents.

## Planning

- draft a plan before implementation;
- create a phased implementation/delegation plan;
- before dispatch, choose a small number of coherent implementation phases from
  the work's dependencies and natural delivery boundaries; do not split work
  merely to reduce an Oracle review's scope;
- before execution, define coherent delivery phases and make an `@oracle` review
  mandatory after each one; record the phase order, specialist ownership, gate
  order, and one-line gate rationale in the deepwork file; share a compact
  version with the user;
- before starting each phase, replace the OpenCode todo list with actionable
  delivery todos for that phase only;

## Phase Execution

- before each implementation phase, decide the execution path: what can run in
  parallel, what must be sequential, which specialists to delegate to, and
  whether to split the same agent into multiple bounded lanes;

### Scheduler Discipline

Use the scheduler model throughout:

- record task/session IDs and ownership boundaries;
- wait for hook-driven background completion before consuming background results;
- avoid blocking Orchestrator lane while background jobs run; if no independent
  work remains, stop briefly and let the completion event resume the workflow;
- do not advance to the next phase while relevant jobs are running or terminal
  results are unreconciled.

## Phase Gate and Commit

- after each planned phase, run relevant validation, update the deepwork file,
  then request its planned `@oracle` gate before continuing;
- before its planned Oracle gate, record relevant accepted research and file
  references so Oracle reviews established context rather than repeating
  discovery;
- record the phase goal, changed paths, validation evidence, and the specific
  decision or risk to review in the deepwork file; provide this context to
  Oracle with the accepted research and file references;
- when the phase changes module boundaries, dependency direction, or file
  placement, run an `@explorer` structure scan in parallel with the Oracle gate;
- reconcile review findings, perform one bounded remediation pass for material
  issues, and validate that pass with focused evidence;
- create a focused commit when the phase is an independently valid delivery
  boundary before starting the next phase;

### Oracle Re-Reviews

Every planned Oracle gate has one initial review and may have at most two
re-reviews. Request a re-review only when the remediation materially changes
the reviewed decision or risk, or when the original concern cannot be verified
with focused evidence. Do not spend a re-review on a mechanical or
already-verified change.

State the attempt in every Oracle prompt, for example:

```text
Gate 2 — review attempt 2 of 3 (1 re-review remaining)
```

For re-reviews, tell Oracle to prioritize unresolved material findings, risks
introduced by remediation, and whether prior findings are resolved. It must not
reopen accepted, unchanged, or resolved concerns. When the two re-reviews are
exhausted, record any remaining material risk or blocker in the deepwork file
and ask the user whether to accept the risk, change scope, or authorize an
exceptional additional review.

## Designer Handoff Guardrail

When a deepwork phase includes `@designer`, treat the delivered UI/UX as
accepted design intent for later phases. Record any important design decisions in
the deepwork file before continuing.

After designer work:

- preserve layout, rhythm, hierarchy, motion, spacing, color, affordances,
  responsiveness, and component feel;
- review and improve user-facing copy with grounded, normal wording, but do not
  change visual structure or interaction intent;
- route follow-up visual, responsive, motion, hierarchy, polish, or
  component-feel changes back to `@designer`;
- use `@fixer` only for bounded mechanical follow-up that preserves the design
  exactly, such as wiring, tests, type fixes, or non-visual behavior changes;
- if design intent must change, record why in the deepwork file before changing
  it.

## Completion

- finish with final validation and a concise summary.
