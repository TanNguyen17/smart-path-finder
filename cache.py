"""
cache.py — Path caching, hub identification, and precomputation.

PathCache stores previously computed routing results keyed by
(source, destination, departure_hour, mode, avoid_nodes, avoid_edges).

Hub precomputation identifies the highest-degree nodes in the graph
and pre-calculates routes between them at representative hours,
so that the most common long-distance queries return instantly.

Complexity of hub precomputation:
    Time:   O(H^2 * D * (V + E) log V)   where H = hubs, D = departure hours
    Space:  O(H^2 * D * P)               where P = average path length stored
"""

class PathCache:
    """Dictionary-based cache for routing results."""

    def __init__(self):
        self.cache = {}

    def _make_key(self, source, destination, departure_hour, mode,
                  avoid_nodes, avoid_edges):
        """Build a hashable cache key with canonical ordering."""
        source = str(source)
        destination = str(destination)
        departure_hour = int(departure_hour)
        mode = str(mode)

        # Convert sets to frozensets for hashability
        avoid_nodes_key = frozenset(avoid_nodes) if avoid_nodes else frozenset()

        # For edges, convert each tuple to a canonical form (sorted pair)
        if avoid_edges:
            normalized_edges = frozenset(
                tuple(sorted(edge)) for edge in avoid_edges
            )
        else:
            normalized_edges = frozenset()

        return (source, destination, departure_hour, mode,
                avoid_nodes_key, normalized_edges)

    def get(self, source, destination, departure_hour, mode,
            avoid_nodes=None, avoid_edges=None):
        """Return cached result or None on miss."""
        key = self._make_key(source, destination, departure_hour, mode,
                             avoid_nodes, avoid_edges)
        return self.cache.get(key, None)

    def set(self, source, destination, departure_hour, mode,
            avoid_nodes, avoid_edges, result, max_size=5000):
        """
        Store a result in the cache. 
        If the cache exceeds max_size, the oldest 10% of entries are removed 
        to manage memory (FIFO eviction).
        """
        if len(self.cache) >= max_size:
            # Drop the oldest 10% of entries
            num_to_remove = max(1, int(max_size * 0.1))
            keys = list(self.cache.keys())
            for i in range(num_to_remove):
                del self.cache[keys[i]]

        key = self._make_key(source, destination, departure_hour, mode,
                             avoid_nodes, avoid_edges)
        self.cache[key] = result

    def clear(self):
        """Remove all entries."""
        self.cache.clear()

    def invalidate(self):
        """Invalidate the entire cache (e.g. after a weekly data update)."""
        removed = len(self.cache)
        self.cache.clear()
        return removed

    def size(self):
        """Return the number of cached entries."""
        return len(self.cache)


def run_query_cached(graph, cache, source, destination,
                     departure_hour, mode,
                     avoid_nodes=None, avoid_edges=None):
    """
    Run a routing query, checking the cache first.

    Returns (result_dict, cache_hit: bool).
    """
    from algorithms import dijkstra_distance, dijkstra_time, bidirectional_dijkstra_distance

    avoid_nodes = avoid_nodes or set()
    avoid_edges = avoid_edges or set()

    # 1. Try cache first
    cached = cache.get(source, destination, departure_hour, mode,
                       avoid_nodes, avoid_edges)
    if cached is not None:
        return (cached, True)

    # 2. Cache miss: compute
    if mode == "distance":
        result = bidirectional_dijkstra_distance(graph, source, destination,
                                                 avoid_nodes, avoid_edges, departure_hour)
    elif mode == "distance_std":
        result = dijkstra_distance(graph, source, destination,
                                  avoid_nodes, avoid_edges, departure_hour)
    elif mode == "time":
        result = dijkstra_time(graph, source, destination,
                               avoid_nodes, avoid_edges, departure_hour)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # 3. Store in cache
    cache.set(source, destination, departure_hour, mode,
              avoid_nodes, avoid_edges, result)

    return (result, False)


def identify_hubs(graph, top_n=50):
    """
    Return list of top_n node IDs with highest degree (most connections).

    High-degree nodes act as natural "hubs" — major intersections through
    which many routes pass.  Precomputing paths between them maximises
    the probability of cache hits for long-distance queries.
    """
    degree = {}
    for node in graph.nodes:
        degree[node] = len(graph.get_neighbors(node))

    sorted_nodes = sorted(degree.keys(), key=lambda n: degree[n],
                          reverse=True)
    return sorted_nodes[:top_n]


def precompute_hub_paths(graph, cache, hubs, departure_hours=None):
    """
    Precompute paths between all pairs of hubs at given hours.

    Returns the number of paths precomputed (int).
    """
    from algorithms import dijkstra_distance, dijkstra_time

    if departure_hours is None:
        departure_hours = [0, 8, 12, 18]

    count = 0
    total_pairs = len(hubs) * (len(hubs) - 1) * len(departure_hours) * 2

    for source in hubs:
        for destination in hubs:
            if source == destination:
                continue

            for hour in departure_hours:
                # Distance mode
                result_distance = dijkstra_distance(
                    graph, source, destination, departure_hour=hour)
                cache.set(source, destination, hour, "distance",
                          set(), set(), result_distance)
                count += 1

                # Time mode
                result_time = dijkstra_time(
                    graph, source, destination, departure_hour=hour)
                cache.set(source, destination, hour, "time",
                          set(), set(), result_time)
                count += 1

                if count % 100 == 0:
                    print(f"Precomputed {count}/{total_pairs} hub paths")

    print(f"Precomputed {count} hub paths")
    return count


def simulate_weekly_update(graph, cache, hubs=None, departure_hours=None, seed=None):
    """
    Simulate weekly travel time update:
    1. Invalidate cache
    2. Optionally re-precompute hub paths

    Returns: number of paths precomputed (0 if no hubs provided)
    """
    from generator import update_travel_times

    old_version = getattr(graph, "data_version", 1)
    updated_edges = update_travel_times(graph, seed=seed)
    graph.data_version = old_version + 1
    removed = cache.invalidate()

    precomputed = 0
    if hubs:
        precomputed = precompute_hub_paths(graph, cache, hubs, departure_hours)

    return {
        "old_version": old_version,
        "new_version": graph.data_version,
        "cache_size": cache.size(),
        "cache_entries_removed": removed,
        "precomputed_paths": precomputed,
        "updated_edges": updated_edges
    }
