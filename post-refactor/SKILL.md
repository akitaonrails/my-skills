---
name: post-refactor
version: 1.0.0
description: |
  Post-refactor clean-code check after recent refactors or a few merged PRs.
  Use when the user says "post-refactor", "after the refactor", "we merged a
  few PRs", "clean code checks", or wants a focused sweep for regressions,
  vulnerabilities, duplicated abstractions, magic values, weak documentation,
  missing coverage, or flaky tests without running a full PR/post-merge audit.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskList
  - AskUserQuestion
---

# Post-Refactor Clean-Code Sweep

Use this skill after a refactor, cleanup series, or a handful of related PRs
landed. It is **not** a full PR audit and should not re-litigate already merged
work. Keep the pass focused on the code that changed recently and on defects
that refactors commonly leave behind.

Primary goal: answer, "Did we leave the touched code cleaner, safer, and well
covered, or did we leave regressions and cleanup debt behind?"

## Scope

Pick the narrowest useful range:

1. If the user names a range, use it exactly.
2. Else, if a release just happened, inspect changes since the previous tag:
   `git describe --tags --abbrev=0 HEAD^` → `PREV_TAG..HEAD`.
3. Else, inspect the last 3-8 related commits or merged PRs.
4. If the range spans unrelated areas, group by subsystem and review each group
   separately.

Do not expand into full architecture review unless a finding shows a real risk.

## Workflow

### 1. Establish the changed surface

Collect:

- commit range and shortlog
- changed files grouped by subsystem
- dependency/config/schema changes
- tests added/changed
- public/user-facing surfaces touched

Prefer cheap git commands and focused reads. Do not read the whole repository.

### 2. Run the local safety gate

Run the project's documented post-change checks. If none are documented, infer
the normal formatter, lint/static-analysis, test, and security/dependency checks
from the stack.

For Rust repos, prefer:

```bash
cargo fmt --check
git diff --check
TAILWIND_SKIP=1 cargo test --workspace
TAILWIND_SKIP=1 cargo clippy --workspace --all-targets -- -D warnings
```

Run vulnerability/dependency checks when available (`cargo audit`, `cargo deny`,
`npm audit`, `bundle audit`, etc.). Treat tool availability separately from
findings: "tool not installed" is a validation gap, not a pass.

### 3. Review the changed code for refactor fallout

For touched implementation files, check:

- regressions from changed behavior, defaults, serialization, migrations, auth,
  scope resolution, IO boundaries, or error handling
- new `unwrap`, `expect`, `panic`, `unreachable`, broad catches, ignored errors,
  or lossy fallbacks in runtime paths
- duplicated helpers or repeated logic that should be consolidated
- over-abstraction: new traits/generics/public APIs that have only one real
  caller and no concrete need
- magic values that should become named constants, config, or comments
- stale comments/docs that no longer match behavior
- hidden coupling between modules or crates introduced by the refactor
- data loss, destructive operations, auth bypass, secret leakage, or unsafe
  path/scope handling

Bias toward practical clean-code fixes. Do not demand abstraction for one-off
logic unless duplication is already causing drift or risk.

### 4. Review test quality and flake risk

Check whether changed behavior has focused tests. Look for:

- missing regression tests for bug fixes or behavior changes
- tests that assert implementation details instead of behavior
- overly broad snapshot/golden tests that hide the meaningful assertion
- sleeps/timeouts, wall-clock dependence, network dependence, shared global
  state, non-temp filesystem writes, randomized order, current-user/home-dir
  dependence, and cross-test pollution
- tests that passed only because they were run individually

If a test looked flaky during the session, rerun that exact target once before
classifying it. If it passes on rerun, report it as "observed transient" with
evidence, not as definitively fixed.

### 5. Classify findings

Use these severities:

- **BLOCKING**: likely regression, vulnerability, data loss, auth/scope bypass,
  failing gate, reproducible flake, or release/deploy blocker.
- **SHOULD-FIX**: maintainability/test gap that is likely to grow or confuse the
  next change; duplicated logic with drift risk; missing focused test for a real
  behavior change.
- **NIT**: cleanup/documentation/readability issue that is safe to defer.
- **OBSERVATION**: verified healthy area or watch item with no required change.

Each finding must include:

- file/path and line when available
- why it matters
- suggested fix or next check
- whether it was verified by a command/test/read

### 6. Fix policy

Do not automatically edit code unless the user explicitly asks to fix findings.
This skill is primarily a focused review/check. If fixes are requested, keep
them small and run the relevant focused gate after each batch.

## Specialist routing

- Use `@explorer` for broad changed-surface mapping when the range touches many
  files.
- Use `@oracle` for code review, maintainability, security, or flake-risk review
  of the changed surface.
- Use `@fixer` only after findings are accepted and bounded implementation work
  is clear.
- Use `@designer` only for user-visible UI/UX regressions.

## Output format

Keep the final report compact:

```markdown
## Post-refactor result

Range: <range>
Gate: <pass/fail/partial>

### Findings
- [SEVERITY] <file:line> — <issue>. <recommended action>

### Coverage / flake notes
- <summary>

### Clean-code notes
- <summary>

### Suggested next step
- <one concrete next action, or "none">
```

If there are no required changes, say so directly and list the checks that
passed.
