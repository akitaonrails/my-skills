---
name: blog-cost-charts
description: Generate dark-themed cost-vs-score bubble scatter charts and score/(cost*time) value-ranking bar charts for a blog post comparing LLM benchmark results (or any dataset with a score/cost/time shape), in Portuguese and English, upload them to S3, and embed them in the Hugo article. Use when the user asks to add charts, graphs, or a visual comparison of models/options after a ranking table on akitaonrails.com.
---

# Blog Cost/Value Charts

You help turn a ranking table (score, cost, time, per item) into two
companion charts for a blog post on this Hugo site: a cost-vs-score bubble
scatter, and a score/(cost×time) value-ranking bar chart. Both are produced
dark-themed, one PNG per language the article ships in (normally `pt` and
`en`), and get embedded right after the ranking table.

This came out of the v4 LLM benchmark article
(`content/2026/09/15/novo-llm-benchmark-v4-*`), which needed exactly this
pair of charts to make a 39-row table skimmable. The script here is the
generalized version of the one-off script written for that post.

## When to use

- The article has a table with a numeric score, a cost, and a time (or any
  three comparable numeric axes) per row, and the user wants a visual
  "which one is the best deal" comparison instead of just the raw table.
- Explicitly requested: "add graphs/charts after the table", "make this
  easier to compare visually", "cost-benefit chart", etc.

## Workflow

### 1. Pick the dataset and scope

Not every row in a big table belongs in the chart. Decide, and say so in the
chart's own footnote:

- Which rows have a genuinely comparable cost figure? Exclude free,
  uncommitted, or flat-rate-plan entries that can't sit meaningfully on a
  dollar axis (a `$0` point breaks a log scale; a flat-rate plan has no
  per-run dollar figure at all). Call these out by name in the footnote
  rather than silently dropping them.
- If costs come from different harnesses/pricing bases (e.g. a real
  per-token API cost vs. a notional share of a flat subscription), don't
  hide that — color-code by `group` (see below) and say so in the footnote
  and in the article's own prose, the same way the source table already
  should.
- A curated subset (15-25 points) reads far better than cramming all 39+
  rows in; prefer restricting to the tier/category the article's own prose
  is actually discussing (e.g. "Tier A only") over trying to fit everything.

### 2. Build the JSON config

Copy `scripts/config.example.json` and edit it. Shape:

```jsonc
{
  "slug": "v4",                    // filename prefix for the output PNGs
  "x_log": true,                    // log-scale cost axis (usually yes: cost ranges span 100x+)
  "x_lim": [0.7, 160],               // tune to the actual data range with a little padding
  "y_lim": [84.5, 102.2],
  "x_ticks": [1, 3, 10, 30, 100],
  "x_tick_fmt": "${}",
  "group_colors": { "codex": "#5fd35f", "claude": "#e8965a", "...": "..." },
  "models": [
    {"name": "GPT-6 Astra", "score": 100.0, "cost": 30.55, "minutes": 100, "group": "codex"}
  ],
  "text": {
    "pt": { "scatter_title": "...", "scatter_subtitle": "...", "scatter_xlabel": "...",
            "scatter_ylabel": "...", "groups": {"codex": "Codex (OpenAI)"},
            "footnote": "...", "ranking_title": "...", "ranking_subtitle": "...",
            "ranking_xlabel": "...", "ranking_footnote": "..." },
    "en": { /* same keys, English copy */ }
  }
}
```

Every key under `text.<lang>` must be filled per language — there's no
translation step in the script, it just renders whatever string you give it.
Match the site's voice rules for both languages (PT-BR: Akita's direct,
skeptical voice, no em dashes; EN: New Yorker tone, same rules) — these
strings are visible chart copy, not throwaway labels.

### 3. Tune label offsets to avoid overlap

Bubble charts with several models at a similar cost/score WILL collide on
first render. Run the script once, actually look at the output image (Read
tool, not just "it ran without error"), and add a `label_offsets` map to the
config for any name whose label overlaps another:

