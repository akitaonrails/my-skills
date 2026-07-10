---
name: iss-audit
version: 1.0.0
description: |
  Audit GitHub issues before implementation. Use when the user asks to
  "audit issue #N", "review open issues", "triage issues", "check opened
  issues", or decide whether an issue is valid, reproducible, worth fixing,
  and how to resolve it cleanly without stacking narrow hacks.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - WebFetch
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskList
  - AskUserQuestion
---

# Issue Audit: from bug report to clean resolution plan

Use this skill to audit open GitHub issues **before writing code**. The goal is
not to rubber-stamp every report. The goal is to decide, critically and fairly:

1. whether the issue description makes sense,
2. whether the behavior is reproducible or at least plausibly reproducible,
3. whether the issue is worth resolving now,
4. what the minimal clean fix should touch,
5. what regression tests must guard against recurrence,
6. whether this is a one-off exception or part of a broader bug class.

Default posture: **skeptical but constructive**. Do not assume the reporter's
diagnosis is correct. Do not dismiss a real user pain just because their
proposed fix is wrong.

---

## Hard rules

- **Do not implement during audit** unless the user explicitly asks to fix after
  the audit. Produce a decision and plan first.
- **One issue at a time for fixes.** Batch-auditing is fine; batch-fixing is not
  unless issues are proven to share the same root cause.
- **Do not close issues as invalid without evidence.** If uncertain, say what
  evidence is missing and ask for it or propose a reproduction probe.
- **Prefer root-cause fixes over symptom patches.** A narrow exception is only
  acceptable when the broader class has been consciously ruled out.
- **Every legitimate bug fix needs a regression test**, unless technically
  impossible. If impossible, explain why and name the closest executable guard.
- **Respect project invariants.** Read `CLAUDE.md`, `AGENTS.md`, README rules,
  compatibility guarantees, and release/testing docs before recommending a fix.
- **Preserve backwards compatibility.** If the project has config/CLI/API
  compatibility rules, treat behavior changes as risky and call them out.

---

## Phase 0 — Scope and inventory

If the user names one issue:

```bash
gh issue view ISSUE_NUMBER --json number,title,state,body,labels,comments,author,createdAt,updatedAt
```

If the user asks for open/opened issues:

```bash
gh issue list --state open --json number,title,labels,updatedAt,author
```

Then audit each issue independently. For a large issue list, sort by:

1. data loss/security/regression risk,
2. reproducibility and clarity,
3. user impact,
4. implementation size,
5. age or release relevance.

Return a compact triage table first, then detailed notes for issues that are
valid or ambiguous.

---

## Phase 1 — Understand the claim, not just the title

For each issue, extract:

- **Observed behavior**: what the user says happened.
- **Expected behavior**: what they wanted instead.
- **Environment**: OS, versions, flags, config, command, paths, CI/runtime.
- **Steps to reproduce**: exact commands or setup, if present.
- **Proposed solution**: if the issue includes one.
- **Impact**: crash, data loss, security leak, UX confusion, docs gap, etc.

If the body is empty or vague, do not invent facts. Classify as one of:

- `already implemented / docs issue`,
- `needs reproduction details`,
- `plausible but under-specified`,
- `valid from code inspection`,
- `invalid / intended behavior`,
- `feature request / product decision`.

---

## Phase 2 — Check whether the description makes sense

Read the relevant code and docs. Ask:

- Does the described path exist in the current code?
- Does the code actually behave the way the report claims?
- Is the reported behavior caused by documented constraints?
- Is the user's proposed solution compatible with project invariants?
- Would fixing it break existing configs, commands, data formats, or workflows?
- Is this actually a docs/expectation problem rather than code?

Use fast local search first:

```bash
gh issue view ISSUE_NUMBER --json title,body,comments
```

Then inspect targeted files with `Read`, `Grep`, `Glob`, or an explorer agent.
Do not paste huge files into context when paths/line references are enough.

---

## Phase 3 — Reproducibility assessment

Classify reproducibility:

| Class | Meaning | Action |
|---|---|---|
| `Confirmed` | You reproduced locally or with an existing failing test | Plan fix and regression test |
| `Code-inspection confirmed` | Exact bug is obvious from code path | Plan fix and regression test |
| `Plausible` | Report matches likely behavior but needs setup | Name minimal reproduction probe |
| `Not reproducible yet` | Tried and failed to reproduce | Ask for details or close only if evidence is strong |
| `Not enough info` | Missing commands/config/env | Ask targeted questions |

Prefer adding or sketching a failing regression test before changing code. If
the issue involves platform behavior that cannot be run locally, propose a unit
test around command construction, config parsing, generated policy, or dry-run
output.

---

## Phase 4 — Worth resolving?

Rate value and urgency:

- **Severity**: security/data loss/crash/regression > broken common workflow >
  confusing UX > docs-only > speculative feature.
- **User impact**: how many users and how frequently?
- **Risk of change**: could fixing break old configs, scripts, files, or
  expectations?
