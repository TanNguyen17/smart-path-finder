"""Post-hoc visualisation of ``benchmark_results.csv``.

Plots three per-query metrics across the three pathfinding algorithms,
broken down by graph density (sparse / dense) and source-destination
distance regime (close / far). Every benchmark scenario uses random
avoidance (count scaled with grid side) so the comparison is uniform.

Requirements (install only if you want to run this)::

    pip install pandas matplotlib

Outputs PNG bar charts grouped into three sibling folders, one per
metric:

* ``compare_node_explore/``  - bars of mean ``nodes_explored``
* ``compare_total_distance/`` - bars of mean ``total_distance``
* ``compare_total_time/``     - bars of mean ``total_time``

Each folder contains:

* ``sparse_close.png``, ``sparse_far.png``,
  ``dense_close.png``, ``dense_far.png`` - one chart per
  (graph, pair_kind) cell, x-axis = grid side, bars grouped by
  algorithm.
* ``overview.png`` - 2x2 layout (rows = graph density,
  cols = pair_kind) for at-a-glance comparison.

Usage::

    python plot_benchmark.py
    python plot_benchmark.py --csv other_results.csv --out figs/
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


METRICS: list[tuple[str, str, str]] = [
    ("nodes_explored", "mean nodes explored", "compare_node_explore"),
    ("total_distance", "mean total distance (km)", "compare_total_distance"),
    ("total_time", "mean total travel time (h)", "compare_total_time"),
]


# ---------------------------------------------------------------------------
# Data loading and aggregation
# ---------------------------------------------------------------------------


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Keep only successful queries so the averages aren't polluted by 0s.
    df = df[df["found"] == 1].copy()
    # Backwards compatibility: older CSVs may lack the new metric columns.
    if "total_distance" not in df.columns:
        df["total_distance"] = 0.0
    if "total_time" not in df.columns:
        df["total_time"] = 0.0
    return df


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-query rows into ``(graph, side, algorithm, pair_kind)``
    buckets with mean values for each plotted metric.
    """
    return df.groupby(
        ["graph", "side", "algorithm", "pair_kind"],
        as_index=False,
    ).agg(
        trials=("nodes_explored", "size"),
        mean_explored=("nodes_explored", "mean"),
        mean_distance=("total_distance", "mean"),
        mean_time=("total_time", "mean"),
    )


def metric_to_summary_col(metric: str) -> str:
    """Map a raw CSV column to the corresponding ``mean_*`` column in
    the summarised frame returned by :func:`summarise`.
    """
    return {
        "nodes_explored": "mean_explored",
        "total_distance": "mean_distance",
        "total_time": "mean_time",
    }[metric]


# ---------------------------------------------------------------------------
# Per-cell bar chart (one image per graph x pair_kind combo, for one metric)
# ---------------------------------------------------------------------------


def plot_one(
    summary: pd.DataFrame,
    graph: str,
    pair_kind: str,
    value_col: str,
    ylabel: str,
    out_dir: Path,
) -> None:
    sub = summary[
        (summary["graph"] == graph) & (summary["pair_kind"] == pair_kind)
    ]
    if sub.empty:
        print(f"no data for graph={graph}, pair_kind={pair_kind}")
        return

    pivot = sub.pivot_table(
        index="side",
        columns="algorithm",
        values=value_col,
        aggfunc="mean",
    ).sort_index()

    ax = pivot.plot(
        kind="bar",
        figsize=(9, 5),
        width=0.78,
        edgecolor="black",
    )
    ax.set_title(f"{graph} graph / {pair_kind} pairs: {ylabel}")
    ax.set_xlabel("grid side (rows = cols)")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=0)
    ax.legend(title="algorithm")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    plt.tight_layout()

    out = out_dir / f"{graph}_{pair_kind}.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ---------------------------------------------------------------------------
# Combined overview: 2x2 grid (rows = graph density, cols = pair_kind)
# ---------------------------------------------------------------------------


def plot_overview(
    summary: pd.DataFrame,
    value_col: str,
    ylabel: str,
    out_dir: Path,
) -> None:
    graphs = ["sparse", "dense"]
    pair_kinds = ["close", "far"]

    fig, axes = plt.subplots(
        len(graphs), len(pair_kinds), figsize=(14, 9), sharey=False
    )

    for i, graph in enumerate(graphs):
        for j, pair_kind in enumerate(pair_kinds):
            ax = axes[i][j]
            sub = summary[
                (summary["graph"] == graph)
                & (summary["pair_kind"] == pair_kind)
            ]
            if sub.empty:
                ax.set_title(f"{graph} / {pair_kind} (no data)")
                continue

            pivot = sub.pivot_table(
                index="side",
                columns="algorithm",
                values=value_col,
                aggfunc="mean",
            ).sort_index()

            pivot.plot(
                kind="bar",
                ax=ax,
                width=0.78,
                edgecolor="black",
                legend=(i == 0 and j == 0),
            )
            ax.set_title(f"{graph} / {pair_kind}")
            ax.set_xlabel("grid side")
            ax.set_ylabel(ylabel)
            ax.tick_params(axis="x", rotation=0)
            ax.grid(axis="y", linestyle=":", alpha=0.5)
            if i == 0 and j == 0:
                ax.legend(title="algorithm", fontsize=8)

    fig.suptitle(
        f"Algorithm comparison: {ylabel}\n"
        "(rows: sparse vs dense, cols: close vs far src/dst)",
        y=1.00,
    )
    plt.tight_layout()

    out = out_dir / "overview.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot benchmark_results.csv")
    parser.add_argument("--csv", type=str, default="benchmark_results.csv")
    parser.add_argument(
        "--out",
        type=str,
        default=".",
        help="base directory; metric subfolders are created underneath",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    base_out = Path(args.out)
    base_out.mkdir(parents=True, exist_ok=True)

    df = load(csv_path)
    print(f"loaded {len(df)} rows from {csv_path}")
    summary = summarise(df)

    for metric, ylabel, folder in METRICS:
        out_dir = base_out / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        col = metric_to_summary_col(metric)
        for graph in ("sparse", "dense"):
            for pair_kind in ("close", "far"):
                plot_one(summary, graph, pair_kind, col, ylabel, out_dir)
        plot_overview(summary, col, ylabel, out_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
