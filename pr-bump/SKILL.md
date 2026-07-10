---
name: pr-bump
description: Merge Dependabot gem/dependency bump PRs quickly and safely. Use when the user says opened PRs, Dependabot, gem updates, bump PRs, test, push, close, or deploy dependency-only pull requests.
---

# PR Bump

Use this workflow to clear routine Dependabot dependency bump PRs without
breaking the app or accidentally shipping unrelated local changes.

The common case is a set of Bundler/Ruby gem update PRs that only touch
`Gemfile.lock`. Prefer a single local consolidated lockfile update over merging
each Dependabot branch one by one.

## Fast Path Summary

1. Inspect local git state and open PRs.
2. Confirm every PR is a dependency-only bump.
3. Consolidate all bumps locally with the package manager, updating each
   dependency to the latest resolvable version rather than the PR's exact target.
4. Run local CI-equivalent checks.
5. Commit only intended files with `Closes #N` references.
6. Push, confirm PRs closed, and wait for GitHub CI.
7. Deploy only after CI passes when the user asked for deploy.

## Preconditions and Guardrails

- Never commit unrelated local changes. If `git status` shows files like
  `.ai-jail`, inspect them and leave them unstaged unless the user explicitly
  asks to include them.
- Before committing, inspect:
  - `git status --short --branch`
  - `git diff --stat`
  - `git diff -- <intended files>`
  - `git log --oneline -10`
- If a deploy command builds from the working tree, temporarily stash unrelated
  local files that would enter the build context, then restore them after
  deploy. This avoids shipping local scratch config.
- Do not run broad auto-formatters as a fix for dependency PRs. If lint fails
  on pre-existing style, prefer a tiny config or targeted fix. If an
  autoformatter changes dozens of files, revert it and narrow the fix.
- If any PR changes application code, migrations, Docker files, or config that
  is not clearly dependency metadata, stop and do a normal PR review instead.

## Step 1: Inspect Open PRs

Use GitHub CLI:

```bash
gh pr list --state open \
  --json number,title,headRefName,baseRefName,author,labels,mergeStateStatus,isDraft,updatedAt,url
```

For each candidate PR:

```bash
gh pr diff <number> --name-only
gh pr view <number> --json commits,files,statusCheckRollup,mergeable,mergeStateStatus
```

Safe routine PR signals:

- author is `app/dependabot` or `dependabot[bot]`
- label includes `dependencies`
- title is a simple bump, e.g. `Bump bootsnap from 1.24.5 to 1.24.6`
- changed files are dependency metadata only, commonly `Gemfile.lock`
- bump type is patch/minor unless the project has already accepted the major
  and tests are strong enough

Branch CI may be failing because Dependabot updated a partial/stale lockfile
and Bundler frozen mode rejects it. Inspect the logs, but don't assume the bump
is bad until a consolidated local update fails.

## Step 2: Consolidate with the Package Manager

For Bundler/Ruby gems, update all open bump gems together on the current default
branch. Do **not** merely apply the exact version from the Dependabot PR. Treat
the PR as a signal that the dependency needs attention, then let Bundler resolve
the latest compatible version under the existing `Gemfile` constraints:

```bash
bundle update <gem_one> <gem_two> ...
bundle check
```

This resolves lockfile conflicts and refreshes transitive dependency checksums
correctly. It may update small transitive dependencies, such as `msgpack` for
`bootsnap`; include those in the final summary.

The goal is "latest safe/resolvable", not "the PR's proposed version". This
reduces churn from repeated tiny follow-up bumps. For Bundler, `bundle update
<gem>` normally means the newest version the dependency graph and existing
Gemfile constraints allow.

Do not widen `Gemfile` constraints, jump to a new major version, or make
application changes just to chase an upstream latest unless the user explicitly
asks. If the true upstream latest requires changing constraints, stop and report
that the latest compatible version was applied and what would be required to go
further.

Do not merge each Dependabot branch if several lockfile PRs are open and likely
to conflict. A single consolidated commit with `Closes #N` references is faster
and produces a clean lockfile.

## Step 3: Verify Locally

Run the project’s CI-equivalent checks from its instructions. For this Rails
project, the tested command set is:

```bash
bundle check
RAILS_ENV=test \
  ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY=0123456789abcdef0123456789abcdef \
  ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY=abcdef0123456789abcdef0123456789 \
  ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT=0123456789abcdef0123456789abcdef \
  bin/rails db:test:prepare test
bin/rubocop -f github
bin/brakeman --no-pager
bin/bundler-audit
```

Run independent checks in parallel when possible, but make sure `bundle check`
or installation succeeds first.

If tests fail:

1. Reproduce the failing subset locally.
2. Determine whether the failure is caused by the dependency change, CI env, or
   pre-existing test fragility.
3. Make only minimal robust fixes.
4. Re-run the focused test and the full CI-equivalent command set.

Known CI-hardening patterns from this project:

- Tests that instantiate API clients must set fake API keys before client
  construction, then restore the original `ENV` value in teardown.
- GitHub Actions test jobs need deterministic Active Record encryption env vars.
- If Docker deploy builds from working tree, stash local `.ai-jail` changes so
  the image matches committed code.

## Step 4: Commit and Push

Stage only intended files, usually just `Gemfile.lock`:

```bash
git add Gemfile.lock
git diff --cached --stat
git diff --cached
git commit -m "Bump <gem_one> and <gem_two>" -m "Closes #<pr1>. Closes #<pr2>."
git push origin master
```

If you made tiny CI/test hardening fixes, stage those explicitly in a separate
commit with a specific message. Keep dependency and test-infra changes easy to
audit.

After push:

```bash
gh pr list --state open --json number,title,url
gh run list --branch master --limit 5 --json databaseId,status,conclusion,headSha,displayTitle,event,createdAt,url
gh run watch <push-ci-run-id> --exit-status
```

Do not deploy until the relevant push CI run passes, unless the user explicitly
accepts that risk.

## Step 5: Deploy When Requested

Use the project’s deploy command. For this Rails project:

```bash
bin/deploy
```

If unrelated local changes would be included in the Docker build context,
temporarily stash them and restore afterward. In zsh, do not use a variable
named `status` because it is read-only. Use `deploy_rc`:

```bash
stash_created=0
if ! git diff --quiet -- .ai-jail; then
  git stash push -m opencode-temp-pr-bump-deploy -- .ai-jail
  stash_created=1
fi

bin/deploy
deploy_rc=$?

if [ "$stash_created" = 1 ]; then
  git stash pop
fi

exit "$deploy_rc"
```

A successful `bin/deploy` should build, push the `latest` image, restart remote
Compose services, and show the app container healthy plus worker/fetcher up.

## Final Response Checklist

Report concisely:

- PR numbers closed
- direct and transitive dependency versions changed, noting when the final
  version is newer than Dependabot's proposed PR version
- local checks run and pass/fail result
- GitHub CI result
- deploy result and service health
- any remaining local uncommitted changes intentionally left alone

Example final note:

```md
Done.

- Closed PRs #29 and #30.
- Updated bootsnap 1.24.5 -> 1.24.7 (newer than PR target 1.24.6), image_processing 2.0.1 -> 2.0.3, msgpack 1.8.0 -> 1.8.1.
- Local tests, RuboCop, Brakeman, and bundler-audit passed.
- GitHub CI passed.
- Deployed successfully; app is healthy, worker and mail fetcher are up.
- `.ai-jail` still has uncommitted local changes and was left untouched.
```
