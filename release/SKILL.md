---
name: release
description: Cut and publish a project release — verify or derive the version number (patch/minor/major) from the changelog and accumulated changes, follow the repo's own branch and versioning strategy, rebase release branches from main/master before tagging, run pr-post-audit when commits have accumulated since the last release, and tag/publish only on green CI at the exact release SHA. Use when the user asks to release, cut/ship/publish/tag a version ("release 2.1", "cut a minor", "ship a patch", "publish the release"), or finalize a changelog for a version. Not for oh-my-opencode-slim release candidates — that is release-smoke-test.
---

# Release

Turn an accumulated mainline into a tagged, published version. This skill is
the explicit "ship it" step that `github-resolution` deliberately separates
from resolving tickets: it runs only when the user asks for a release.

## Preconditions

1. An explicit release ask from the user — ideally with the intended version
   or bump level ("release 3.2", "cut a minor"). Never cut a release nobody
   asked for.
2. The intended work is already merged: approved tickets resolved and closed
   by `github-resolution`, hosted CI green on the mainline head.
3. Working tree clean or unrelated local changes understood and excluded:
   `git status --short --branch`.

## Phase 1: Version selection

1. Find the last release: `git tag --sort=-v:refname | head`, `git describe
   --tags --abbrev=0`, plus the changelog's latest versioned section.
2. Classify everything accumulated since that tag using the project's own
   changelog headings (the same rule `github-resolution` applies): bug fix →
   patch, additive capability → minor, breaking change (format, public
   API/CLI/wire contract, removed surface) → major.
3. Reconcile with the user's ask:
   - User named a number → verify it matches the classification. A mismatch
     (breaking entries but a minor was asked for, or vice versa) is a
     stop-and-confirm, never a silent bump in either direction.
   - User gave only a level ("cut a minor") → derive the number and state it
     before proceeding.
   - User gave nothing → derive from classification and state it before
     proceeding.

## Phase 2: Branch and versioning strategy

Detect the repo's strategy — stated policy always wins:

- Read CONTRIBUTING/README/AGENTS release sections.
- `gh repo view --json defaultBranchRef`, `git branch -r`: look for
  `release/*`, `develop`, `next`, and version maintenance branches
  (`1.x`, `v2`).

Then follow the flow the project actually uses:

- **Single mainline + tags (the common default):** the release is cut from
  `main`/`master` directly. No release branch to manage.
- **Release branch flow:** before tagging anything, bring the release branch
  up to date with `main`/`master` — rebase it (`git rebase <default>`) when
  the branch is yours alone, or merge the default branch into it when the
  branch is shared and the project forbids force-pushing. Resolve conflicts
  deliberately, re-run the full gate on the reconciled tree, and only then
  treat it as the release candidate. Releasing from a stale release branch
  ships old code — the rebase/merge is not optional.
- **Maintenance/backport flow (urgent patch on top of a released major):**
  fixes must already exist on the mainline; cherry-pick them onto the
  maintenance branch cut from the last release tag, tag the patch from that
  branch, and let the branch go dormant afterward.

## Phase 3: Pre-release audit gate

Count the commits accumulated since the last release tag:

```bash
git rev-list --count "$(git describe --tags --abbrev=0)"..HEAD
```

- **1–2 commits:** skip `pr-post-audit` — record the count and the skip in
  the final report.
- **More than 2 commits:** run `pr-post-audit` over the range
  (last release tag → release candidate) before tagging. Fix anything it
  finds, then re-run it. Only a clean post-audit unlocks the tag.

## Phase 4: CI gate

- If the repo has proper CI: release only on green at the EXACT release SHA.
  Wait for the relevant jobs; never treat pending or skipped jobs as passing.
  A release-bound candidate needs the full cross-platform / cross-target
  matrix green on that SHA before tagging — a mainline gated only on the fast
  subset is not proven for release (see `pr-post-audit`).
- If the repo has no CI: run the full local gate once on the exact release
  tree and state plainly in the report that hosted CI was absent.

## Phase 5: Cut and publish

1. Bump the version where the project keeps it (manifest, version file,
   lockfile, changelog) using the repo's own convention — no invented
   schemes.
2. Finalize the changelog: move the Unreleased/pending section under the new
   version with the release date; the Unreleased section left empty for the
   next cycle.
3. Commit the release metadata, then create an **annotated** tag on the
   verified SHA. Push the branch (if any) first, then the tag. Never rewrite
   or force-push a published tag.
4. Publish: if the repo has a tag-driven pipeline, watch it build and
   publish the artifacts from the tag; otherwise create the GitHub release
   with notes taken from the changelog section (keep-a-changelog style if the
   repo uses it).

## Phase 6: Verify and report

Verify the released thing exists: tag visible on the remote, artifacts /
package version resolvable (registry, release page, download URL), version
endpoint answering if the project has one. Then report:

```markdown
## Release vX.Y.Z

- Version rationale: <classification of accumulated changes + user ask>
- Strategy: <single mainline + tag | release branch (rebased/merged from <default> at <SHA>) | maintenance backport>
- Commits since last release: <N> — pr-post-audit: <run clean | skipped (N ≤ 2)>
- CI: <green on <SHA> (jobs) | full local gate, no hosted CI>
- Tag: <tag> on <SHA> — published: <artifact links / release URL>
- Verification: <tag on remote, artifact/version checks>
```

## Hard rules

- Never tag on red, pending, or skipped CI.
- Never cut a release the user did not ask for, at a number they did not
  confirm.
- Never release from a release branch that was not rebased/merged from
  `main`/`master` first.
- Never rewrite published tags or release history.
- A surprise (version mismatch, strategy ambiguity, unexpected commits in the
  range) is a stop-and-confirm, not a judgment call.
