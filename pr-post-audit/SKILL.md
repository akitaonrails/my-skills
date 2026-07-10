---
name: pr-post-audit
version: 1.0.0
description: |
  Audit the COMBINED state after a batch of pull requests has been
  merged. Use when the user asks to "audit what we just merged",
  "look at the recent state", "any cross-PR issues?", "did the
  combination break anything?", or after 3+ PRs land in a short
  window. Catches what per-PR audits couldn't see: cross-PR
  interactions (helper drift, config bloat, invariant bridges built
  from two halves), compounded doc staleness, CHANGELOG gaps across
  the batch, and combination-only bugs. Drives phased fixes
  (BLOCKING → SHOULD-FIX → NIT), runs CI between phases, optionally
  live-tests the combined state on a deployment target, and surfaces
  a version-bump recommendation. NEVER auto-releases — the operator
  cuts the release.
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

# PR Post-Audit: catch what the per-PR gate couldn't see

`pr-audit` gate-keeps individual merges. **This skill catches the
things that aren't bugs in any single PR but emerge from the
combination** — helper drift between two PRs, invariant bridges
built from two halves, config bloat, doc-staleness that compounds,
and CHANGELOG gaps that only show when you grep the batch.

The single rule: **every fix commit names its phase** (`P1` /
`P2` / `P3`) so the audit trail stays grep-able.

---

## Phase 0 — Establish the batch boundary

Without a fixed range, the audit drifts. Pick exactly one:

```bash
# Option A — since the last release tag
RANGE="$(git describe --tags --abbrev=0)..HEAD"

# Option B — since N days
RANGE="--since='7 days ago'"

# Option C — since a specific commit (last audit, last release commit)
RANGE="<sha>..HEAD"
```

List the merges and sum the deltas:

```bash
git log $RANGE --merges --oneline
git log $RANGE --shortstat | tail -1
```

If only 1-2 merges are in the range, this skill is overkill — run
`pr-audit` retroactively or skip. Three or more merges in different
areas → keep going.

---

## Phase 1 — Baseline metrics

Capture **before** doing anything. We compare deltas at the end of
each fix phase.

```bash
# Format / lint / tests (stack-agnostic — see pr-audit § Phase 1 for
# the command table per stack).
cargo fmt --all -- --check   # adapt per stack
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace 2>&1 | grep -E "test result.*passed" \
  | awk '{ sum += $4 } END { print "tests:", sum }'

# Dependency delta (any new deps from the batch?)
git diff $RANGE -- '**/Cargo.toml' '**/package.json' \
  '**/pyproject.toml' '**/go.mod' '**/Gemfile' '**/mix.exs'

# Doc surface touched by the batch
git diff $RANGE --name-only -- docs/ README.md AGENTS.md CLAUDE.md
```

Record baseline: `format ✓  lint ✓  tests N`. Stash for later.

---

## Phase 2 — Per-PR audit gap fill

If the per-PR audits already ran (this session, recorded in memory
or transcript), pull findings forward and skip to Phase 3.

If any PR in the batch slipped through without an audit, run
`pr-audit` on it retroactively before the cross-PR pass. The
cross-PR sweep assumes each PR has been individually classified.

---

## Phase 3 — Cross-PR interaction sweep (the load-bearing pass)

This is what makes this skill different from `pr-audit`. Six
checks. Each catches a different way the combination can be worse
than the individual PRs.

### 3.1 Cross-PR invariant matrix

For every cross-cutting invariant in `CLAUDE.md` / `AGENTS.md`,
grep across **all changed files in the batch**, not per-PR. A
common combination failure: PR A added a struct field; PR B added
the init path that populates it via a direct env read. Neither PR
alone violates the invariant; together they bridge one.

```bash
CHANGED=$(git diff $RANGE --name-only)

# Each invariant gets a grep. Example for the ai-memory repo:
echo "$CHANGED" | grep -E '\.(rs|ts|py|go|rb|ex)$' \
  | xargs grep -nE "std::env::var|process\.env|os\.environ|ENV\[" 2>/dev/null

# (run one grep per invariant — see pr-audit § Phase 2 for the recipes)
```

Hits in changed files that violate an invariant → `[BLOCKING]`,
even if no single PR introduced both halves.

### 3.2 Helper drift

Did two PRs add similar helpers in different modules? Look for
near-duplicate function signatures across new code:

```bash
# Cheap heuristic: list new pub fns added in the batch
git diff $RANGE | grep -E "^\+\s*(pub|export|def|func)\s+(fn |function |async )?\w+" \
  | sort | uniq -c | sort -rn | head -20
```

Two PRs each adding `derive_project_name` / `derive_name_from_cwd`
in different crates → `[SHOULD-FIX]`. Consolidate.

### 3.3 Config drift

Did multiple PRs in the batch add fields to the same `Config` /
`Settings` / `AppState` struct, each consistent in isolation but
compounding? Run:

```bash
git diff $RANGE -- '**/config*' '**/settings*' '**/state*' \
  | grep -E "^\+\s*pub\s+\w+:\s+" | head -20
```

