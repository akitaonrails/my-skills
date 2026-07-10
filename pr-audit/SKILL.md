---
name: pr-audit
version: 1.0.0
description: |
  Audit a GitHub pull request before merging. Use when the user asks to
  "audit PR #N", "review the open PRs", "should we merge this", "check
  what's pending", or otherwise wants an opinion on a PR before
  approving it. Loads the project's cross-cutting invariants, reads the
  full diff, runs local CI gates, classifies findings under six
  dimensions with severity tags, and reports pros / cons / recommended
  fix — but does NOT merge until the user explicitly approves. After
  approval, handles the merge ritual: thank the author, close the
  linked issue, audit docs for staleness, decide on version bump, live
  test on homelab if deployable.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - WebFetch
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskList
  - AskUserQuestion
---

# PR Audit: from "should we merge?" to a clean post-merge state

The single rule this skill enforces: **never merge during evaluation.**
The AGENTS.md / CLAUDE.md rule in any repo using this skill says report
pros / cons / recommended fix and wait for approval. Everything below
is the workflow that makes that report worth reading.

---

## Phase 0 — Pre-flight (do these before reading the diff)

Five quick checks that decide whether to keep going.

### 0.1 Is the PR ready for audit?

```bash
gh pr view $PR --json isDraft,state,title,body,mergeStateStatus,updatedAt
```

Only audit PRs that are ready: `isDraft=false`, `state=OPEN`, and the
title/body do not clearly say WIP, draft, do-not-merge, blocked, or
otherwise incomplete. A recent commit is **not** a blocker by itself;
if the PR is non-draft and appears complete, audit it. If the PR is
draft or clearly incomplete, list it as skipped with the reason and do
not spend audit budget on it yet.

### 0.2 Scope gate — solo vs fan-out

```bash
gh pr view $PR --json additions,deletions,changedFiles,files \
  | jq '{
      loc: (.additions + .deletions),
      files: .changedFiles,
      areas: ([.files[].path | split("/")[0:2] | join("/")] | unique | length)
    }'
```

"Areas" here = the first one or two path segments of each changed
file, deduplicated. In a multi-crate Rust workspace it counts
`crates/foo` vs `crates/bar`. In a Node monorepo it counts
`packages/foo` vs `apps/web`. In a Django project it counts
`apps/users` vs `apps/billing`. Adjust the slice depth (`[0:2]` vs
`[0:1]`) to match the layout.

| LoC | Areas touched | Audit mode |
|---|---|---|
| ≤ 500 | ≤ 3 | Solo — single audit pass in the main context |
| > 500 OR > 3 | — | Parallel fan-out — one `Agent` subagent per area, bounded reports ≤ 400 words each |

The fan-out prompt template is in **§ Templates** below.

### 0.3 Load the project's cross-cutting invariants

```bash
test -f CLAUDE.md && head -200 CLAUDE.md
test -f AGENTS.md && head -200 AGENTS.md
```

Pin every numbered invariant in working memory before reading the
diff. Findings get matched against this list. A common shape:
"single-writer SQLite actor", "one config-read path", "indexes in
same transaction", "typed identity 3-tuple", "no `lazy_static`",
"namespaced storage layout", etc.

### 0.4 Has CHANGELOG been updated?

```bash
gh pr diff $PR -- CHANGELOG.md | head
```

Any user-facing change (new flag / env var / endpoint / MCP tool /
public API / behaviour change / observable bug fix) without an
`[Unreleased]` entry is **`[BLOCKING]`**, goes at the top of the cons
list, and is a **hard gate**: do not move the report to a "merge as-is"
recommendation. The two acceptable outcomes are:

1. The author updates the PR to add the entry. Wait for the push, then
   re-run from Phase 1.
2. The operator explicitly waives ("merge anyway, I'll batch the
   CHANGELOG later"). Record the waiver in the report so the
   post-merge follow-up commit attribution is clear.

The "batched CHANGELOG follow-up" pattern was the single most-forgotten
contributor obligation across the last several merge batches — every
batch needed a `docs(changelog)` cleanup commit. Treating absence as
BLOCKING at PR-review time shifts the cost from one post-release
scramble to one pre-merge review comment. See CLAUDE.md invariant #19.

Internal-only changes that don't surface to users (refactors, dead-code
removal, test-only churn) are exempt.

### 0.5 Has the author flagged the behaviour change?

If the diff changes a default (a CLI flag's behaviour, a config
default, an env var), the commit message OR the PR body must say so
loudly. Grep for it:

```bash
gh pr view $PR --json title,body
gh pr view $PR --json commits | jq -r '.commits[].messageHeadline'
```

If a default changed and nothing in the PR says so → **`[BLOCKING]`**.

---

## Phase 1 — Local CI gate

Check out the PR locally. The audit is unreliable if the code doesn't
build.

```bash
gh pr checkout $PR
```

Then run the project's three gates: **format check, lint, tests**.
Detect the stack from project files and run the appropriate commands.
Common patterns:

