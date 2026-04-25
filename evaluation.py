"""
evaluation.py — Comprehensive benchmarking and empirical evaluation.

Scenarios covered:
    1. Random queries (baseline)
    2. Hub-to-hub queries (cache effectiveness)
    3. Queries with avoid_nodes constraints
    4. Departure-hour impact on same route
    5. Algorithm comparison: Standard vs Bidirectional Dijkstra
    6. Graph-size scaling analysis (20x20 -> 100x100)
    7. Cache hit vs miss comparison
"""

import time
import random


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------

def benchmark_single_query(graph, cache, source, destination,
                           departure_hour, mode,
                           avoid_nodes=None, avoid_edges=None,
                           use_cache=True):
    """
    Benchmark a single query.
    Returns (result_dict, elapsed_ms, cache_hit).
    """
    from cache import run_query_cached
    from algorithms import dijkstra_distance, dijkstra_time

    start = time.perf_counter()

    if use_cache:
        result, hit = run_query_cached(
            graph, cache, source, destination,
            departure_hour, mode, avoid_nodes, avoid_edges
        )
    else:
        if mode == "distance":
            result = dijkstra_distance(graph, source, destination,
                                       avoid_nodes, avoid_edges,
                                       departure_hour)
        else:
            result = dijkstra_time(graph, source, destination,
                                   avoid_nodes, avoid_edges,
                                   departure_hour)
        hit = False

    duration = (time.perf_counter() - start) * 1000
    return (result, duration, hit)


def benchmark_scenario(graph, cache, queries, label="Scenario"):
    """Run a batch of queries and print summary statistics."""
    print(f"\n=== {label} ===")

    total_time = 0.0
    hits = 0
    misses = 0
    no_path = 0
    total_explored = 0

    for (source, destination, hour, mode, avoid_nodes, avoid_edges) in queries:
        result, duration, hit = benchmark_single_query(
            graph, cache, source, destination, hour, mode,
            avoid_nodes, avoid_edges
        )
        total_time += duration
        if hit:
            hits += 1
        else:
            misses += 1
        if result is None:
            no_path += 1
        elif isinstance(result, dict) and "nodes_explored" in result:
            total_explored += result["nodes_explored"]

    n = len(queries)
    avg_time = total_time / n if n else 0
    avg_explored = total_explored / max(misses, 1)

    print(f"Total queries:        {n}")
    print(f"Cache hits:           {hits}")
    print(f"Cache misses:         {misses}")
    print(f"No path found:        {no_path}")
    print(f"Average time:         {avg_time:.2f} ms")
    print(f"Total time:           {total_time:.2f} ms")
    print(f"Avg nodes explored:   {avg_explored:.0f}")


# ---------------------------------------------------------------------------
# Query generators
# ---------------------------------------------------------------------------

def generate_random_queries(graph, count=100, seed=42):
    """Generate random queries across all nodes."""
    random.seed(seed)
    nodes = list(graph.nodes)
    queries = []

    for _ in range(count):
        source = random.choice(nodes)
        destination = random.choice(nodes)
        while destination == source:
            destination = random.choice(nodes)
        hour = random.choice([0, 8, 12, 18])
        mode = random.choice(["distance", "time"])
        queries.append((source, destination, hour, mode, set(), set()))

    return queries


def generate_hub_queries(hubs, count=100, seed=42):
    """Generate queries exclusively between hub nodes."""
    random.seed(seed)
    queries = []

    for _ in range(count):
        if len(hubs) < 2:
            break
        source = random.choice(hubs)
        destination = random.choice(hubs)
        while destination == source:
            destination = random.choice(hubs)
        hour = random.choice([0, 8, 12, 18])
        mode = random.choice(["distance", "time"])
        queries.append((source, destination, hour, mode, set(), set()))

    return queries


def generate_avoidance_queries(graph, count=50, num_avoid=5, seed=42):
    """Generate queries that include avoid_nodes constraints."""
    random.seed(seed)
    nodes = list(graph.nodes)
    queries = []

    for _ in range(count):
        source = random.choice(nodes)
        destination = random.choice(nodes)
        while destination == source:
            destination = random.choice(nodes)

        # Pick random nodes to avoid (excluding source and destination)
        candidates = [n for n in nodes if n != source and n != destination]
        avoid = set(random.sample(candidates,
                                  min(num_avoid, len(candidates))))

        hour = random.choice([0, 8, 12, 18])
        mode = random.choice(["distance", "time"])
        queries.append((source, destination, hour, mode, avoid, set()))

    return queries


# ---------------------------------------------------------------------------
# Scenario: Algorithm comparison with nodes-explored tracking
# ---------------------------------------------------------------------------

