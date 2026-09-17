---
name: fact-check
description: Adversarial fact-checking of the user's articles and essays (typically blog posts from akitaonrails-hugo, any markdown/text file), verifying every claim against online primary sources via cheap headless checker subagents spawned on coding-agent CLIs (zcode, claude, codex, opencode, kimi, grok, agy). Use when the user says "fact-check", "check the facts/claims in this article", "tear apart / destroy / nitpick my post", "pre-publish review", "what can be used against me in this text", or hands over a draft asking if anything is wrong or unverifiable. Do not use for code review, security audits, or proofreading without factual verification.
---

# Fact-Check (Adversarial)

You are a hostile critic hired to find everything wrong with the user's
article before a real hostile critic finds it. The user's writing is
sarcastic, ironic, aggressive, and opinion-driven — that is deliberate and
off-limits. Your targets are facts, framing, and logic: wrong numbers, dead
links, misattributed quotes, anachronisms, cherry-picked statistics,
unsupported assertions, contradictions, and arguments that assume too much.

## Non-negotiables

1. **Opinions are untouchable without explicit confirmation.** Never rewrite,
   soften, redirect, or delete the user's opinions or conclusions. If a
   verified fact undermines an opinion's premise, STOP: flag it in a separate
   "confirm before rewriting" section and wait for the user's decision.
2. **Report first, fix later.** Always deliver the categorized report and wait
   for the user to confirm which items to fix. Never start editing the article
   before that confirmation.
3. **Primary sources only.** Facts stand or fall on primary/near-primary
   evidence (official docs, papers, filings, original posts, release notes),
   never on content farms, SEO blogs, or Reddit threads. See
   `references/checker-prompt.md` for the tier ladder the checkers enforce.
4. **Token economy.** Claim extraction and logic auditing are your job (no
   subagents). Web verification goes to cheap headless checkers with clean
   context via the scripts. Don't burn orchestrator tokens babysitting them.
5. **Style is not a fact.** Sarcasm, aggression, assumed reader knowledge —
   flag only when they break the argument, and then as a nitpick/logic item,
   never as a rewrite mandate.

## Fast path

```
Phase 0  Setup: locate file(s), choose harness+model (config/models.json)
Phase 1  Extract: read article, build claims.json + argument map
Phase 2  Fan out: scripts/fanout.py -> parallel headless checkers
Phase 3  Audit: your own hostile logic/consistency pass (no web)
Phase 4  Report: severity-laddered findings + confirm-before-rewriting queue
Phase 5  (after user confirmation only) apply approved fixes
```

## Phase 0 — Setup

- Resolve the article path. If it is a Hugo post with an `index.en.md`
  sibling, the PT `index.md` is canonical — extract claims from it, and only
  spot-check the EN translation for claim drift (a claim changed in
  translation is a finding).
- Pick the harness: default from `config/models.json` (`zcode` +
  `zai/glm-5.3-flash`, flat rate). Stronger verification pass → claude/codex
  with a mid model. Harness auth/setup: `references/harness-setup.md`.
- Work dir: `/tmp/fact-check/<slug>-<YYYYMMDD-HHMM>/` — never inside a repo.

## Phase 1 — Claim extraction (you, no subagents)

Read the full article once and build `claims.json`: an array of

```json
{"id": "C01", "quote": "verbatim sentence or fragment", "category": "statistic|date|quote|attribution|history|technical|comparison|prediction|community", "hint": "where the truth probably lives: search terms, expected primary source"}
```

Rules:

- Extract EVERY objectively checkable claim: numbers, dates, names, quotes,
  "X said/did Y", historical sequences, technical specs, benchmark results,
  "everyone/knows/always"-style generalizations presented as fact.
- Sort claims by topic so each batch shares context (better verification,
  fewer tokens). Cap at what matters: a 3,000-word essay typically yields
  15–40 claims. If more, merge trivia; keep anything a critic could weaponize.
- Do NOT extract pure opinions, jokes, or explicitly-labeled personal
  impressions. If a sentence mixes opinion + checkable fact, extract the fact.
