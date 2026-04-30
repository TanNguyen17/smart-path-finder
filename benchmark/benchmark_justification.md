# Benchmark Justification

This document explains how the empirical comparison in
[benchmark.py](benchmark.py) is set up: how "sparse" vs "dense" graphs
are constructed, how "close" vs "far" source-destination pairs are
selected, how random avoidance is sized, and which metrics are recorded
for each query.

The benchmark compares three pathfinding algorithms
(`dijkstra_distance`, `dijkstra_time`, `bidi_distance` from
[../algorithms.py](../algorithms.py)) across four scenarios produced by
the cross of two graph densities (sparse / dense) and two distance
regimes (close / far). Every choice below is made so that the four
reported cells actually probe different algorithmic regimes rather than
shades of the same setup.

---

## 1. Sparse vs Dense Graph Definitions

Both densities are produced by the same
[`generate_graph`](../generator.py) routine - only the keyword arguments
differ. Throughout the table below, `S` denotes the grid side length
(`rows = cols = S`), supplied via the `--sides` CLI flag.

### Parameter table

| Parameter | Sparse value | Dense value | Justification |
|---|---|---|---|
| `rows`, `cols` | `S` | `S` | Square grid so the close/far Manhattan thresholds (which scale with `S`) apply uniformly to both densities. The total number of nodes is `S²`, which lets us quote a single "size" axis on the plots. |
| `drop_prob` | `0.20` | `0.02` | Probability that each candidate base 4-grid edge is *omitted* during construction. Sparse keeps ~80% of streets ("many closed roads"), dense keeps ~98%. Both stay well above the 2D bond-percolation threshold `p_c = 0.5`, so the giant connected component covers >99% of nodes in either case. The 0.20 / 0.02 pair mirrors the equivalent contrast used in @as2 's `GridGraphGenerator`. |
| `diag_prob` | `0.005` | `0.30` | Probability that each cell adds a diagonal shortcut to its lower-right or lower-left neighbour. Sparse keeps almost no diagonals so paths must follow grid axes (long zig-zag detours around closed streets); dense gets ~30% of cells with diagonals, which materially shortens many paths and increases branching factor seen by Dijkstra. |
| `highway_edges` | `max(1, int(0.001 · S²))` | `int(0.20 · S²)` | Number of long-range "highway" edges added on top of the local grid. Scaling with `S²` (i.e. with node count) keeps the relative density consistent across sides - otherwise a 100x100 grid would look proportionally less dense than a 30x30 grid for the same fixed highway count. The `max(1, ...)` floor on sparse ensures at least one long-range shortcut exists even when `0.001 · S²` rounds to zero (e.g. `S=30`), which protects the graph from rare disconnection. Dense's 20% factor (i.e. roughly one highway for every 5 grid cells) creates the "highway-rich metropolis" topology that the dense/far cell is meant to test. |
| `local_speed` | `40.0` (default) | `40.0` (default) | Held identical between densities so the only thing that changes is the graph topology, not the per-edge cost. |
| `highway_speed` | `80.0` (default) | `80.0` (default) | Same rationale. The 2x speed advantage over local roads makes `dijkstra_time` actually prefer highways in the dense graph (relevant for the time-mode comparison). |
| `min_highway_grid_dist` | `12` (default) | `12` (default) | Minimum Manhattan distance between the two endpoints of a highway edge. Without this floor the generator could "promote" two adjacent cells into a highway, which would be indistinguishable from a local road and waste the highway budget. `12` is roughly `S/2` for the smallest tested side (`S=30`), so every highway is a *real* long-range jump, not a glorified local link. |
| `seed` | `args.seed + side` | `args.seed + side` | The base seed is reproducible, but each side gets its own offset so that the four graphs at sides `30, 50, 70, 100` are statistically independent. Without the `+ side` term, the random sequence at side=50 would just be a prefix of the sequence at side=100, making the size axis a less honest test. |
| `id_mode` | `"str"` (`"r_c"` labels) | `"str"` | Required by `pick_pair`, which parses node ids as `"row_col"` to recover the grid coordinates and compute Manhattan distance for the close/far classification. |

### What each density is meant to probe

- **Sparse** (drop=0.20, diag~0, few highways) - many forced detours,
  longer paths in raw grid steps, very little branching. Stresses an
  algorithm's *path-length* sensitivity.
- **Dense** (drop=0.02, diag=0.30, many highways) - short geometric
  paths, high branching factor at every node. Stresses an algorithm's
  *expansion-per-step* cost.

