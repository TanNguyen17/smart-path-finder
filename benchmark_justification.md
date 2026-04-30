# Benchmark Justification

This document explains how the empirical comparison in
[benchmark.py](benchmark.py) was set up: how "sparse" vs "dense" graphs
are constructed, and how "close" vs "far" source/destination pairs are
selected.

The goal of the benchmark is to compare the number of nodes each of the
three pathfinding algorithms expands across realistically distinct
scenarios. Every choice below is made so that the four reported cells
(sparse-close, sparse-far, dense-close, dense-far) actually probe
different algorithmic regimes rather than shades of the same setup.

---

## 1. Sparse vs Dense Graph Definitions

Both densities are produced by the same
[`generate_graph`](generator.py) routine — only the keyword arguments
differ. Throughout the table below, `S` denotes the grid side length
(`rows = cols = S`), supplied via the `--sides` CLI flag.

### Parameter table

| Parameter | Sparse value | Dense value | Justification |
|---|---|---|---|
| `rows`, `cols` | `S` | `S` | Square grid so the close/far Manhattan thresholds (which scale with `S`) apply uniformly to both densities. The total number of nodes is `S²`, which lets us quote a single "size" axis on the plots. |
| `drop_prob` | `0.20` | `0.02` | Probability that each candidate base 4-grid edge is *omitted* during construction. Sparse keeps ~80% of streets ("many closed roads"), dense keeps ~98%. Both stay well above the 2D bond-percolation threshold `p_c = 0.5`, so the giant connected component covers >99% of nodes in either case. The 0.20 / 0.02 pair mirrors the equivalent contrast used in @as2 's `GridGraphGenerator`. |
| `diag_prob` | `0.005` | `0.30` | Probability that each cell adds a diagonal shortcut to its lower-right or lower-left neighbour. Sparse keeps almost no diagonals so paths must follow grid axes (long zig-zag detours around closed streets); dense gets ~30% of cells with diagonals, which materially shortens many paths and increases branching factor seen by Dijkstra. |
| `highway_edges` | `max(1, int(0.001 · S²))` | `int(0.20 · S²)` | Number of long-range "highway" edges added on top of the local grid. Scaling with `S²` (i.e. with node count) keeps the relative density consistent across sides — otherwise a 100×100 grid would look proportionally less dense than a 30×30 grid for the same fixed highway count. The `max(1, ...)` floor on sparse ensures at least one long-range shortcut exists even when `0.001 · S²` rounds to zero (e.g. `S=30`), which protects the graph from rare disconnection. Dense's 20% factor (i.e. roughly one highway for every 5 grid cells) creates the "highway-rich metropolis" topology that the dense/far cell is meant to test. |
| `local_speed` | `40.0` (default) | `40.0` (default) | Held identical between densities so the only thing that changes is the graph topology, not the per-edge cost. |
| `highway_speed` | `80.0` (default) | `80.0` (default) | Same rationale. The 2× speed advantage over local roads makes `dijkstra_time` actually prefer highways in the dense graph (relevant for the time-mode comparison). |
| `min_highway_grid_dist` | `12` (default) | `12` (default) | Minimum Manhattan distance between the two endpoints of a highway edge. Without this floor the generator could "promote" two adjacent cells into a highway, which would be indistinguishable from a local road and waste the highway budget. `12` is roughly `S/2` for the smallest tested side (`S=30`), so every highway is a *real* long-range jump, not a glorified local link. |
| `seed` | `args.seed + side` | `args.seed + side` | The base seed is reproducible, but each side gets its own offset so that the four graphs at sides `30, 50, 70, 100` are statistically independent. Without the `+ side` term, the random sequence at side=50 would just be a prefix of the sequence at side=100, making the size axis a less honest test. |
| `id_mode` | `"str"` (`"r_c"` labels) | `"str"` | Required by `pick_pair`, which parses node ids as `"row_col"` to recover the grid coordinates and compute Manhattan distance for the close/far classification. |

