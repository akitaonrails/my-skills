#!/usr/bin/env python3
"""Generate a dark-themed cost/score bubble chart + value-ranking bar chart
for a blog post, in one or more languages, from a JSON dataset.

Usage:
    python3 make_charts.py config.json --outdir ./out

See config.example.json in this directory for the expected shape. Produces,
for each language key present in `text`:
    <outdir>/<slug>-cost-score-<lang>.png
    <outdir>/<slug>-value-ranking-<lang>.png
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BG = "#0d1117"
GRID = "#2a2f3a"
FG = "#e6e6e6"
MUTED = "#9aa0a6"

DEFAULT_PALETTE = [
    "#5fd35f", "#e8965a", "#f2d43d", "#59c3e6",
    "#d16bd1", "#e06666", "#7f8cff", "#8fd694",
]

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": FG,
    "axes.edgecolor": GRID,
    "axes.labelcolor": FG,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "font.family": "DejaVu Sans",
    "font.size": 12,
})


def size_for_time(t, k=22, base=90):
    """sqrt scaling so bubble AREA is roughly proportional to time."""
    return base + (t ** 0.5) * k


def build_group_colors(models, palette):
    groups = []
    for m in models:
        g = m.get("group")
        if g is not None and g not in groups:
            groups.append(g)
    return {g: palette[i % len(palette)] for i, g in enumerate(groups)}


def make_scatter(models, group_colors, text, cfg, out_path):
    fig_w, fig_h = cfg.get("scatter_size", [11.5, 9.6])
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=170)

    for m in models:
        color = group_colors.get(m.get("group"), DEFAULT_PALETTE[0])
        ax.scatter(
            m["cost"], m["score"],
            s=size_for_time(m["minutes"], k=cfg.get("bubble_k", 22), base=cfg.get("bubble_base", 90)),
            color=color, edgecolors="#00000055", linewidths=0.8, alpha=0.92, zorder=3,
        )

    offsets = cfg.get("label_offsets", {})
    for m in models:
        dx, dy = offsets.get(m["name"], [8, 8])
        ax.annotate(m["name"], (m["cost"], m["score"]), xytext=(dx, dy),
                    textcoords="offset points", fontsize=9.3, color=FG, zorder=4)

    if cfg.get("x_log", True):
        ax.set_xscale("log")
    xlim = cfg.get("x_lim")
    if xlim:
        ax.set_xlim(*xlim)
    ylim = cfg.get("y_lim")
    if ylim:
        ax.set_ylim(*ylim)
    xticks = cfg.get("x_ticks")
    if xticks:
        ax.set_xticks(xticks)
        ax.set_xticklabels([cfg.get("x_tick_fmt", "${}").format(t) for t in xticks])

    ax.grid(True, which="major", color=GRID, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID)

    ax.set_title(text["scatter_title"], fontsize=18, fontweight="bold", color=FG, pad=54, loc="left")
    ax.text(0.0, 1.045, text["scatter_subtitle"], transform=ax.transAxes,
            fontsize=10.2, color=MUTED, linespacing=1.6)
    ax.set_xlabel(text["scatter_xlabel"], fontsize=12)
    ax.set_ylabel(text["scatter_ylabel"], fontsize=12)

    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=c,
                       markeredgecolor="#00000055", markersize=10, label=text["groups"][g])
               for g, c in group_colors.items()]
    fig.legend(handles=handles, loc="lower center", ncol=cfg.get("legend_cols", 2),
               frameon=False, fontsize=9.5, labelcolor=FG, handletextpad=0.6,
               bbox_to_anchor=(0.5, 0.065))

    if text.get("footnote"):
        fig.text(0.5, 0.005, text["footnote"], ha="center", fontsize=8.6, color=MUTED)

    fig.tight_layout(rect=(0, 0.16, 1, 0.87))
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def make_ranking(models, group_colors, text, cfg, out_path):
    rows = []
    for m in models:
        idx = m["score"] / (m["cost"] * m["minutes"]) * cfg.get("index_scale", 1000)
        rows.append((m["name"], idx, m.get("group")))
    rows.sort(key=lambda r: r[1])

    fig_w, fig_h = cfg.get("ranking_size", [10, 9.5])
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=170)
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [group_colors.get(r[2], DEFAULT_PALETTE[0]) for r in rows]

    bars = ax.barh(names, vals, color=colors, edgecolor="#00000055", linewidth=0.8, height=0.62, zorder=3)
    for bar, v in zip(bars, vals):
        ax.text(v + max(vals) * 0.012, bar.get_y() + bar.get_height() / 2, f"{v:.1f}",
                va="center", fontsize=9.5, color=FG)

    ax.set_xlim(0, max(vals) * 1.14)
    ax.grid(True, axis="x", color=GRID, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0, labelsize=10.5)
    ax.tick_params(axis="x", labelsize=9.5)

    ax.set_title(text["ranking_title"], fontsize=17, fontweight="bold", color=FG, pad=30, loc="left")
    ax.text(0.0, 1.035, text["ranking_subtitle"], transform=ax.transAxes, fontsize=10, color=MUTED)
    ax.set_xlabel(text["ranking_xlabel"], fontsize=11)

    if text.get("ranking_footnote"):
        fig.text(0.5, 0.01, text["ranking_footnote"], ha="center", fontsize=8.6, color=MUTED)

    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(out_path)
    plt.close(fig)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="Path to a JSON config (see config.example.json)")
    ap.add_argument("--outdir", default=".", help="Output directory for the PNGs")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    models = cfg["models"]
    slug = cfg.get("slug", "chart")
    palette = cfg.get("palette", DEFAULT_PALETTE)
    group_colors = cfg.get("group_colors") or build_group_colors(models, palette)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for lang, text in cfg["text"].items():
        make_scatter(models, group_colors, text, cfg, outdir / f"{slug}-cost-score-{lang}.png")
        make_ranking(models, group_colors, text, cfg, outdir / f"{slug}-value-ranking-{lang}.png")


if __name__ == "__main__":
    sys.exit(main())