- **Maintenance cost**: new complexity, new dependency, new API surface.
- **Product fit**: does this belong in the tool or in docs/user config?

Valid outcomes:

- `Fix now` — clear bug, bounded change, testable.
- `Fix with design caution` — valid but changes semantics/security/API.
- `Docs/comment only` — behavior is intended but expectations need clarity.
- `Needs reporter info` — no responsible fix can be planned yet.
- `Decline` — incompatible with project goals or too risky for benefit.

---

## Phase 5 — Root cause and bug-class analysis

Before proposing a patch, decide whether this is:

1. **A simple exception**: one bad special case; narrow fix is appropriate.
2. **A class of bugs**: same pattern likely exists in multiple paths.
3. **A design gap**: current model lacks a concept/option needed to solve it.
4. **A documentation gap**: behavior is correct but not explained.
5. **A test gap**: code works now but no regression guard exists.

Ask explicitly:

- Are there parallel code paths for Linux/macOS/Windows, config/CLI, runtime
  and dry-run, normal/browser/lockdown modes, global/project config, or
  wrapper/child process paths?
- Would a one-line exception leave the same bug elsewhere?
- Is there a helper or abstraction that should own the rule?
- Can the same test cover the class, not just the exact reported example?
- Does the fix need migration or compatibility behavior?

Avoid “fix towers”: do not stack another conditional onto an already messy path
unless it is clearly the right ownership point. If a small refactor is needed to
put the rule in one place, include it in the plan.

---

## Phase 6 — Minimal clean fix plan

For valid issues, produce a code plan with:

- **Files/functions to touch** with line references when possible.
- **Why those files own the rule**.
- **Behavior before/after**.
- **Compatibility risks**.
- **Test plan**, including the regression test that would fail today.
- **Verification commands** using the project's documented gates.
- **Out of scope** items to avoid feature creep.

The minimal clean fix is not always the fewest lines. It is the smallest change
that puts the rule in the right place, covers all parallel paths, and prevents
the same bug class from recurring.

### Regression test expectations

Tests should usually include:

- one focused unit/regression test for the reported case,
- one adjacent case proving the broader rule or boundary,
- one backwards-compatibility/default-behavior test if behavior/config changed,
- platform/policy generation tests when runtime reproduction is hard.

If a feature has multiple front doors, test at least the relevant ones:

- CLI parsing,
- config parsing/merge/save,
- generated commands/policies/dry-run,
- runtime helpers,
- docs if the project tests docs examples.

---

## Phase 7 — Output format

For one issue:

```markdown
## Issue #N — <title>

Decision: Fix now | Fix with design caution | Docs/comment only | Needs info | Decline
Reproducibility: Confirmed | Code-inspection confirmed | Plausible | Not reproducible | Not enough info
Severity: Critical | High | Medium | Low

### Audit
- What the issue claims:
- What the code/docs show:
- Does the description make sense?
- Is the proposed solution right?

### Root cause / class of bug
- Root cause:
- Simple exception or bug class?
- Parallel paths to check:

### Resolution plan
- Minimal clean code touch:
- Regression tests:
- Verification:
- Compatibility / rollout risks:

### Suggested issue response
<short GitHub comment text>
```

For multiple issues, start with:

```markdown
| Issue | Decision | Reproducibility | Severity | Recommended next step |
|---|---|---|---|---|
```

Then include detailed sections only for issues that need action or judgment.

---

## Suggested GitHub comment patterns

### Valid bug

```markdown
Confirmed. The issue is in <file/function>: <brief reason>. I plan to fix it by
<clean ownership point>, with regression tests for <cases>. This looks like
<simple exception / broader class>, so the fix will also cover <adjacent paths>.
```

### Needs info

```markdown
I can't responsibly reproduce this yet. Could you share:

1. exact command,
2. relevant config,
3. OS/version,
4. expected vs actual output?

The closest code path is <file/function>, but there are multiple possible causes.
```

### Intended behavior / docs

```markdown
This appears to be intended behavior because <reason>. The confusing part is
that <docs gap>. I recommend clarifying docs rather than changing runtime
behavior, because changing it would break <compatibility risk>.
```

### Decline

```markdown
I don't recommend implementing this as proposed. It conflicts with <project
invariant/security/compatibility>. A safer alternative is <alternative>, or we
can revisit if a concrete reproduction shows a bug rather than a product tradeoff.
```

---

## Anti-patterns this skill should catch

- Fixing only the reporter's exact string/path/flag while leaving equivalent
  paths broken.
- Changing defaults to satisfy one report without considering existing users.
- Adding a config field without default/serialization/backward-compat tests.
- Fixing Linux but forgetting macOS/dry-run/Landlock/seatbelt equivalents.
- Fixing runtime but forgetting generated docs/help/status output.
- Closing vague issues without asking for the exact missing reproduction data.
- Accepting the user's proposed implementation without checking root cause.
- Adding tests that only assert the new implementation, not the old bug.
- Treating feature requests as bugs without a product/security decision.