| Stack signal | Gate commands |
|---|---|
| `Cargo.toml` (Rust) | `cargo fmt --all -- --check` · `cargo clippy --workspace --all-targets -- -D warnings` · `cargo test --workspace` |
| `package.json` (Node / TS) | `npm run format:check` (or `prettier --check .`) · `npm run lint` (or `eslint .`) · `npm test` (or `vitest run` / `jest`) |
| `pyproject.toml` / `setup.py` (Python) | `ruff format --check .` (or `black --check .`) · `ruff check .` (or `flake8` / `mypy .`) · `pytest` |
| `go.mod` (Go) | `gofmt -l . \| grep .` (must be empty) · `go vet ./...` (or `golangci-lint run`) · `go test ./...` |
| `Gemfile` (Ruby) | `bundle exec rubocop` · `bundle exec rspec` |
| `mix.exs` (Elixir) | `mix format --check-formatted` · `mix credo` · `mix test` |

If the repo has CI config (`.github/workflows/`, `.gitlab-ci.yml`,
`Makefile`, `justfile`, `Taskfile.yml`, `package.json` scripts), prefer
the commands it actually runs over guessing — `grep -rE "fmt|lint|test"
.github/workflows/ Makefile package.json 2>/dev/null` will surface them.

Record the **test count delta** vs the base branch (or vs the
previous run on `main` if the runner reports a total). A PR that
**decreases** test count without explicit justification ("removed dead
tests for X feature") is suspect — flag it as a finding. If the
runner doesn't print a count, fall back to "all green" + a note.

If lint or tests fail, halt the audit. The PR isn't ready for
review; tell the user so and ask whether to push back or fix.

---

## Phase 2 — Read the diff with intent

```bash
gh pr diff $PR
```

Read every line. For each hunk classify what it does, then check it
against the six dimensions.

### The six dimensions (every finding lives under one of these)

| Dimension | What to look for |
|---|---|
| **Regressions** | Default behaviour changed, edge cases broken, a contract weakened |
| **Dead code** | Stubs, unreachable branches, leftover scaffolding, unused fns |
| **Unnecessary duplication** | Two paths that should be one helper; copy-pasted logic |
| **Magic values** | Hardcoded numbers / strings without a named constant or rationale comment |
| **Clean code degradation** | God functions (> ~100 LoC), mixed concerns, unclear naming, weak error handling, missing rationale comments where the code is non-obvious |
| **Test coverage gaps** | Untested edge cases (esp. failure paths, halfway failures, idempotency), missing regression test for the BUG the PR claims to fix |

### Cross-cutting invariant greps (run during the audit)

Project-specific. The shape is always "for each invariant, write the
grep that detects a violation, then run it scoped to the PR's
changed files." A few generic recipes:

```bash
# Generic — "no environment reads outside the config loader"
# (Rust: std::env::var · Node: process.env · Python: os.environ
#  · Go: os.Getenv · Ruby: ENV[ · Shell: $ENV_VAR access patterns)
grep -rnE "std::env::var|process\.env\.|os\.environ\.|os\.Getenv|ENV\[" \
  $(gh pr diff $PR --name-only)

# Generic — "no global mutable singletons"
# (Rust: lazy_static! / OnceCell  · Node: module-level let
#  · Python: module-level dict  · Go: var x = sync.Once / package vars)
grep -rnE "lazy_static!|OnceCell|once_cell|sync\.Once" \
  $(gh pr diff $PR --name-only)
```

The real value is in the **project-specific** invariants you load
from `CLAUDE.md` / `AGENTS.md`. Write one grep per invariant once,
keep them in a project-local notes file, reuse on every PR. Any hit
inside the PR diff that violates an invariant → **`[BLOCKING]`**.

### Coupled doc-staleness audit (same pass)

If the diff adds **any** of: a new flag, a new env var, a new
endpoint, a new MCP tool, a new error code, a new public API
function — the same audit pass greps the docs and the README:

```bash
NEW_NAME="FOO_BAR"        # whatever was added
grep -rn "$NEW_NAME" README.md README.rst README.md.tmpl docs/ doc/ \
  2>/dev/null
```

If the docs don't mention it → **`[SHOULD-FIX]`** under a "Doc
staleness" findings sub-section. Catch it now; it's cheaper than a
follow-up commit when a user files an issue.

---

## Phase 3 — Severity tags

Every finding gets exactly one of these:

| Tag | Meaning |
|---|---|
| `[BLOCKING]` | Wrong / broken / misleads users. Must fix before merge. |
| `[SHOULD-FIX]` | Cleanup or coverage gap. Can land separately, but call it out. |
| `[NIT]` | Cosmetic — formatting, typo, dead link, naming preference. |
| `[UNCERTAIN]` | You suspect a problem but can't confirm without more context. Explain what would confirm it. |

If a dimension has **zero findings**, write "none found." Don't pad.

---

## Phase 4 — The audit report

Use this exact shape. Same shape every time so the user can grep
audit output across sessions and across PRs.

```
## PR #N audit — <one-line title>

**Local CI:** format ✓  lint ✓  tests N → M (+K) ✓

**Pros (3-5 bullets):**
- …

**Cons (3-5 bullets):**
- …

**Recommended fix:** none / minor patch (described inline) / split into N PRs / hold for author / merge as-is

### Findings

#### Regressions
- [SEVERITY] file_path:line — what's wrong (and what should replace it)
- (or "none found.")

#### Dead code
- …

#### Unnecessary duplication
- …

#### Magic values
- …

#### Clean code degradation
- …

#### Test coverage gaps
- …

#### Doc-staleness coupling (if applicable)
- …
```

End with: **"OK to merge as-is? Or want me to address [SEVERITY]
items first?"** — the question that gates the merge.

---

## Phase 5 — On approval: the merge ritual

Only after the user explicitly says "merge" / "go ahead" / equivalent.

### 5.1 Merge the PR

```bash
gh pr merge $PR --merge --delete-branch=false
```

Confirm:
```bash
gh pr view $PR --json state,mergeCommit,mergedAt
```

### 5.2 Close linked issues with attribution

If the PR body says "Closes #X" GitHub auto-closes. Either way, leave
a comment thanking the author and citing the merge SHA:

```bash
gh issue comment $ISSUE_NUMBER --body "$(cat <<'EOF'
Thanks <author> — <one specific thing that made the PR land fast or
that you negotiated>. Merged as <merge_sha>.
EOF
)"
```

### 5.3 Decide on version bump

Three buckets:

| What landed | Action |
|---|---|
| Bug fix, doc-only, internal refactor | Defer to next release |
| New flag / env var / endpoint / MCP tool / behaviour change | Bump minor next release; add CHANGELOG note now if not already there |
| Breaking change | Bump major; flag in CHANGELOG `### Breaking` |

If the user has a `bin/release` script, version bump is one command
later. Don't cut a release per PR unless asked.

### 5.4 Live test if the project is deployable

If the repo has a `bin/deploy` (or equivalent) and the PR touched
runtime behaviour:

```bash
bin/deploy
source bin/deploy.env && ssh "$SERVER" "sudo docker inspect --format='{{.State.Health.Status}}' <container>"
```

Smoke test one user-visible path. Report version banner +
health-check status.

---

## Phase 6 — Post-merge follow-ups

Almost every non-trivial merge spawns at least one of:

- A doc audit (separate skill / pass) if behaviour changed
- A regression test the audit said was missing
- A nit cleanup commit (batched — don't do 5 commits for 5 nits)
- An updated `[Unreleased]` CHANGELOG entry if the author forgot

Stage these as `TaskCreate` items at merge time so they don't get
forgotten. Group them into a single follow-up commit when you act on
them.

---

## Templates

### Fan-out audit prompt (one per crate-area, when scope-gate triggers)

```
You are auditing PR #N (<title>) for the <crate-name> crate. The PR
touches: <files in this crate>.

Project invariants (from CLAUDE.md/AGENTS.md):
<paste relevant ones>

PR description:
<paste body>

Audit dimensions — report findings under each, tagged
[BLOCKING] / [SHOULD-FIX] / [NIT] / [UNCERTAIN]:

- Regressions
- Dead code
- Unnecessary duplication
- Magic values
- Clean code degradation
- Test coverage gaps

For each finding: `file:line — what's wrong (and what should replace
it)`. If a dimension has zero findings, write "none found." Under
400 words total. No praise.

Files to read in full:
<list of files>

Get the diff via: `gh pr diff $PR -- <path>`
```

### Reply template — closing an issue via PR

```
Thanks <author> — <one specific thing>. Merged as <sha>.

<optional one-line note about anything we'll follow up on>.
```

### Reply template — explaining why we're not merging right now

```
<author>: this is solid work and we'd like to take it. Holding for a
moment because <reason — author still pushing / blocked by another
PR / needs minor adjustment described below>. Will pick it up
<when>.

<inline description of what we want changed, if anything>.
```

---

## Hard NOs

- **Never merge during the evaluation phase.** Even if the audit comes
  back clean. The user gates the merge.
- **Never push hooks / signing bypass flags** (`--no-verify`,
  `--no-gpg-sign`) unless the user explicitly asks. If a hook fails,
  diagnose; don't bypass.
- **Never audit draft or clearly incomplete PRs.** § 0.1 exists for a reason.
- **Never split an audit + fix into one PR.** Audit first; if fixes
  are needed, the user decides whether to ask the author or to do them
  in a follow-up PR after merge.
- **Never claim "looks good" without the local CI gate green.**
- **Never auto-bump version after a merge.** Bumps happen on the
  user's release schedule, not on every PR.

---

## When the user asks "check the open PRs" (plural)

Same workflow per PR, but batch the pre-flight:

```bash
gh pr list --state open --limit 20 --json number,title,author,isDraft,body,additions,deletions,changedFiles,updatedAt
```

Group:
1. **Draft / incomplete PRs** (`isDraft=true`, WIP/DNM/blocked title or
   body) → list with skip reason; do not audit.
2. **Ready PRs** (`isDraft=false` and appears complete) → one-line each
   on what they touch; audit these when the user asked to audit open PRs.

Don't bulk-audit by default — audit budget is real. Default to "which
of these is on your mind?" if the user hasn't pointed at one.