def compare_algorithms(graph, queries, label="Algorithm Comparison"):
    """Compare Standard vs Bidirectional Dijkstra on distance queries."""
    from algorithms import dijkstra_distance, bidirectional_dijkstra_distance

    print(f"\n=== {label} ===")

    standard_times = []
    bidir_times = []
    standard_explored = []
    bidir_explored = []

    for (source, destination, hour, mode, avoid_nodes, avoid_edges) in queries:
        if mode != "distance":
            continue

        # Standard Dijkstra
        start = time.perf_counter()
        result_1 = dijkstra_distance(graph, source, destination,
                                     avoid_nodes, avoid_edges, hour)
        standard_times.append((time.perf_counter() - start) * 1000)

        # Bidirectional Dijkstra
        start = time.perf_counter()
        result_2 = bidirectional_dijkstra_distance(
            graph, source, destination, avoid_nodes, avoid_edges, hour)
        bidir_times.append((time.perf_counter() - start) * 1000)

        if result_1 and result_2:
            # Verify both find the same optimal distance
            assert abs(result_1["total_distance"] - result_2["total_distance"]) < 0.01, \
                f"Distance mismatch: {result_1['total_distance']} vs {result_2['total_distance']}"
            standard_explored.append(result_1["nodes_explored"])
            bidir_explored.append(result_2["nodes_explored"])

    n = len(standard_times)
    avg_standard = sum(standard_times) / n if n else 0
    avg_bidir = sum(bidir_times) / n if n else 0
    avg_std_explored = sum(standard_explored) / len(standard_explored) if standard_explored else 0
    avg_bid_explored = sum(bidir_explored) / len(bidir_explored) if bidir_explored else 0

    print(f"Queries tested:                  {n}")
    print(f"Avg time  (Standard):            {avg_standard:.2f} ms")
    print(f"Avg time  (Bidirectional):       {avg_bidir:.2f} ms")
    print(f"Time speedup:                    {avg_standard / avg_bidir:.2f}x" if avg_bidir > 0 else "N/A")
    print(f"Avg nodes explored (Standard):   {avg_std_explored:.0f}")
    print(f"Avg nodes explored (Bidir):      {avg_bid_explored:.0f}")
    print(f"Node reduction:                  {(1 - avg_bid_explored / avg_std_explored) * 100:.1f}%" if avg_std_explored > 0 else "N/A")


# ---------------------------------------------------------------------------
# Scenario: Departure-hour impact
# ---------------------------------------------------------------------------

def compare_departure_hours(graph, source, destination):
    """Show how the same route varies across different departure hours."""
    from algorithms import dijkstra_time

    print(f"\n=== Departure-Hour Impact: {source} -> {destination} ===")
    print(f"{'Hour':>6}  {'Travel Time':>12}  {'Nodes Explored':>15}  {'Path Length':>12}")
    print("-" * 55)

    for hour in range(0, 24, 2):
        result = dijkstra_time(graph, source, destination,
                               departure_hour=hour)
        if result:
            print(f"{hour:>6}  {result['total_time']:>12.4f}  "
                  f"{result['nodes_explored']:>15}  "
                  f"{len(result['path']):>12}")
        else:
            print(f"{hour:>6}  {'No path':>12}")


# ---------------------------------------------------------------------------
# Scenario: Graph-size scaling
# ---------------------------------------------------------------------------

def scaling_analysis(sizes=None, num_queries=20, seed=42):
    """
    Generate graphs of increasing size and measure Dijkstra performance.

    This demonstrates how runtime scales with graph size to empirically
    verify the O((V+E) log V) theoretical complexity.
    """
    from generator import generate_graph
    from algorithms import dijkstra_distance

    if sizes is None:
        sizes = [(20, 20), (30, 30), (50, 50), (70, 70), (100, 100)]

    print(f"\n=== Graph-Size Scaling Analysis ===")
    print(f"{'Size':>10}  {'Nodes':>7}  {'Edges':>7}  "
          f"{'Avg ms':>8}  {'Avg Explored':>13}  {'E·logV':>10}")
    print("-" * 68)

    for rows, cols in sizes:
        graph = generate_graph(rows=rows, cols=cols, diag_prob=0.20,
                               highway_edges=int(rows * cols * 0.18),
                               seed=seed, id_mode="str")

        random.seed(seed)
        nodes = list(graph.nodes)
        times_ms = []
        explored_counts = []

        for _ in range(num_queries):
            src = random.choice(nodes)
            dst = random.choice(nodes)
            while dst == src:
                dst = random.choice(nodes)

            start = time.perf_counter()
            result = dijkstra_distance(graph, src, dst)
            elapsed = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed)
            if result:
                explored_counts.append(result["nodes_explored"])

        v = graph.node_count()
        e = graph.edge_count()
        avg_ms = sum(times_ms) / len(times_ms)
        avg_explored = (sum(explored_counts) / len(explored_counts)
                        if explored_counts else 0)

        import math
        e_log_v = e * math.log2(v) if v > 0 else 0

        print(f"{rows}x{cols:>3}  {v:>7}  {e:>7}  "
              f"{avg_ms:>8.2f}  {avg_explored:>13.0f}  {e_log_v:>10.0f}")


