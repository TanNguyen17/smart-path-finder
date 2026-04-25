"""
algorithms.py — Pathfinding algorithms for the Smart Path Finder.

Implements three routing strategies, all built on the custom MinHeap:

1. dijkstra_distance   — shortest path by total *distance*
2. dijkstra_time       — shortest path by total *travel time* (time-aware)
3. bidirectional_dijkstra_distance — bidirectional search for distance

Every function returns a dict:
    {
        "path"           : list[str],       # ordered node sequence
        "total_distance" : float,
        "total_time"     : float,
        "nodes_explored" : int              # number of nodes finalised
    }
    or None if no path exists.

Time complexity  (with custom MinHeap):  O((V + E) log V)
Space complexity:                        O(V + E)
"""

from heap import MinHeap


def dijkstra_distance(graph, source, destination,
                      avoid_nodes=None, avoid_edges=None,
                      departure_hour=0):
    """
    Find the path that minimises total *distance* using Dijkstra's algorithm.

    Parameters
    ----------
    graph          : Graph instance
    source, dest   : node identifiers
    avoid_nodes    : set of node IDs to skip
    avoid_edges    : set of (u, v) tuples to skip
    departure_hour : int 0-23, used to compute travel time along the path

    Returns  dict | None
    """
    source = str(source)
    destination = str(destination)
    avoid_nodes = avoid_nodes or set()
    avoid_edges = avoid_edges or set()

    distance = {}       # node -> best known distance from source
    parent = {}         # node -> previous node on best path
    visited = set()     # nodes already finalised
    nodes_explored = 0  # counter for empirical evaluation

    distance[source] = 0.0
    parent[source] = None

    heap = MinHeap()
    heap.push(0.0, source)

    while heap:
        current_distance, u = heap.pop()

        if u in visited:
            continue
        visited.add(u)
        nodes_explored += 1

        # early exit: destination reached
        if u == destination:
            break

        for v, edge_distance, edge_travel_times in graph.get_neighbors(u, avoid_nodes, avoid_edges):
            if v in visited:
                continue

            new_distance = current_distance + edge_distance

            if v not in distance or new_distance < distance[v]:
                distance[v] = new_distance
                parent[v] = u
                heap.push(new_distance, v)

    if destination not in parent:
        return None

    # reconstruct path
    path = []
    node = destination
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()

    total_distance = distance[destination]

    # compute travel time along this specific path
    total_travel_time = 0.0
    cumulative_time = 0.0

    for i in range(len(path) - 1):
        u_node, v_node = path[i], path[i + 1]

        for neighbor_v, edge_dist, travel_times in graph.adjacent[u_node]:
            if neighbor_v == v_node:
                current_hour = (departure_hour + int(cumulative_time)) % 24
                edge_time = travel_times[current_hour]
                total_travel_time += edge_time
                cumulative_time += edge_time
                break

    return {
        "path": path,
        "total_distance": total_distance,
        "total_time": total_travel_time,
        "nodes_explored": nodes_explored
    }


def dijkstra_time(graph, source, destination,
                  avoid_nodes=None, avoid_edges=None,
                  departure_hour=0):
    """
    Find the path that minimises total *travel time* using Dijkstra's
    algorithm with time-aware edge weights.

    At each expansion the algorithm computes the current hour-of-day
    based on elapsed travel time and looks up the corresponding
    travel-time value for the edge being relaxed.

    Returns  dict | None
    """
    source = str(source)
    destination = str(destination)
    avoid_nodes = avoid_nodes or set()
    avoid_edges = avoid_edges or set()

    time_cost = {}
    parent = {}
    visited = set()
    nodes_explored = 0

    time_cost[source] = 0.0
    parent[source] = None

    heap = MinHeap()
    heap.push(0.0, source)

    while heap:
        current_time, u = heap.pop()

        if u in visited:
            continue
        visited.add(u)
        nodes_explored += 1

        if u == destination:
            break

        for v, edge_distance, edge_travel_times in graph.get_neighbors(u, avoid_nodes, avoid_edges):
            if v in visited:
                continue

            current_hour = (departure_hour + int(current_time)) % 24
            edge_time = edge_travel_times[current_hour]
            new_time = current_time + edge_time

            if v not in time_cost or new_time < time_cost[v]:
                time_cost[v] = new_time
                parent[v] = u
                heap.push(new_time, v)

    if destination not in parent:
        return None

    # reconstruct path
    path = []
    node = destination
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()

    total_travel_time = time_cost[destination]

    # compute distance along this specific path
    total_distance = 0.0
    for i in range(len(path) - 1):
        u_node, v_node = path[i], path[i + 1]

        for neighbor_v, edge_dist, travel_times in graph.adjacent[u_node]:
            if neighbor_v == v_node:
                total_distance += edge_dist
                break

    return {
        "path": path,
        "total_distance": total_distance,
        "total_time": total_travel_time,
        "nodes_explored": nodes_explored
    }


