#!/usr/bin/env python3
"""Fan out claim batches to parallel headless checker subagents.

Takes a claims.json file (array of claim objects extracted from an article),
batches them, renders the adversarial checker prompt template per batch, runs
the batches in parallel through scripts/dispatch_checker.py, extracts the JSON
verdict array from each answer, and merges everything into:

    <out>/verdicts.jsonl   one verdict object per claim, all batches merged
    <out>/summary.json     run stats: batches, status, verdict counts, tokens, cost
    <out>/batch-NN/...     per-batch artifacts (prompt, answer, result)

The orchestrator (you, the agent using this skill) pre-sorts claims so related
claims sit in the same batch — coherent batches verify better and waste fewer
tokens on re-established context.

Stdlib only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dispatch_checker import (run_one, default_env_file,  # noqa: E402
                              load_default_model, load_model_config)

_here = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = _here.parent / "references" / "checker-prompt.md"

VERDICTS = ("false", "imprecise", "misleading", "unsupported", "correct", "opinion-skipped")


def render_prompt(template: str, claims: list[dict], title: str, lang: str) -> str:
    repl = {
        "{{TITLE}}": title,
        "{{LANG}}": lang,
        "{{CLAIMS}}": json.dumps(claims, indent=2, ensure_ascii=False),
        "{{CLAIM_COUNT}}": str(len(claims)),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def extract_json_array(text: str) -> list | None:
    """Pull the last JSON array out of an answer (fenced or bare)."""
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    for candidate in reversed(fences + [text]):
        candidate = candidate.strip()
        start = candidate.find("[")
        end = candidate.rfind("]")
        if start == -1 or end <= start:
            continue
        try:
            parsed = json.loads(candidate[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except ValueError:
            continue
    return None


def run_batch(batch: dict, args, model: str | None, variant: str | None) -> dict:
    res = run_one(
        harness=args.harness,
        prompt=batch["prompt"],
        out_dir=batch["dir"],
        cwd=Path(args.cwd).resolve(),
        model=model,
        variant=variant,
        timeout=args.timeout,
        stall=args.stall,
        env_file=Path(args.env_file) if args.env_file else default_env_file(),
    )
    verdicts = extract_json_array(res.get("answer", ""))
    return {
        "batch": batch["name"],
        "claim_ids": [c.get("id") for c in batch["claims"]],
        "status": res["status"],
        "tokens_in": res["tokens_in"],
        "tokens_out": res["tokens_out"],
        "cost_usd": res.get("cost_usd"),
        "cost_usd_est": res.get("cost_usd_est"),
        "duration_s": res["duration_s"],
        "verdicts": verdicts,
    }


def _num(r: dict, key: str) -> float:
    v = r.get(key)
    return v if isinstance(v, (int, float)) else 0


def write_run_outputs(out_dir: Path, results: list[dict], n_claims: int,
                      wall_s: float, harness: str, model: str | None) -> dict:
    """Merge batch results into verdicts.jsonl, summary.json and cost_report.md."""
    counts: dict[str, int] = {}
    with open(out_dir / "verdicts.jsonl", "w") as fh:
        for r in sorted(results, key=lambda x: x["batch"]):
            for v in r.get("verdicts") or []:
                if not isinstance(v, dict):
                    continue
                verdict = v.get("verdict", "unknown")
                counts[verdict] = counts.get(verdict, 0) + 1
                v["_batch"] = r["batch"]
                fh.write(json.dumps(v, ensure_ascii=False) + "\n")

    ok = sum(1 for r in results if r["status"] == "ok" and r.get("verdicts") is not None)
    summary = {
        "claims": n_claims,
        "batches": len(results),
        "batches_ok": ok,
        "batches_failed": len(results) - ok,
        "tokens_in": sum(_num(r, "tokens_in") for r in results),
        "tokens_out": sum(_num(r, "tokens_out") for r in results),
        "cost_usd": round(sum(_num(r, "cost_usd") for r in results), 4),
        "cost_usd_est": round(sum(_num(r, "cost_usd_est") for r in results), 4),
        "wall_s": round(wall_s, 1),
        "verdict_counts": {k: counts[k] for k in sorted(counts)},
        "batches_detail": [
            {"batch": r["batch"], "claims": len(r.get("claim_ids") or []),
             "status": r["status"],
             "tokens_in": _num(r, "tokens_in"), "tokens_out": _num(r, "tokens_out"),
             "cost_usd": r.get("cost_usd"), "cost_usd_est": r.get("cost_usd_est"),
             "duration_s": _num(r, "duration_s")}
            for r in sorted(results, key=lambda x: x["batch"])
        ],
        "failures": [{"batch": r["batch"], "status": r["status"]}
                     for r in results if r["status"] != "ok" or not r.get("verdicts")],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "cost_report.md").write_text(
        build_cost_report(results, summary, harness, model))
    return summary


def build_cost_report(results: list[dict], summary: dict,
                      harness: str, model: str | None) -> str:
    """Human-readable token/cost report for one fan-out run."""
    def batch_cost(r: dict) -> tuple[str, str]:
        # A 0.0 "native" cost is indistinguishable from unreported; show the
        # estimate instead (honest source label) when there is one.
        if isinstance(r.get("cost_usd"), (int, float)) and r["cost_usd"] > 0:
            return f"{r['cost_usd']:.4f}", "native"
        if isinstance(r.get("cost_usd_est"), (int, float)) and r["cost_usd_est"] > 0:
            return f"{r['cost_usd_est']:.4f}", "estimated"
        return "-", "-"

    rows = []
    for r in sorted(results, key=lambda x: x["batch"]):
        cost, source = batch_cost(r)
        rows.append(f"| {r['batch']} | {len(r.get('claim_ids') or [])} | {r['status']} "
                    f"| {_num(r, 'tokens_in'):,.0f} | {_num(r, 'tokens_out'):,.0f} "
                    f"| {cost} | {source} | {_num(r, 'duration_s'):,.1f}s |")
    total_cost, total_source = batch_cost({"cost_usd": summary["cost_usd"],
                                           "cost_usd_est": summary["cost_usd_est"]})
    verdicts = ", ".join(f"{k}={v}" for k, v in summary["verdict_counts"].items()) or "none"

    notes = [
        "- `native` cost is reported by the harness itself; `estimated` is list-price "
        "from `config/models.json` — an upper bound that ignores cache-read discounts "
        "and flat-rate subscriptions.",
    ]
    cost_note = (load_model_config().get("harnesses", {}).get(harness, {}).get("cost_note"))
    if cost_note:
        notes.append(f"- {harness}: {cost_note}")
    notes.append("- Subagent spend only — the orchestrator agent's own tokens are not included.")

    return (
        f"# Fact-check cost report\n\n"
        f"- Run: {time.strftime('%Y-%m-%d %H:%M')} — harness `{harness}`, "
        f"model `{model or '(harness default)'}`\n"
        f"- Claims: {summary['claims']} in {summary['batches']} batches "
        f"({summary['batches_ok']} ok, {summary['batches_failed']} failed) — "
        f"verdicts: {verdicts}\n"
        f"- Wall time: {summary['wall_s']}s\n\n"
        f"| Batch | Claims | Status | Tokens in | Tokens out | Cost USD | Source | Duration |\n"
        f"| --- | --- | --- | ---: | ---: | ---: | --- | ---: |\n"
        f"{chr(10).join(rows)}\n"
        f"| **TOTAL** | **{summary['claims']}** | **{summary['batches_ok']}/{summary['batches']} ok** "
        f"| **{summary['tokens_in']:,.0f}** | **{summary['tokens_out']:,.0f}** "
        f"| **{total_cost}** | {total_source} | **{summary['wall_s']}s** |\n\n"
        f"Notes:\n" + "\n".join(notes) + "\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fan out claim batches to parallel headless checker subagents.")
    ap.add_argument("--claims", required=True,
                    help="claims.json: array of {id, quote, category, hint, ...}")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--title", default="(untitled article)")
    ap.add_argument("--lang", default="pt-BR")
    ap.add_argument("--batch-size", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--harness", required=True,
                    choices=["claude", "codex", "opencode", "zcode", "kimi", "grok", "agy"])
    ap.add_argument("--model", default=None,
                    help="override; default = config/models.json for the harness")
    ap.add_argument("--variant", default=None, help="reasoning effort override")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--stall", type=int, default=300)
    ap.add_argument("--env-file", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="render prompts and show the plan without dispatching")
    args = ap.parse_args()

    claims = json.loads(Path(args.claims).read_text())
    if not isinstance(claims, list) or not claims:
        ap.error("claims file must be a non-empty JSON array")
    for i, c in enumerate(claims):
        if "id" not in c or "quote" not in c:
            ap.error(f"claim #{i} missing 'id' or 'quote'")

    template = Path(args.template).read_text()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    batches = []
    for i in range(0, len(claims), args.batch_size):
        chunk = claims[i:i + args.batch_size]
        name = f"batch-{(i // args.batch_size) + 1:02d}"
        bdir = out_dir / name
        prompt = render_prompt(template, chunk, args.title, args.lang)
        (bdir).mkdir(parents=True, exist_ok=True)
        (bdir / "prompt.txt").write_text(prompt)
        batches.append({"name": name, "claims": chunk, "dir": bdir, "prompt": prompt})

    model = args.model or load_default_model(args.harness)[0]
    if args.variant:
        variant = args.variant
    else:
        variant = load_default_model(args.harness)[1] if not args.model else None

    print(f"{len(claims)} claims -> {len(batches)} batches "
          f"(size {args.batch_size}, parallel {args.parallel})")
    print(f"harness={args.harness} model={model or '(default)'} variant={variant or '-'}")

    if args.dry_run:
        for b in batches:
            print(f"  {b['name']}: {len(b['claims'])} claims "
                  f"-> {b['dir'] / 'prompt.txt'}")
        return 0

    started = time.time()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(run_batch, b, args, model, variant): b["name"]
                   for b in batches}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                r = fut.result()
            except Exception as exc:  # noqa: BLE001 — report, don't crash siblings
                r = {"batch": name, "claim_ids": [], "status": "error",
                     "tokens_in": 0, "tokens_out": 0, "cost_usd": None,
                     "cost_usd_est": None, "duration_s": 0, "verdicts": None,
                     "error": f"{type(exc).__name__}: {exc}"}
            tag = r["status"] + ("" if r.get("verdicts") is not None else " (no json)")
            print(f"  {name}: {tag} "
                  f"({r.get('duration_s', 0)}s, {len(r.get('verdicts') or [])} verdicts)")
            results.append(r)

    summary = write_run_outputs(out_dir, results, len(claims),
                                time.time() - started, args.harness, model)
    print(json.dumps(summary, indent=2))
    print(f"\nverdicts      -> {out_dir / 'verdicts.jsonl'}")
    print(f"cost report   -> {out_dir / 'cost_report.md'}")
    ok = summary["batches_ok"]
    return 0 if ok == len(batches) else (1 if ok else 2)


if __name__ == "__main__":
    sys.exit(main())