### What each density is meant to probe

- **Sparse** (drop=0.20, diag≈0, few highways) — many forced detours,
  longer paths in raw grid steps, very little branching. Stresses an
  algorithm's *path-length* sensitivity.
- **Dense** (drop=0.02, diag=0.30, many highways) — short geometric
  paths, high branching factor at every node. Stresses an algorithm's
  *expansion-per-step* cost.

Empirically the resulting edge counts differ by ~50% (e.g. at `S=100`:
sparse ≈ 15,901 edges, dense ≈ 24,277), which is enough to drive
visibly different exploration counts in the plots.

---

## 2. Close vs Far Source/Destination Distance

Once a graph is built, each trial picks a `(src, dst)` pair whose
Manhattan distance on the underlying grid satisfies a `pair_kind`
constraint. The classification uses Manhattan distance — not graph
distance — because Manhattan is a cheap, monotonic proxy for "how far
apart geographically" the endpoints are, and it does not depend on the
random topology.

### Threshold table

| `pair_kind` | Manhattan distance constraint | Example at `S=30` | Example at `S=100` | Justification |
|---|---|---|---|---|
| `close` | `≤ max(2, S // 8)` | `≤ 3` | `≤ 12` | "Short trips" — the kind of query you'd issue when navigating within a neighbourhood. The `S // 8` ratio scales the close radius with grid size so the test stays meaningful at large `S` (otherwise `≤ 2` on a 100-grid would be a trivial corner-case). The `max(2, ...)` floor guarantees that at small `S` (e.g. 30) the threshold isn't degenerate, so we still sample real adjacent-but-not-trivial pairs. Close pairs are the worst-case for **bidirectional** Dijkstra: the two frontiers have very little room to meet "in the middle", so its theoretical advantage shrinks. |
| `far` | `≥ S` | `≥ 30` | `≥ 100` | "Cross-grid trips" — endpoints span at least the side length, so the path traverses roughly half the grid diagonal or more. Far pairs are the **showcase scenario for bidirectional Dijkstra**: forward and backward frontiers each have to cover only ~½ the path length, so the explored area is roughly halved compared to one-way Dijkstra. They also expose the impact of highways on `dijkstra_time` (which can take a long but fast route) versus `dijkstra_distance` (which sticks to short hops). |

Both thresholds match the close/far definition used in
[as2/smart_path/benchmark.py](../as2/smart_path/benchmark.py), which
keeps the two benchmarks directly comparable.

### Sampling procedure

For each `(graph, side, algorithm, pair_kind)` cell we draw `--trials`
random pairs subject to the above constraint. The picker
([`pick_pair`](benchmark.py)) retries up to 200 times to land on a
satisfying pair; if it cannot (extremely rare on these graphs), it
falls through to a uniform random pair so the benchmark never hangs.

### What each pair-kind is meant to probe

- **Close** — small search radius; tests whether each algorithm has
  any per-query overhead that dominates when the answer is found
  quickly. Bidirectional Dijkstra's setup cost is highest here, so
  this cell often shows it explore *more* than one-way Dijkstra on a
  per-query basis.
- **Far** — large search radius; tests asymptotic exploration
  behaviour. Bidirectional should explore noticeably fewer nodes here
  because each direction only has to grow to ~½ of the total path
  length.

---

## 3. Reading the four cells

Putting it together, the four panels of
[`compare_explorations_overview.png`](compare_explorations_overview.png)
are interpreted as:

| | close pairs | far pairs |
|---|---|---|
| **sparse** | tests overhead on tight queries through a holey grid | tests detour-heavy worst case for one-way Dijkstra |
| **dense** | tests overhead on tight queries through a high-branching grid | tests highway exploitation and bidirectional speedup |

Together they cover the four corners of "how much of the graph the
algorithm has to look at" — which is exactly what `nodes_explored`
measures.