Empirically the resulting edge counts differ by ~50% (e.g. at `S=100`:
sparse ~ 15,901 edges, dense ~ 24,277), which is enough to drive
visibly different exploration counts in the plots.

---

## 2. Close vs Far Source/Destination Distance

Once a graph is built, each trial picks a `(src, dst)` pair whose
Manhattan distance on the underlying grid satisfies a `pair_kind`
constraint. The classification uses Manhattan distance - not graph
distance - because Manhattan is a cheap, monotonic proxy for "how far
apart geographically" the endpoints are, and it does not depend on the
random topology.

### Threshold table

| `pair_kind` | Manhattan distance constraint | Example at `S=30` | Example at `S=100` | Justification |
|---|---|---|---|---|
| `close` | `<= max(2, S // 8)` | `<= 3` | `<= 12` | "Short trips" - the kind of query you'd issue when navigating within a neighbourhood. The `S // 8` ratio scales the close radius with grid size so the test stays meaningful at large `S` (otherwise `<= 2` on a 100-grid would be a trivial corner-case). The `max(2, ...)` floor guarantees that at small `S` (e.g. 30) the threshold isn't degenerate, so we still sample real adjacent-but-not-trivial pairs. Close pairs stress per-query overhead and are the worst-case for **bidirectional** Dijkstra: the two frontiers have very little room to meet "in the middle", so its theoretical advantage shrinks. |
| `far` | `>= S` | `>= 30` | `>= 100` | "Cross-grid trips" - endpoints span at least the side length, so the path traverses roughly half the grid diagonal or more. Far pairs are the **showcase scenario for bidirectional Dijkstra**: forward and backward frontiers each have to cover only ~1/2 the path length, so the explored area is roughly halved compared to one-way Dijkstra. They also expose the impact of highways on `dijkstra_time` (which can take a long but fast route) versus `dijkstra_distance` (which sticks to short hops). |

Both thresholds match the close/far definition used in
[../../as2/smart_path/benchmark.py](../../as2/smart_path/benchmark.py),
which keeps the two benchmarks directly comparable.

### Sampling procedure

For each `(graph, side, pair_kind)` cell we draw `--trials` random
pairs subject to the above constraint. The picker
([`pick_pair`](benchmark.py)) retries up to 200 times to land on a
satisfying pair; if it cannot (extremely rare on these graphs), it
falls through to a uniform random pair so the benchmark never hangs.

### What each pair-kind is meant to probe

- **Close** - small search radius; tests whether each algorithm has
  any per-query overhead that dominates when the answer is found
  quickly. Bidirectional Dijkstra's setup cost is highest here, so
  this cell often shows it explore *more* than one-way Dijkstra on a
  per-query basis.
- **Far** - large search radius; tests asymptotic exploration
  behaviour. Bidirectional should explore noticeably fewer nodes here
  because each direction only has to grow to ~1/2 of the total path
  length.

---

## 3. Random Avoidance (size scaled with grid side)

Every query passes a non-empty `avoid_nodes` set into the algorithm to
exercise the constraint-handling code path. The size of that set is
deterministic per side, not a CLI flag.

| Function | Formula | Examples (`S = 30, 50, 70, 100`) |
|---|---|---|
| [`avoid_count_for`](benchmark.py) | `max(2, S // 4)` | `7, 12, 17, 25` forbidden nodes |

### Justification

- **Linear in `S`, not in `S²`**: at 1% of nodes the count would jump
  to `100` forbidden nodes on the 100-grid, which can carve a
  disconnecting cut on the sparse graph (`drop_prob=0.20`) and push
  many trials to "no path found". The `S // 4` schedule keeps the
  challenge growing with the graph (more forbidden nodes on bigger
  grids) while staying well below the bond-percolation threshold.
- **Floor of 2**: ensures even very small grids still see *some*
  forbidden nodes, so the avoid-handling branch is exercised in every
  cell.
- **Random sample, src/dst excluded**:
  [`random_avoid_nodes`](benchmark.py) calls `rng.sample` over the node
  pool minus `src` and `dst`. Avoid sets are picked once per query and
  shared across all three algorithms (see Section 5).

### What this is meant to probe

A non-trivial fraction of close-pair queries will have an "easy"
optimal path that crosses one of the forbidden nodes, forcing a
detour. That detour shows up as a higher `nodes_explored` and
`runtime_ms` than the same query would produce with empty avoidance.
We don't sweep avoidance as a separate axis; the fixed schedule keeps
the report focused on the four (graph x pair) cells.

