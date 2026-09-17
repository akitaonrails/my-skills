# Harness Setup

How to configure each coding-agent CLI so `scripts/dispatch_checker.py` and
`scripts/fanout.py` can spawn headless checker subagents on it. Adapted from
the `llm-coding-benchmark` harness runners.

**Credential safety first — this repo is public:**

- Tokens NEVER live in this repo. They live in per-harness config files under
  `~/.config` / `~/.zcode` / `~/.codex` / `~/.claude`, or in the zsh secrets
  file (`~/.config/zsh/secrets`, `export NAME=...` lines).
- The scripts read the secrets file only to inject env vars into the child
  process. Every file they write (answers, streams, logs) passes through a
  scrubber that redacts common key shapes and the literal secret values.
- Run outputs default to `/tmp/fact-check/...`, never inside a git repo.
- `.gitignore` in this repo blocks `.env*`, `*.key`, `*token*`, `*secret*`
  patterns. If you suspect a leak: rotate the key immediately, then clean
  history (`git filter-repo`) — scrubbing after the fact is not enough.

## Per-harness cheat sheet

| Harness | Auth | Cheap model suggestion | Web tools | Headless shape |
| --- | --- | --- | --- | --- |
| `zcode` | `zcode login` (Z.AI OAuth) or `~/.zcode/cli/config.json` apiKey | `zai/glm-5.3-flash` (flat rate) | built-in | `--prompt=<text> --cwd=… --mode=yolo --json --verbose` |
| `claude` | Max subscription (`~/.claude/.credentials.json`) or `ANTHROPIC_API_KEY` | `claude-haiku-*` | WebSearch/WebFetch (allowed via flags) | `claude -p --output-format stream-json --allowedTools WebSearch WebFetch Read` |
| `codex` | `codex login` (ChatGPT OAuth → `~/.codex/auth.json`) or `OPENAI_API_KEY` | `gpt-*-flash` variants | `-c tools.web_search=true` | `codex exec --json --ephemeral -s read-only -` (prompt on stdin) |
| `opencode` | `~/.local/share/opencode/auth.json` + provider config (`{env:VAR}` refs) | `openrouter/google/gemini-*-flash-lite`, `openrouter/z-ai/glm-*-flash` | webfetch built-in | `opencode run --format json [-m provider/model]` |
| `kimi` | `KIMI_API_KEY` (Moderato plan) | plan default | built-in | `kimi -p --output-format stream-json` |
| `grok` | `GROK_API_KEY` | plan default | web search ON by default (we omit `--disable-web-search`) | `grok -p --output-format streaming-json --always-approve` |
| `agy` | Google OAuth (Antigravity) | `gemini-*-flash` | built-in | `agy --print <text> --model <id>` |

Env vars the scripts may inject from the secrets file (names only):
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`,
`GROK_API_KEY`, `ZAI_API_KEY`, `KIMI_API_KEY`, `MOONSHOT_API_KEY`,
`QWEN36_API_KEY`, `OLLAMA_API_KEY`.

## New-user setup, one by one

### zcode (default: flat-rate GLM Coding Plan — cheapest default)
1. Install: `npm i -g @zai-org/zcode-cli` (or your package manager's equivalent).
2. `zcode login` → Z.AI account with a GLM Coding Plan.
3. Model: set in `~/.zcode/cli/config.json` → `model.main`. The dispatcher
   rewrites `model.main` per run when `--model` is passed, and restores your
   original value afterwards.

### claude (Claude Code)
1. Install: `npm i -g @anthropic-ai/claude-code` or mise.
2. `claude login` (Max subscription) — credentials land in
   `~/.claude/.credentials.json`. Headless `-p` mode uses the same auth.
   Alternatively set `ANTHROPIC_API_KEY` (pay per token).
3. The dispatcher allow-lists `WebSearch WebFetch Read` and deny-lists
   `Bash Write Edit`, so checkers can research but not modify anything.

### codex (OpenAI Codex CLI)
1. Install: `npm i -g @openai/codex` or mise.
2. `codex login` → ChatGPT OAuth (writes `~/.codex/auth.json`) or set
   `OPENAI_API_KEY`. Plan credits are consumed.
3. Web research is enabled per run with `-c tools.web_search=true`, and the
   sandbox is `-s read-only`.

### opencode
1. Install: `curl -fsSL https://opencode.ai/install | bash` or mise.
2. Auth: `opencode auth login` (writes `~/.local/share/opencode/auth.json`) —
   supports OpenRouter, Anthropic, Google, etc. For OpenRouter set
   `OPENROUTER_API_KEY`.
3. Models are addressed `provider/model` (e.g.
   `openrouter/google/gemini-3.5-flash-lite`). Check `opencode models`.

### kimi / grok / agy (secondary)
- `kimi`: Moonshot `KIMI_API_KEY`; `-p` mode auto-approves tools.
- `grok`: `GROK_API_KEY`; official `@xai-official/grok` CLI package.
- `agy`: Antigravity CLI, Google OAuth (`agy login`), no API key.

## Quirks learned from the benchmark (beware)

- **zcode** headless parser accepts ONLY the `--prompt=<text>` equals form
  (space form and `-p`/`--model` are rejected), buffers ALL stdout until exit
  (stall detection is disabled for it; wall-clock timeout only), and has no
  CLI model flag — model comes from config rewrite (see above).
- **codex** is wrapped in `bash -lc` because installs are often npm/mise shell
  shims; the prompt travels on stdin via the trailing `-` argument.
- **kimi** in `-p` mode prints no usage events (the dispatcher records 0
  tokens) and the process can linger after the final event — the runner kills
  the process group on timeout.
- **claude** cost comes from the final `result` event's `total_cost_usd`;
  subscription auth returns no meaningful cost (tokens still counted).
- **grok**: the benchmark disabled web search for determinism; we re-enable it
  by simply not passing `--disable-web-search`.

## Cost reporting

Every run leaves a cost trail:

- `dispatch_checker.py` writes per-run `result.json` with `tokens_in/out`,
  `cost_usd` (native, when the harness reports it: claude, opencode, grok),
  and `cost_usd_est` (list-price estimate from `config/models.json` rates when
  it doesn't: zcode, kimi, agy). `cost_source` says which.
- `fanout.py` aggregates both into `summary.json` (with a per-batch
  `batches_detail` breakdown) and writes `cost_report.md` — a human-readable
  table (tokens, cost, source, duration per batch + totals) to paste into the
  final report.

Estimates are upper bounds: they ignore cache-read discounts and flat-rate
subscriptions (zcode's GLM Coding Plan, claude Max, codex/kimi plan credits),
so a flat-rate run shows its list-price equivalent, not real spend. The
report's notes section says so. Update `rates_per_m` in `config/models.json`
when pricing changes.

## Troubleshooting

- `command not found` → the CLI is not on PATH for non-interactive shells;
  install via mise or symlink into `~/.local/bin`.
- Checker returns no JSON → inspect `<out>/batch-NN/stream.ndjson` and
  `stderr.log`; usually auth expired (re-run the harness's `login`) or the
  model id is wrong for your plan (`--model` override).
- `no json` in fanout output → the answer lacked a fenced JSON array; re-run
  that batch with a stronger model (`--model ... --variant high`).
