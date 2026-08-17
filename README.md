# my-skills

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
| opencode | `~/.config/opencode/skills` | symlink → `~/.claude/skills` |
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
- **`oh-my-opencode-slim`** — plugin-managed, registered in `~/.claude.json`.
- **`assess-team`, `assess-partners`** — their own git repos, hosted on a
  private remote. **This repo is public**; assessment methodology, templates
  and reports must not be published here. The seven `assess-*` skills are
  nested inside `assess-team/skills/`.
- **`.system`** — Codex-internal.
- Vendor bundles: `~/.grok/bundled/skills`, `~/.config/crush/anthropic_skills/`,
  `~/.gemini/antigravity-cli/builtin/skills`.

## Rules

`.gitignore` blocks `.venv/`, `__pycache__/`, and binaries (`*.pdf`, images,
archives). Assessment PDFs in particular must never be committed here.

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