def bidirectional_dijkstra_distance(graph, source, destination,
                                    avoid_nodes=None, avoid_edges=None,
                                    departure_hour=0):
    """
    Bidirectional Dijkstra for *distance* minimisation.

    Two search frontiers expand simultaneously — one from *source* and
    one from *destination*.  The algorithm terminates once
    ``min_forward + min_backward >= best_distance``, guaranteeing
    optimality while typically exploring ~50 % fewer nodes.

    Note: bidirectional search is only correct for distance (a static,
    symmetric weight).  Travel *time* is direction- and departure-
    dependent, so bidirectional search is not applied to time queries.

    Returns  dict | None
    """
    source = str(source)
    destination = str(destination)
    avoid_nodes = avoid_nodes or set()
    avoid_edges = avoid_edges or set()

    if source == destination:
        return {"path": [source], "total_distance": 0.0,
                "total_time": 0.0, "nodes_explored": 1}

    # Forward search (from source)
    distance_forward = {source: 0.0}
    parent_forward = {source: None}
    visited_forward = set()
    heap_forward = MinHeap()
    heap_forward.push(0.0, source)

    # Backward search (from destination)
    distance_backward = {destination: 0.0}
    parent_backward = {destination: None}
    visited_backward = set()
    heap_backward = MinHeap()
    heap_backward.push(0.0, destination)

    # Track the best known full path
    best_distance = float("inf")
    meeting_node = None
    nodes_explored = 0

    def expand_one_step(heap, distance_mine, parent_mine, visited_mine,
                        distance_other, visited_other):
        nonlocal best_distance, meeting_node, nodes_explored

        current_distance, u = heap.pop()

        if u in visited_mine:
            return
        visited_mine.add(u)
        nodes_explored += 1

        # Check if this node was already finalised by the OTHER search
        if u in visited_other:
            candidate = distance_mine[u] + distance_other[u]
            if candidate < best_distance:
                best_distance = candidate
                meeting_node = u

        # Relax neighbors
        for v, edge_distance, _ in graph.get_neighbors(u, avoid_nodes, avoid_edges):
            if v in visited_mine:
                continue

            new_distance = current_distance + edge_distance

            if v not in distance_mine or new_distance < distance_mine[v]:
                distance_mine[v] = new_distance
                parent_mine[v] = u
                heap.push(new_distance, v)

                # Also check meeting condition here
                if v in distance_other:
                    candidate = new_distance + distance_other[v]
                    if candidate < best_distance:
                        best_distance = candidate
                        meeting_node = v

    while heap_forward and heap_backward:
        # Peek at the minimum key in each heap
        min_forward = heap_forward.data[0][0] if heap_forward else float("inf")
        min_backward = heap_backward.data[0][0] if heap_backward else float("inf")

        # Termination condition
        if min_forward + min_backward >= best_distance:
            break

        # Expand the side with smaller minimum (balances the two searches)
        if min_forward <= min_backward:
            expand_one_step(heap_forward, distance_forward, parent_forward,
                            visited_forward, distance_backward, visited_backward)
        else:
            expand_one_step(heap_backward, distance_backward, parent_backward,
                            visited_backward, distance_forward, visited_forward)

    # Handle no path found
    if meeting_node is None:
        return None

    # Reconstruct path
    path_forward = []
    node = meeting_node
    while node is not None:
        path_forward.append(node)
        node = parent_forward.get(node)
    path_forward.reverse()

    path_backward = []
    node = parent_backward.get(meeting_node)
    while node is not None:
        path_backward.append(node)
        node = parent_backward.get(node)

    path = path_forward + path_backward

    # Compute total travel time along this path
    total_distance = best_distance
    total_travel_time = 0.0
    cumulative_time = 0.0

    for i in range(len(path) - 1):
        u_node, v_node = path[i], path[i + 1]

        for neighbor_v, _, travel_times in graph.adjacent[u_node]:
            if neighbor_v == v_node:
                current_hour = (departure_hour + int(cumulative_time)) % 24
                edge_time = travel_times[current_hour]
                total_travel_time += edge_time
                cumulative_time += edge_time
                break

    return {
        "path": path,
        "total_distance": total_distance,
        "total_time": total_travel_time,
        "nodes_explored": nodes_explored
    }


if __name__ == "__main__":
    from graph import Graph

    graph = Graph()
    # rush hour times vs off-peak
    # slow at hours 7-9, 17-19
    graph.add_edge("A", "B", 4.0, [5] * 7 + [10] * 2 + [5] * 8 + [10] * 2 + [5] * 5)
    graph.add_edge("B", "C", 3.0, [4] * 7 + [8] * 2 + [4] * 8 + [8] * 2 + [4] * 5)
    graph.add_edge("A", "C", 10.0, [12] * 24)

    # test dijkstra_distance
    result = dijkstra_distance(graph, "A", "C")
    print(f"Path: {result['path']}, Distance: {result['total_distance']}, Explored: {result['nodes_explored']}")

    # test dijkstra_time
    result = dijkstra_time(graph, "A", "C", departure_hour=8)
    print(f"Path: {result['path']}, Travel Time: {result['total_time']}, Explored: {result['nodes_explored']}")

    # test bidirectional_dijkstra_distance
    result = bidirectional_dijkstra_distance(graph, "A", "C")
    print(f"Path: {result['path']}, Distance: {result['total_distance']}, Explored: {result['nodes_explored']}")