---

## 4. Metrics Recorded Per Query

Each query produces one row in `benchmark_results.csv` with four
algorithmic outcomes, plus bookkeeping fields:

| Metric | Source | What it captures |
|---|---|---|
| `nodes_explored` | algorithm result dict | Number of nodes finalised by the search before termination. Algorithm-agnostic measure of work done; the primary signal for bidirectional Dijkstra's advantage. |
| `total_distance` | algorithm result dict | Sum of edge `distance` along the returned path (km). For `dijkstra_distance` and `bidi_distance` this is the optimum; for `dijkstra_time` it is the distance of the *time-optimal* path, which is generally > the distance optimum. |
| `total_time` | algorithm result dict | Sum of edge travel times along the returned path (h), evaluated against the live time-of-day profile. Lowest for `dijkstra_time` by construction. |
| `runtime_ms` | `time.perf_counter()` around the algorithm call | Wall-clock time spent inside the algorithm only - pair-picking and avoid-sampling are excluded so this reflects pure algorithmic cost. |

Bookkeeping fields (`graph`, `side`, `nodes`, `edges`, `algorithm`,
`pair_kind`, `src`, `dst`, `avoid_count`, `found`) accompany every row
so the CSV is self-describing for post-hoc analysis.

### Aggregations in [plot_benchmark.py](plot_benchmark.py)

For each metric the plotter computes the mean across trials per
`(graph, side, algorithm, pair_kind)` cell and writes one bar chart
per (graph, pair_kind) into a metric-specific folder:

- [compare_node_explore/](compare_node_explore/) - bars of mean `nodes_explored`
- [compare_total_distance/](compare_total_distance/) - bars of mean `total_distance`
- [compare_total_time/](compare_total_time/) - bars of mean `total_time`
- [compare_runtime/](compare_runtime/) - bars of mean `runtime_ms`

Each folder contains `sparse_close.png`, `sparse_far.png`,
`dense_close.png`, `dense_far.png`, and a 2x2 `overview.png`.

---

## 5. Fair-Comparison Methodology (shared queries per cell)

A subtle but essential property: **for each `(graph, side, pair_kind)`
cell, the same list of `(src, dst, avoid_nodes)` triples is fed to all
three algorithms**.

### Why this matters

If each algorithm picked its own random pairs, the rng state would
diverge between calls and the three algorithms would end up running on
different query distributions. With only 20 trials per cell, the
sample variance can flip the *direction* of the comparison: at one
point in development we observed `dijkstra_time` reporting a higher
mean travel time than `dijkstra_distance`, even though
`dijkstra_time` is provably <= on any *given* query. The cause was
that the two algorithms were running on different random pairs whose
mean Manhattan distance happened to differ.

### How it's enforced

[`make_queries`](benchmark.py) is called once per cell to produce the
trial list, and the inner loop runs all three algorithms over that
shared list before the rng advances:

```python
for pair_kind in pair_kinds:
    queries = make_queries(graph, side, pair_kind, args.trials, rng)
    for algorithm in ALGORITHMS:
        for src, dst, avoid_nodes in queries:
            run_one_query(...)
```

### Invariants this guarantees

After a run, every cell satisfies:

| Invariant | Why |
|---|---|
| `mean_distance` identical for `dijkstra_distance` and `bidi_distance` | Both solve shortest-distance on the same query set |
| `mean_time(dijkstra_time) <= mean_time(dijkstra_distance)` | `dijkstra_time` optimises the very metric it reports |
| `mean_distance(dijkstra_distance) <= mean_distance(dijkstra_time)` | Dual property: the time-optimal path can detour for speed |

The CSV exposes `src` and `dst` per row, so these invariants can be
spot-checked downstream.

---

## 6. Reading the Four Cells

Putting it together, the 2x2 layout in
[compare_node_explore/overview.png](compare_node_explore/overview.png)
(and equivalently in the three other metric folders) is interpreted as:

| | close pairs | far pairs |
|---|---|---|
| **sparse** | tests overhead on tight queries through a holey grid | tests detour-heavy worst case for one-way Dijkstra |
| **dense** | tests overhead on tight queries through a high-branching grid | tests highway exploitation and bidirectional speedup |

Together they cover the four corners of "how much of the graph the
algorithm has to look at" - which is what `nodes_explored` and
`runtime_ms` measure - and "how the chosen path differs across cost
models" - which is what `total_distance` and `total_time` measure.
