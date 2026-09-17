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
   verified fact undermines an opinion's premise (a deal breaker for the
   article's conclusions), STOP: flag it in a separate "confirm before
   rewriting" section and wait for the user's decision.
2. **Pass 1 auto-applies fixes by default.** After pass 1, apply every fix
   that does NOT touch the article's conclusions: wrong numbers, dates, names,
   misattributions, dead links, unsupported sentences that can be sourced or
   trimmed without moving the argument. Only deal breakers (a verified fact
   that pulls the thread of a conclusion) wait for the user. Pass 2 always
   reports first and asks before touching anything it finds.
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

## Fast path (two passes, always)

```
Phase 0  Setup: locate file(s), choose harnesses (pass 1 + pass 2, config/models.json)
Phase 1  Extract: read article, build claims.json + argument map
Phase 2  PASS 1: scripts/fanout.py with the first harness (default: grok)
Phase 3  Audit: your own hostile logic/consistency pass (no web)
Phase 4  Report pass 1: auto-fix everything that does not touch the
         conclusions (humanizer on changed prose for blog posts); only deal
         breakers for the article's conclusions wait for the user
Phase 6  PASS 2: re-extract claims from the FIXED article, fanout.py with the
         second harness (default: claude)
Phase 7  Final report: new findings from pass 2 + verification that pass-1
         fixes actually landed -> confirm with user before fixing -> apply
```

Two passes are mandatory, never parallel: pass 1 (cheap harness) finds the
breakage, approved fixes land, then pass 2 (stronger harness) audits the
corrected article with clean context. Running both harnesses on the same
pre-fix text wastes the second pass on findings that are already fixed.
Re-extract claims before pass 2 (Phase 1 again on the fixed file) because
fixed sentences change the quoted text the checkers verify.

## Phase 0 — Setup

- Resolve the article path. If it is a Hugo post with an `index.en.md`
  sibling, the PT `index.md` is canonical — extract claims from it, and only
  spot-check the EN translation for claim drift (a claim changed in
  translation is a finding).
- Pick the harnesses: pass 1 defaults to `config/models.json`
  `default_harness` (currently `grok`, default model, cheap per check); pass 2
  defaults to `second_pass_harness` (currently `claude`, session default
  covered by the Max subscription). Override per run with `--harness`/
  `--model`/`--variant` when the user asks for specific harnesses or the
  defaults are unavailable (check auth first: `references/harness-setup.md`).
  Harness auth/setup: `references/harness-setup.md`.
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

## Phase 2 — Fan out verification (pass 1)

```sh
python3 <skill-dir>/scripts/fanout.py \
  --claims /tmp/fact-check/<run>/claims.json \
  --out-dir /tmp/fact-check/<run>/pass1 \
  --title "Article title" --lang pt-BR \
  --harness grok --batch-size 6 --parallel 3
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

## Phase 6 — Pass 2 (fixed article, second harness)

After the user approves pass-1 fixes and they land (Phase 5), re-run Phase 1
on the FIXED article into `claims-pass2.json` (quotes drift when fixes change
sentences), then fan out again with the pass-2 harness:

```sh
python3 <skill-dir>/scripts/fanout.py \
  --claims /tmp/fact-check/<run>/claims-pass2.json \
  --out-dir /tmp/fact-check/<run>/pass2 \
  --title "Article title" --lang pt-BR \
  --harness claude --batch-size 6 --parallel 3
```

Pass 2's report (Phase 7) focuses on what pass 1 missed or what the fixes
broke; re-verify that every approved pass-1 fix actually shipped.

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

## Phase 4 — Pass 1 report + auto-fix

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
proposed minimal fix.

Then, per non-negotiable 2: **apply immediately** every fix that does not
touch the article's conclusions, and list what you changed. The report ends
with:

1. **✅ Auto-fixed** — the S1/S2/S4/S6 items already applied, one line each.
2. **⚠ Confirm before rewriting (deal breakers)** — items where a verified
   fact undermines an opinion's premise or the article's conclusions. State
   the tension plainly and ask the user to decide. Only these wait.
3. Totals per severity, plus tokens/cost spent (from `cost_report.md` /
   `summary.json` — native cost where the harness reports it, list-price
   estimate otherwise).

Then proceed to Phase 6 (pass 2) without waiting, unless deal breakers are
pending — unresolved deal breakers block pass 2, since pass 2 audits the
fixed article and the fix is undecided.

## Phase 5 — Apply fixes

- Fix exactly the approved items (user-confirmed, or auto-approved under
  non-negotiable 2 in pass 1) with minimal edits preserving voice.
- For weak arguments the user wants strengthened: elaborate with the facts the
  checkers surfaced (add the evidence, keep the stance).
- Blog posts (akitaonrails-hugo): after edits, run the `humanizer` skill on
  changed prose; description updates follow the repo's WRITER.md gate.
- Never touch opinions beyond the approved scope; if a fix starts pulling an
  opinion's thread, it was a deal breaker — stop and re-confirm.

## Hygiene

- Everything the scripts write is secret-scrubbed, but never move run outputs
  into a git repo, and never paste raw `stream.ndjson` into chat.
- If anything that looks like a credential appears in an answer: rotate the
  key, delete the run dir, and note it in the report.