More than 3 new fields in one struct, across PRs that didn't
coordinate → `[SHOULD-FIX]`. The struct may need a sub-grouping
pass or a builder.

### 3.4 Behaviour-change compounding

Did multiple PRs change defaults of the same surface (a CLI flag,
a config default, a wire format)? Cross-check by grepping the
batch's commit messages and PR bodies for keywords:

```bash
for sha in $(git log $RANGE --merges --format=%H); do
  git log -1 --format="%H %s%n%b" $sha \
    | grep -iE "default|now defaults|previously|breaking|changed behaviour"
done
```

Two PRs both nudging the same default → `[BLOCKING]` (last-PR-wins
without explicit coordination is rarely intentional).

### 3.5 Test-budget ratio

```bash
TESTS_DELTA=$(git diff $RANGE | grep -cE "^\+\s*(#\[(test|tokio::test)\]|test\(|it\(|describe\()")
LOC_ADDED=$(git diff $RANGE --shortstat | grep -oE "[0-9]+ insertion" | grep -oE "[0-9]+")
echo "tests added: $TESTS_DELTA  /  LoC added: $LOC_ADDED  →  ratio: $((TESTS_DELTA * 1000 / LOC_ADDED))/1000"
```

Heuristic: under **5 tests per 1000 LoC** is suspect. Either the
batch is mostly mechanical refactor (legit) or test coverage is
trailing the feature surface. Drill in.

### 3.6 Two-pass agent fan-out

For batches > 1000 LoC OR > 5 PRs, run agents:

- **Pass 1** — per-area agents, one per crate / package / app
  (same prompt template as `pr-audit` § Templates).
- **Pass 2** — a single synthesis agent that reads all the per-area
  reports and looks for **cross-area interactions only**. This is
  the load-bearing call this skill is built around.

Template for the synthesis agent is in **§ Templates** below.

---

## Phase 4 — Doc-staleness sweep

Every behaviour change / new flag / new endpoint / new tool in the
batch maps to a doc grep. Do this **mechanically**, one item at a
time:

```bash
# For each user-facing surface added in the batch (build the list
# from PR bodies + CHANGELOG diffs):
for surface in "AI_MEMORY_BASE_PATH" "--web-slug" "/favicon.ico" "memory_delete_page"; do
  echo "== $surface =="
  grep -rn "$surface" docs/ README.md README.rst doc/ 2>/dev/null \
    | head -3
done
```

A surface with zero hits in `docs/` + `README` → `[SHOULD-FIX]`
under a Doc-staleness sub-section.

A doc that describes the **old** behaviour after a default
changed → `[BLOCKING]` (actively misleads users).

---

## Phase 5 — CHANGELOG completeness

Not "is there an entry" — "is there an entry **for every PR in the
batch**?"

