# blog-cost-charts

Generates a dark-themed cost-vs-score bubble scatter chart and a
score/(cost×time) value-ranking bar chart, per language, for a blog post
comparing benchmarked options (LLMs, tools, plans, anything with a
score/cost/time shape).

Written after building this pair of charts by hand for the akitaonrails.com
v4 LLM benchmark article (`content/2026/09/15/novo-llm-benchmark-v4-*`),
where a 39-row ranking table needed a visual "which one's the best deal"
companion. The script is the generalized, reusable version of that one-off.

## Contents

- `SKILL.md` — the workflow: scoping the dataset, building the config,
  tuning label placement, generating, uploading to S3, embedding in the
  Hugo article, and rebuilding/verifying before commit.
- `scripts/make_charts.py` — the chart generator. Takes a JSON config, emits
  two PNGs per language key present in the config's `text` object.
- `scripts/config.example.json` — a minimal working example to copy and
  edit for a new article.

## Quick start

```bash
cp scripts/config.example.json /path/to/my-config.json
# edit my-config.json: models, axis limits, per-language titles/labels
python3 scripts/make_charts.py /path/to/my-config.json --outdir ./out
# look at the output, tune label_offsets for any overlapping labels, re-run
# then: upload every PNG to S3 (see SKILL.md step 5) before embedding
```

Charts never look right on the first render when models cluster at similar
cost/score — budget for a couple of render-look-nudge cycles on
`label_offsets` before calling it done.