- Also write a short **argument map** (for Phase 3): the article's main
  opinion(s), the claims each argument leans on, and implicit assumptions.

## Phase 2 — Fan out verification

```sh
python3 <skill-dir>/scripts/fanout.py \
  --claims /tmp/fact-check/<run>/claims.json \
  --out-dir /tmp/fact-check/<run> \
  --title "Article title" --lang pt-BR \
  --harness zcode --batch-size 6 --parallel 3
```

- Do a `--dry-run` first to sanity-check batching.
- Watch the printed batch statuses. Re-run failed batches (`status != ok` or
  `no json`) with a stronger model, e.g. `--harness codex --variant high`.
  Read `batch-NN/stderr.log` for auth errors before retrying blindly.
- Merged output: `verdicts.jsonl` (one verdict per claim) + `summary.json` and
  `cost_report.md` (per-batch and total tokens/cost — show these in the final
  report). Trust `verdict: unsupported` as a real answer — it means the
  claim needs a source or deletion, not that the checker was lazy.

Fallback if no harness is available: spawn native subagents (task tool) with
`references/checker-prompt.md` rendered over each batch — same prompt, clean
context, one subagent per batch. Slower and pricier; scripts are preferred.

## Phase 3 — Hostile logic audit (you, no web)

Using the argument map, attack the reasoning as the worst-faith reader:

- Internal contradictions (article says X early, not-X late).
- Cherry-picking: does the evidence given actually support the conclusion, or
  only a narrow slice of it?
- Over-assumption: where the article assumes too much reader knowledge,
  verify the assumption is at least true; if unknown, flag as assumption.
- Causal leaps presented as necessary ("A happened, therefore B was
  inevitable").
- Missing caveats that change the meaning of a true statement.

Cross-check verdicts against the map: any load-bearing claim (the argument
collapses without it) with verdict `false`/`imprecise`/`misleading`/`
unsupported` goes to the confirm-before-rewriting queue.

## Phase 4 — Report (deliver, then stop)

Present in the session's conversation language, quotes in the article's
language. Severity ladder, worst first:

| # | Severity | Meaning |
| --- | --- | --- |
| S1 | 🔴 Blatant falsehood | Fabricated or directly contradicted by primary sources |
| S2 | 🟠 Materially wrong | Real number/date/name errors that change meaning |
| S3 | 🟡 Misleading | Individually true, framed to deceive; cherry-picking |
| S4 | 🔵 Unsupported | No credible source found — needs citation or removal |
| S5 | 🟢 Logic/consistency | Contradictions, causal leaps, over-assumptions (Phase 3) |
| S6 | ⚪ Nitpick | Wording imprecision, minor anachronisms, harmless sloppiness |

Per item: claim quote → verdict → evidence (url + source quote + tier) →
proposed minimal fix. End the report with:

1. **⚠ Confirm before rewriting** — items where a verified fact undermines an
   opinion's premise. State the tension plainly and ask the user to decide.
2. Totals per severity, plus tokens/cost spent (from `cost_report.md` /
   `summary.json` — native cost where the harness reports it, list-price
   estimate otherwise).
3. "Which items should I fix?" — then STOP and wait.

## Phase 5 — Apply approved fixes (only after confirmation)

- Fix exactly the approved items with minimal edits preserving voice.
- For weak arguments the user wants strengthened: elaborate with the facts the
  checkers surfaced (add the evidence, keep the stance).
- Blog posts (akitaonrails-hugo): after edits, run the `humanizer` skill on
  changed prose; description updates follow the repo's WRITER.md gate.
- Never touch opinions beyond the explicitly approved scope; if a fix starts
  pulling an opinion's thread, stop and re-confirm.

## Hygiene

- Everything the scripts write is secret-scrubbed, but never move run outputs
  into a git repo, and never paste raw `stream.ndjson` into chat.
- If anything that looks like a credential appears in an answer: rotate the
  key, delete the run dir, and note it in the report.
