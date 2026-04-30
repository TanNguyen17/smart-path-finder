"""Empirical benchmark for the Smart Path Finder.

Mirrors the structure of ``as2/smart_path/benchmark.py`` but compares
the three dsa-final algorithms across two graph densities and two
source-destination distance regimes. Every query uses random-node
avoidance whose count scales with the grid side.

    graph_kind  in {sparse, dense}
                  - sparse: drop_prob=0.20, ~no diagonals, almost no highways
                  - dense:  drop_prob=0.02, diag_prob=0.30, many highways
    side        in user-supplied list (e.g. 30,50,70,100); rows = cols = side
    algorithm   in {dijkstra_distance, dijkstra_time, bidi_distance}
    pair_kind   in {close, far}
                  - close: Manhattan distance <= max(2, side // 8)
                  - far:   Manhattan distance >= side
    avoidance   always random; count = max(2, side // 4) nodes excluded
                per query (sides 30,50,70,100 -> 7,12,17,25 forbidden).

For each (graph, side, pair_kind) cell we draw ``--trials`` random
``(src, dst, avoid_nodes)`` queries ONCE and run all three algorithms
on the same query list. That makes the comparison apples-to-apples:
any difference between algorithms reflects algorithmic behaviour, not
divergent random sampling. Three metrics are recorded per query:
``nodes_explored``, ``total_distance``, ``total_time``.

Outputs ``benchmark_results.csv`` and a markdown summary on stdout.

Run with::

    python benchmark.py --sides 30,50,70,100 --trials 20
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
from pathlib import Path

from algorithms import (
    bidirectional_dijkstra_distance,
    dijkstra_distance,
    dijkstra_time,
)
from generator import generate_graph


DEFAULT_TRIALS = 20


def build_sparse(side: int, seed: int):
    """Sparse grid: ~20% of base streets dropped, almost no shortcuts.

    Mirrors the @as2 sparse layout: many closed streets, very few diagonal
    shortcuts, almost no highways. The Dijkstra search must therefore walk
    around large blocked regions, exploring more nodes per query.
    """
    g = generate_graph(
        rows=side,
        cols=side,
        drop_prob=0.20,
        diag_prob=0.005,
        highway_edges=max(1, int(side * side * 0.001)),
        seed=seed,
        id_mode="str",
    )
    return g


def build_dense(side: int, seed: int):
    """Dense grid: only ~2% of streets dropped, many diagonals + highways."""
    g = generate_graph(
        rows=side,
        cols=side,
        drop_prob=0.02,
        diag_prob=0.30,
        highway_edges=int(side * side * 0.20),
        seed=seed,
        id_mode="str",
    )
    return g


def parse_rc(node_id: str) -> tuple[int, int]:
    """Parse a "r_c" string id into (row, col) integers."""
    r_str, c_str = node_id.split("_", 1)
    return int(r_str), int(c_str)


def pick_pair(
    graph,
    rng: random.Random,
    side: int,
    kind: str,
) -> tuple[str, str]:
    """Sample a (src, dst) pair according to ``kind``.

    Uses the underlying grid coordinates encoded in the "r_c" node ids
    to bias selection toward short or long Manhattan distances.

    * ``close`` - both endpoints lie within ``max(2, side // 8)``
      Manhattan steps of each other.
    * ``far`` - both endpoints are at least ``side`` Manhattan steps
      apart (i.e. roughly half the grid diagonal or more).
    """
    nodes = list(graph.nodes)

    if kind == "close":
        threshold = max(2, side // 8)
        for _ in range(200):
            a = rng.choice(nodes)
            ar, ac = parse_rc(a)
            dr = rng.randint(-threshold, threshold)
            dc = rng.randint(-threshold, threshold)
            if dr == 0 and dc == 0:
                continue
            br, bc = ar + dr, ac + dc
            if not (0 <= br < side and 0 <= bc < side):
                continue
            b = f"{br}_{bc}"
            if b != a and b in graph.nodes:
                return a, b
        a, b = rng.sample(nodes, 2)
        return a, b

    if kind == "far":
        threshold = side
        a = b = nodes[0]
        for _ in range(200):
            a, b = rng.sample(nodes, 2)
            ar, ac = parse_rc(a)
            br, bc = parse_rc(b)
            if abs(ar - br) + abs(ac - bc) >= threshold:
                return a, b
        return a, b

    raise ValueError(f"unknown pair kind: {kind}")


ALGORITHMS = {
    "dijkstra_distance": dijkstra_distance,
    "dijkstra_time": dijkstra_time,
    "bidi_distance": bidirectional_dijkstra_distance,
}


def avoid_count_for(side: int) -> int:
    """Number of random nodes to forbid per query, scaled with grid side.

    A linear-in-side schedule so the avoid challenge grows with the
    graph but never approaches the percolation threshold (which would
    risk disconnecting the sparse graph).
    """
    return max(2, side // 4)


def random_avoid_nodes(
    graph,
    rng: random.Random,
    side: int,
    src: str,
    dst: str,
) -> set:
    """Sample ``avoid_count_for(side)`` random nodes excluding src/dst."""
    pool = [n for n in graph.nodes if n != src and n != dst]
    k = min(avoid_count_for(side), len(pool))
    if k == 0:
        return set()
    return set(rng.sample(pool, k))


def make_queries(
    graph,
    side: int,
    pair_kind: str,
    trials: int,
    rng: random.Random,
) -> list[tuple[str, str, set]]:
    """Pre-generate ``trials`` ``(src, dst, avoid_nodes)`` tuples once per
    cell so all three algorithms run on the *same* set of queries.

    This guarantees a fair head-to-head comparison: any difference in
    reported metrics between algorithms reflects algorithmic behaviour,
    not divergent random sampling.
    """
    queries = []
    for _ in range(trials):
        src, dst = pick_pair(graph, rng, side, pair_kind)
        avoid_nodes = random_avoid_nodes(graph, rng, side, src, dst)
        queries.append((src, dst, avoid_nodes))
    return queries


def run_one_query(
    graph_kind: str,
    graph,
    side: int,
    algorithm: str,
    pair_kind: str,
    src: str,
    dst: str,
    avoid_nodes: set,
) -> dict:
    """Run a single algorithm on a single ``(src, dst, avoid_nodes)``
    query and return the per-query record dict.
    """
    fn = ALGORITHMS[algorithm]
    result = fn(
        graph,
        src,
        dst,
        avoid_nodes=avoid_nodes,
        avoid_edges=set(),
        departure_hour=8,
    )
    sr, sc = parse_rc(src)
    dr, dc = parse_rc(dst)
    manhattan = abs(sr - dr) + abs(sc - dc)
    if result is None:
        nodes_explored = 0
        path_len = 0
        total_distance = 0.0
        total_time = 0.0
        found = 0
    else:
        nodes_explored = int(result.get("nodes_explored", 0))
        path_len = len(result.get("path", []))
        total_distance = float(result.get("total_distance", 0.0))
        total_time = float(result.get("total_time", 0.0))
        found = 1
    return {
        "graph": graph_kind,
        "side": side,
        "nodes": graph.node_count(),
        "edges": graph.edge_count(),
        "algorithm": algorithm,
        "pair_kind": pair_kind,
        "src": src,
        "dst": dst,
        "manhattan": manhattan,
        "nodes_explored": nodes_explored,
        "path_len": path_len,
        "total_distance": total_distance,
        "total_time": total_time,
        "avoid_count": len(avoid_nodes),
        "found": found,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    data = sorted(values)
    k = int(round(q * (len(data) - 1)))
    return data[k]


def summarise(records: list[dict]):
    """Group records by (graph, side, algorithm, pair_kind) and compute
    mean / median / p95 of nodes_explored plus mean total_distance,
    mean total_time, mean path length, and found-rate.
    """
    buckets: dict[tuple, list[dict]] = {}
    for r in records:
        key = (r["graph"], r["side"], r["algorithm"], r["pair_kind"])
        buckets.setdefault(key, []).append(r)

    out = []
    for key, rs in sorted(buckets.items()):
        explored = [r["nodes_explored"] for r in rs if r["found"]]
        path_lens = [r["path_len"] for r in rs if r["found"]]
        distances = [r["total_distance"] for r in rs if r["found"]]
        times = [r["total_time"] for r in rs if r["found"]]
        manhattans = [r["manhattan"] for r in rs]
        if not explored:
            stats = {
                "trials": len(rs),
                "mean_explored": 0.0,
                "median_explored": 0.0,
                "p95_explored": 0.0,
                "mean_distance": 0.0,
                "mean_time": 0.0,
                "mean_path_len": 0.0,
                "mean_manhattan": statistics.mean(manhattans) if manhattans else 0.0,
                "found_rate": 0.0,
            }
        else:
            stats = {
                "trials": len(rs),
                "mean_explored": statistics.mean(explored),
                "median_explored": statistics.median(explored),
                "p95_explored": percentile(explored, 0.95),
                "mean_distance": statistics.mean(distances),
                "mean_time": statistics.mean(times),
                "mean_path_len": statistics.mean(path_lens),
                "mean_manhattan": statistics.mean(manhattans),
                "found_rate": len(explored) / len(rs),
            }
        out.append((key, stats))
    return out


def write_csv(records: list[dict], path: Path) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)


def print_markdown_table(summary) -> None:
    print(
        "\n| graph | side | algorithm | pair_kind | trials | "
        "mean_explored | median_explored | p95_explored | "
        "mean_distance | mean_time | mean_path_len | mean_manhattan | "
        "found_rate |"
    )
    print("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for key, s in summary:
        graph_kind, side, algo, pair_kind = key
        print(
            f"| {graph_kind} | {side} | {algo} | {pair_kind} | "
            f"{s['trials']} | {s['mean_explored']:.0f} | "
            f"{s['median_explored']:.0f} | {s['p95_explored']:.0f} | "
            f"{s['mean_distance']:.2f} | {s['mean_time']:.2f} | "
            f"{s['mean_path_len']:.1f} | {s['mean_manhattan']:.1f} | "
            f"{s['found_rate']:.2f} |"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Empirical benchmark for dsa-final"
    )
    parser.add_argument(
        "--sides",
        type=str,
        default="30,50,70,100",
        help="comma-separated grid sides (rows = cols = side)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help="queries per (graph, side, algorithm, pair_kind) cell",
    )
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument(
        "--out",
        type=str,
        default="benchmark_results.csv",
        help="path for the per-query CSV",
    )
    args = parser.parse_args(argv)

    sides = [int(s) for s in args.sides.split(",") if s.strip()]
    rng = random.Random(args.seed)

    graph_specs = [
        ("sparse", build_sparse),
        ("dense", build_dense),
    ]

    pair_kinds = ("close", "far")

    all_records: list[dict] = []

    for side in sides:
        for graph_kind, builder in graph_specs:
            print(f"[bench] building {graph_kind} graph side={side}")
            graph = builder(side, seed=args.seed + side)
            print(
                f"[bench]   built {graph.node_count()} nodes, "
                f"{graph.edge_count()} edges, "
                f"avoid_count={avoid_count_for(side)}"
            )
            for pair_kind in pair_kinds:
                # Generate the trial queries once and reuse them across
                # all three algorithms in this cell. This is what makes
                # algorithm comparisons apples-to-apples.
                queries = make_queries(
                    graph, side, pair_kind, args.trials, rng
                )
                for algorithm in ALGORITHMS:
                    print(
                        f"[bench]   running {algorithm} / pair={pair_kind}"
                    )
                    for src, dst, avoid_nodes in queries:
                        record = run_one_query(
                            graph_kind,
                            graph,
                            side,
                            algorithm,
                            pair_kind,
                            src,
                            dst,
                            avoid_nodes,
                        )
                        all_records.append(record)

    out_path = Path(args.out)
    write_csv(all_records, out_path)
    print(f"\n[bench] wrote {len(all_records)} records to {out_path}")

    summary = summarise(all_records)
    print_markdown_table(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
