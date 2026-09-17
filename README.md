# my-skills

> **These are Fabio Akita's personal skills** — custom-tailored to his
> machines, subscriptions, and workflow. They are published for reference and
> inspiration. Treat them as examples of what a skill can look like, then ask
> your own LLM to write skills for your exact needs. Avoid reusing other
> people's skills verbatim: they carry someone else's assumptions, paths, and
> credentials layout.

Single master repository for my agent skills, shared across every AI agent CLI
on this machine. Each harness's `skills/` directory stays a **real directory**
whose entries are symlinks into this repo — so one edit here reaches all of them.

## Layout

Flat: one directory per skill, each with a `SKILL.md`.

## Consumers

| Harness | Skills directory | How it links |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | per-skill symlinks |
| Codex | `~/.codex/skills` | per-skill symlinks |
| opencode | `~/.config/opencode/skills` | real dir: per-skill symlinks + opencode-only entries |
| opencode (checkout) | `~/opencode/.opencode/skills` | per-skill symlinks |
| Kimi | `~/.kimi-code/skills` | whole-dir symlink → this repo |
| shared | `~/.agents/skills` | per-skill symlinks |
| alias | `~/skills` | symlink → `~/.claude/skills` |

Per-skill symlinks rather than replacing each `skills/` with one directory
symlink: the harness directories also hold entries that must **not** live here
(see below), and per-skill links let those sit alongside untouched.

## Deliberately NOT in this repo

- **`omarchy`, `diagnose-crash`** — package-owned, symlinked from
  `/usr/share/omarchy/default/agents/skills/`. Owned by the omarchy package and
  replaced on update.
- **`oh-my-opencode-slim`** — opencode-only: the plugin (registered in
  `~/.claude.json` telemetry aside, it runs solely inside opencode) and its
  config skill live in `~/.config/opencode/skills/` as a real directory, not
  shared through `~/.claude/skills`.
- **`assess-team`, `assess-partners`** — their own git repos, hosted on a
  private remote. **This repo is public**; assessment methodology, templates
  and reports must not be published here. The seven `assess-*` skills are
  nested inside `assess-team/skills/`.
- **`.system`** — Codex-internal.
- Vendor bundles: `~/.grok/bundled/skills`, `~/.config/crush/anthropic_skills/`,
  `~/.gemini/antigravity-cli/builtin/skills`.

## External components (inventory + update procedure)

Third-party skills and plugins installed around this repo. None of them
auto-update; re-check occasionally.

| Component | Source | Where it lives | Update procedure |
| --- | --- | --- | --- |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | vendored in this repo (`humanizer/`) | re-pull upstream, strip `.git`, run `python3 humanizer/scripts/validate-package.py` |
| simplify | adapted from Addy Osmani's [agent-skills](https://github.com/addyosmani/agent-skills) | this repo (`simplify/`) | one-time adaptation; diff upstream manually when it drifts |
| codemap, clonedeps | oh-my-opencode-slim heritage | this repo | local forks — no upstream sync |
| oh-my-opencode-slim | npm `oh-my-opencode-slim` | opencode plugin (`~/.config/opencode/opencode.json`) + config skill in `~/.config/opencode/skills/` | `opencode plugin oh-my-opencode-slim` run from a non-repo dir (it writes local scope otherwise), restart opencode |
| opencode-openai-codex-auth | npm | opencode plugin | same as above |
| agent-browser | npm `agent-browser` (mise node global) | CLI + `~/.config/opencode/skills/agent-browser/` | `npm i -g agent-browser@latest`, then copy the package's `skills/agent-browser/SKILL.md` over the installed skill |
| Claude Code plugins (clangd-lsp, frontend-design, rust-analyzer-lsp, typescript-lsp) | claude-plugins-official | `~/.claude.json` | `claude plugin update <name>` |
| Claude synced skills (skill-creator, docs, pdf, …) | claude.ai cloud sync | `~/.claude/skills/synced/` | managed by account sync |
| omarchy, diagnose-crash | omarchy package | symlinks into `/usr/share/omarchy/default/agents/skills/` | omarchy system updates |
| Grok / crush / Antigravity bundled skills | ship with the tool | `~/.grok/bundled/skills`, `~/.config/crush/anthropic_skills/`, `~/.gemini/antigravity-cli/builtin/skills` | update the tool |

Last checked 2026-09-17 — humanizer 3.0.0 (up to date), oh-my-opencode-slim
2.2.21 stable (beta line 3.0.0-beta.13 available), opencode-openai-codex-auth
4.4.0, agent-browser 0.38.1, all four Claude plugins latest.

## Rules

`.gitignore` blocks `.venv/`, `__pycache__/`, binaries (`*.pdf`, images,
archives), and credential-shaped files (`.env`, `*.key`, `*token*`,
`*secret*`). Assessment PDFs and anything resembling a key or token must never
be committed here — the repo is public.

`humanizer` is vendored from <https://github.com/blader/humanizer> with its
`.git` stripped. Re-pull upstream manually if it needs updating.

## Adding a skill

```sh
mkdir ~/Projects/my-skills/<name>          # add SKILL.md
for h in ~/.claude/skills ~/.agents/skills ~/.codex/skills ~/opencode/.opencode/skills; do
  ln -s ~/Projects/my-skills/<name> "$h/<name>"
done
```

Harnesses read `SKILL.md` at startup, so restart a running agent to pick up a
newly added skill.