```jsonc
"label_offsets": { "GPT 5.6 sol": [14, -22], "GPT 5.6 terra": [-14, 20] }
```

Values are `[dx, dy]` in points from the bubble center. Expect 2-3 iterations
of render → look → nudge before it's clean. This is the single most
time-consuming part of the workflow; budget for it rather than shipping the
first render.

### 4. Generate

```bash
python3 scripts/make_charts.py path/to/config.json --outdir /path/to/scratchpad/charts
```

Outputs `<slug>-cost-score-<lang>.png` and `<slug>-value-ranking-<lang>.png`
per language key in `text`. Read each image back before moving on — check
for: overlapping labels, title/subtitle collisions, a legend sitting on top
of data, and that the value-ranking numbers look sane (spot-check one or two
by hand: `score / (cost * minutes) * 1000`).

### 5. Upload to S3 — do not skip this

Static blog posts can't reference local files. Every PNG must go up before
it's embeddable:

```bash
set -a; source ~/.config/zsh/secrets 2>/dev/null; set +a
for f in <slug>-cost-score-pt.png <slug>-cost-score-en.png <slug>-value-ranking-pt.png <slug>-value-ranking-en.png; do
  aws s3 cp "/path/to/scratchpad/charts/$f" "s3://new-uploads-akitaonrails/YYYY/MM/DD/$f" \
    --region us-east-2 --content-type image/png
done
```

Use the article's own publish date for the `YYYY/MM/DD` path, matching the
convention already used for post images. After uploading, verify each URL
actually resolves (don't just trust the upload exit code):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://new-uploads-akitaonrails.s3.us-east-2.amazonaws.com/YYYY/MM/DD/<file>.png"
```

Expect `200` for all four.

### 6. Embed in the article

Insert right after the ranking table's own footnotes/caveats (before moving
on to narrative sections), one language-appropriate image per post, with a
short lead-in sentence and a plain-language alt text describing the axes:

```markdown
![Bubble chart: dollar cost on the X axis (log scale) against score on the Y axis, bubble size is wall-clock time, color is the harness](https://new-uploads-akitaonrails.s3.us-east-2.amazonaws.com/YYYY/MM/DD/<slug>-cost-score-en.png)
```

Do this in both the `index.md` (PT) and `index.en.md` (EN) siblings in the
same turn, each pointing at its own language's PNG — never mix languages in
one post's images.

### 7. Rebuild and verify before committing

```bash
hugo --minify
grep -o 'https://new-uploads-akitaonrails.s3[^")]*' public/<pt-path>/index.html
grep -o 'https://new-uploads-akitaonrails.s3[^")]*' public/en/<en-path>/index.html
```

Confirm the build has no errors and each language's page references its own
PNG. Then commit both markdown files together (they're a translation pair —
see the site's bilingual-editing rule) and push per the user's usual
publish flow.

## Design notes (why the script looks like this)

- **Dark theme, log-scale cost axis, bubble size = time**: mirrors a
  reference chart style the user has used before (`#0d1117` background,
  colored bubbles, muted gridlines). Cost in a benchmark context routinely
  spans two-plus orders of magnitude ($0.90 to $120+), so linear cost axes
  make cheap options indistinguishable — always log-scale it.
- **Color = group, not score**: coloring by cost basis/harness (real API $
  vs. notional subscription $ vs. free) visually carries the "these aren't
  directly comparable" caveat that the article's prose already has to state
  in words. Don't color by score/tier instead; that duplicates the Y axis.
- **Value index = score / (cost × time), scaled ×1000 for readable numbers**:
  this combined ranking routinely surprises — a model with a merely-good
  score but very low cost AND fast wall time can out-rank the single
  highest-score cheap model. Call that out explicitly in the article's prose
  next to the chart; it's usually the actual news, not filler.
- **Never automate the "which rows to include" decision**: that's an
  editorial judgment about the article's argument, not a data-cleaning step.