```bash
# Each PR in the batch
gh pr list --search "merged:>$LAST_RELEASE" --json number,title

# Each [Unreleased] entry's `[#NN]` ref
grep -oE "#[0-9]+" CHANGELOG.md | head -20
```

Diff the two sets. Any PR number missing from `[Unreleased]` →
`[SHOULD-FIX]`. Add it as part of P2.

---

## Phase 6 — Phased fixes

Every fix commit starts with the phase label so `git log --grep="\bP[123]\b"`
turns up the audit history later.

### P1 — BLOCKING (correctness + invariants)

One commit per BLOCKING. Run CI between each. Each commit message
starts with `fix(audit-P1): <one-line>`.

### P2 — SHOULD-FIX (cleanup + coverage)

Batched **by concern**, not by PR. Group like:

- One commit for missing test coverage gaps (across PRs)
- One commit for doc-staleness fixes (across PRs)
- One commit for CHANGELOG completeness (single commit, all entries)
- One commit per helper consolidation / refactor

Each commit message starts with `fix(audit-P2): <concern>` or
`refactor(audit-P2): <concern>`.

### P3 — NIT (cosmetic)

**Single commit, batched.** Five nits don't deserve five commits.
Message: `chore(audit-P3): batched nits — <list>`.

After each phase: re-run baseline gates, record the test count
delta vs the phase-start baseline. A test count that DROPPED
without justification → halt; investigate.

---

## Phase 7 — Combined live test (if deployable)

Per-PR live tests don't catch combination bugs. If the repo has a
`bin/deploy` (or equivalent) and any PR in the batch touched runtime
behaviour:

```bash
bin/deploy
source bin/deploy.env  # whatever the deploy env looks like
ssh "$SERVER" "<health-check command for the project>"
# Smoke test ONE end-to-end user path that crosses two of the merged PRs.
```

The smoke test is the point — pick a path that exercises features from
multiple PRs in the batch, not just one. Report version banner +
health status.

---

## Phase 8 — Version bump decision

Codified, not vibes:

| Batch contains | Bump |
|---|---|
| Any breaking change | **major** (or pre-1.0: minor with `### Breaking` note) |
| Any new flag / env var / endpoint / public API / MCP tool / behaviour change | **minor** |
| Bug fixes / docs / internal refactors only | **patch** (or defer) |

Ask the user explicitly:

> "Batch contents → recommended bump: **minor (X.Y → X.{Y+1}.0)**.
> Cut now via `bin/release X.{Y+1}.0`, or sit on it for the next
> intentional release?"

Never run `bin/release` without explicit approval.

---

## Phase 9 — Post-mortem to memory (optional)

If the cross-PR sweep surfaced a **recurring pattern** (the third
batch in a row where Config gained 2+ uncoordinated fields, every
batch forgets CHANGELOG, every batch ships a doc-link to a file
that doesn't exist), record it as a feedback memory:

> "After [N] consecutive batches, the same class of finding keeps
> appearing. Should we adjust the per-PR template or the gate?"

This is the only way the skill compounds session-over-session.

---

## Output format

```
## Post-audit — batch [<range>] across N PRs

**Baseline:** format ✓  lint ✓  tests <N>  (LoC delta: +<X>, deps Δ: <list or none>)

**PRs in batch:**
- #N — <title>
- #M — <title>
- ...

**Cross-PR findings (Phase 3):**

### Invariant matrix
- [SEVERITY] file:line — what's wrong, naming both PRs whose
  combination introduced it
- (or "none found.")

### Helper drift
- ...

### Config drift
- ...

### Behaviour-change compounding
- ...

### Test-budget ratio
- ratio: <X> tests / 1000 LoC. <"healthy" / "thin — drill in">

### Synthesis (Pass 2)
- ...

**Doc staleness (Phase 4):**
- [SEVERITY] surface — missing from / stale in <doc path>

**CHANGELOG completeness (Phase 5):**
- Missing [Unreleased] entries for: #N, #M

**Phased fix plan:**
- P1: <N commits>
- P2: <N commits, batched by concern>
- P3: <1 commit>

**Live test:** <skip / planned target / done — result>

**Version bump:** <patch / minor / major>. Cut now or defer?
```

---

## Templates

### Synthesis-pass agent prompt (Phase 3.6 Pass 2)

```
You are the synthesis-pass auditor for a batch of <N> PRs that
landed between <range>. Each per-area agent has already audited
its slice; their reports are pasted below.

Your job is NOT to re-audit individual PRs. Your job is to find
issues that emerge from the COMBINATION — things no single per-area
report could see:

1. Did two PRs add similar / duplicate helpers in different modules?
2. Did two PRs both touch the same cross-cutting invariant from
   different angles, building a bridge that violates it together?
3. Did multiple PRs change defaults on the same surface without
   coordinating?
4. Did the Config / Settings / AppState struct grow uncoordinated
   fields?
5. Are there doc-staleness or CHANGELOG gaps that only show when
   you cross-reference the per-area reports?

Each per-area report is below.

<paste all reports>

Output (under 400 words):

### Cross-area findings
- [SEVERITY] PRs #A and #B together — <description, with file refs>

If you find none, write "none found across areas." No padding.
```

### Reply template — closing the audit (no fix needed)

```
Cross-PR audit on batch [<range>] across <N> PRs.

No cross-area findings. Each PR audited individually, no
combination effects detected. CHANGELOG complete; docs in sync.

Recommended bump: <tier>. Cut now or defer?
```

### Reply template — phased fix plan announcement

```
Cross-PR audit found:
- <N> BLOCKING (P1)
- <N> SHOULD-FIX (P2, batched by concern)
- <N> NIT (P3, single commit)

Plan: address P1 → P2 → P3 sequentially, CI between each phase.
Each fix commit starts with `<type>(audit-PN): …` so the trail
stays grep-able.

ETA on the whole pass: <rough estimate>. Proceed?
```

---

## Hard NOs

- **No fix commits without a phase label.** Every commit message
  in the fix phases starts with `<type>(audit-P[123]): …`.
- **No P1 + P2 in the same commit.** Phase separation is the
  point of the workflow.
- **No nit-thrashing.** Five NITs = one commit, batched.
- **No auto-release.** Phase 8 surfaces the recommendation; the
  operator runs `bin/release` (or skips).
- **No skipping the synthesis pass on a > 1000 LoC batch.**
  The whole point of this skill is the cross-area view.
- **No silent test-count drops.** If tests decrease without
  explicit justification ("removed dead test X"), halt and
  investigate before continuing.

---

## When to invoke this skill vs. `pr-audit`

| Situation | Skill |
|---|---|
| One PR up for review, not yet merged | `pr-audit` |
| Three PRs from yesterday already merged, want a once-over | `pr-post-audit` |
| About to cut a release | `pr-post-audit` (covers Phase 8) |
| Multiple PRs landed but you want each evaluated independently | `pr-audit` × N (per-PR gate) |
| Reviewing a single mega-PR | `pr-audit` (with its own internal fan-out) |
| "Audit what we shipped this week" | `pr-post-audit` with `--since='7 days ago'` |