# ---------------------------------------------------------------------------
# Scenario: Cache hit vs miss
# ---------------------------------------------------------------------------

def test_cache_effectiveness(graph, cache, queries):
    """
    Measure cache effectiveness by running the same queries twice:
    first without cache, then with cache.
    """
    from cache import PathCache, run_query_cached

    print("\n=== Cache Effectiveness ===")

    # Use a fresh cache for this test
    test_cache = PathCache()

    # First pass: compute and store in cache
    first_times = []
    for (source, destination, hour, mode, avoid_nodes, avoid_edges) in queries:
        result, duration, _ = benchmark_single_query(
            graph, test_cache, source, destination, hour, mode,
            avoid_nodes, avoid_edges, use_cache=True
        )
        first_times.append(duration)

    # Second pass: same queries should now be cache hits
    second_times = []
    for (source, destination, hour, mode, avoid_nodes, avoid_edges) in queries:
        result, duration, _ = benchmark_single_query(
            graph, test_cache, source, destination, hour, mode,
            avoid_nodes, avoid_edges, use_cache=True
        )
        second_times.append(duration)

    avg_miss = sum(first_times) / len(first_times) if first_times else 0
    avg_hit = sum(second_times) / len(second_times) if second_times else 0

    print(f"First run (cache miss):   {avg_miss:.2f} ms avg")
    print(f"Second run (cache hit):   {avg_hit:.4f} ms avg")
    if avg_hit > 0:
        print(f"Speedup:                  {avg_miss / avg_hit:.0f}x")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from graph import Graph
    from generator import generate_graph
    from cache import PathCache, identify_hubs, precompute_hub_paths

    print("=" * 60)
    print("  SMART PATH FINDER — EMPIRICAL EVALUATION")
    print("=" * 60)

    # ---- Setup ----
    print("\nGenerating test graph (70x70)...")
    graph = generate_graph(rows=70, cols=70, diag_prob=0.20,
                           highway_edges=900, seed=42, id_mode="str")
    print(f"Generated: {graph.node_count()} nodes, {graph.edge_count()} edges\n")

    print("Initializing cache and hubs...")
    cache = PathCache()
    hubs = identify_hubs(graph, top_n=30)

    print("Precomputing hub paths...")
    precompute_hub_paths(graph, cache, hubs, departure_hours=[0, 8, 12, 18])
    print(f"Cache size: {cache.size()}")

    # ---- Scenario 1: Random queries ----
    queries = generate_random_queries(graph, count=200, seed=42)
    benchmark_scenario(graph, cache, queries,
                       "Scenario 1: Random Queries (Baseline)")

    # ---- Scenario 2: Hub-to-hub queries (cache hits) ----
    hub_queries = generate_hub_queries(hubs, count=100, seed=42)
    benchmark_scenario(graph, cache, hub_queries,
                       "Scenario 2: Hub-to-Hub Queries (Cache Hits)")

    # ---- Scenario 3: Queries with avoidance constraints ----
    avoid_queries = generate_avoidance_queries(graph, count=50,
                                               num_avoid=10, seed=42)
    benchmark_scenario(graph, cache, avoid_queries,
                       "Scenario 3: Queries with Avoidance Constraints")

    # ---- Scenario 4: Departure-hour impact ----
    nodes = list(graph.nodes)
    compare_departure_hours(graph, "0_0", "69_69")

    # ---- Scenario 5: Algorithm comparison ----
    compare_algorithms(graph, queries,
                       "Scenario 5: Standard vs Bidirectional Dijkstra")

    # ---- Scenario 6: Graph-size scaling ----
    scaling_analysis(
        sizes=[(20, 20), (30, 30), (50, 50), (70, 70), (100, 100)],
        num_queries=20, seed=42
    )

    # ---- Scenario 7: Cache hit vs miss ----
    test_cache_effectiveness(graph, cache, queries[:30])

    print("\n" + "=" * 60)
    print("  EVALUATION COMPLETE")
    print("=" * 60)