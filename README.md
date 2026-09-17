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
