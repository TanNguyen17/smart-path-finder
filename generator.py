"""
generator.py — Synthetic graph generator for the Smart Path Finder.

Generates a realistic road network by combining:
    1. A regular grid of local roads (4-connected)
    2. Random diagonal shortcuts (~20 % of cells)
    3. Long-range highway edges between distant nodes

Each edge receives a 24-hour travel-time profile based on a realistic
traffic pattern (morning/evening peaks) plus random noise.
"""

import random
from graph import Graph


def node_id_from_cell(r, c, cols, id_mode="str"):
    """Convert a grid cell (row, col) to a node identifier."""
    if id_mode == "int":
        return r * cols + c
    if id_mode == "seq":
        return str(r * cols + c + 1)   # 1-based sequential string ID
    return f"{r}_{c}"


def undirect_key(u, v):
    """Return a canonical (smaller, larger) pair for deduplication."""
    return (u, v) if u <= v else (v, u)


def default_traffic_profile():
    """
    Return a 24-element multiplier list modelling daily traffic.

    Peak hours (7-9 AM, 5-7 PM) have multipliers > 1.4,
    off-peak night hours (0-5 AM) have multipliers < 0.85.
    """
    return [
        0.80, 0.80, 0.80, 0.80, 0.80, 0.85,       # 0-5   (night)
        1.10, 1.50, 1.60, 1.40,                     # 6-9   (morning peak)
        1.10, 1.00, 1.00, 1.00, 1.00, 1.00, 1.05,  # 10-16 (midday)
        1.40, 1.60, 1.50,                           # 17-19 (evening peak)
        1.10, 1.00, 0.90, 0.85                      # 20-23 (night)
    ]


def build_travel_times(distance, speed_units_per_hour, profile,
                       noise_min, noise_max):
    """
    Build a 24-value travel-time array for one edge.

    travel_time[h] = (distance / speed) * traffic_profile[h] * noise
    """
    base_time = distance / speed_units_per_hour
    result = []

    for h in range(24):
        noise = random.uniform(noise_min, noise_max)
        t = base_time * profile[h] * noise
        result.append(max(0.001, float(t)))

    return result


def generate_graph(
    rows=70,
    cols=70,
    diag_prob=0.20,
    highway_edges=900,
    local_speed=40.0,
    highway_speed=80.0,
    min_highway_grid_dist=12,
    seed=42,
    id_mode="str",
    verbose=False
):
    """
    Generate a synthetic road-network graph.

    Parameters
    ----------
    rows, cols             : grid dimensions (nodes = rows * cols)
    diag_prob              : probability of a diagonal shortcut per cell
    highway_edges          : number of long-range highway edges to add
    local_speed            : speed on local roads (distance units / hour)
    highway_speed          : speed on highways
    min_highway_grid_dist  : minimum Manhattan distance for highways
    seed                   : random seed for reproducibility
    id_mode                : "str" for "r_c" labels, "int" for integer IDs,
                             "seq" for sequential 1-based string IDs
    verbose                : if True, print each node/edge as it is created

    Returns
    -------
    Graph instance
    """
    random.seed(seed)
    graph = Graph()
    profile = default_traffic_profile()

    cell_to_id = {}
    existing_edges = set()  # prevent duplicate undirected edges

    # 1. Create nodes — sequential counter, independent of row/col
    if verbose:
        print(f"\n  Phase 1/4: Creating {rows * cols} nodes (intersections)...")
    node_counter = 0
    for r in range(rows):
        for c in range(cols):
            if id_mode == "seq":
                node_counter += 1
                node_id = str(node_counter)
            else:
                node_id = node_id_from_cell(r, c, cols, id_mode)
            graph._add_node(node_id)
            cell_to_id[(r, c)] = node_id
            if verbose:
                print(f"    Node {node_id:>6} created at (Row {r}, Col {c})")
    if verbose:
        print(f"  -> {graph.node_count()} nodes created.")

    edge_counter = 0

    def add_road_by_cells(r1, c1, r2, c2, speed, noise_min, noise_max,
                          road_kind):
        nonlocal edge_counter
        u = cell_to_id[(r1, c1)]
        v = cell_to_id[(r2, c2)]
        key = undirect_key(u, v)
        if key in existing_edges:
            return
        existing_edges.add(key)

        dr = abs(r1 - r2)
        dc = abs(c1 - c2)

        # Distance model
        if road_kind == "local_straight":
            distance = 1.0          # horizontal/vertical neighbour
        elif road_kind == "local_diagonal":
            distance = 1.414        # approx sqrt(2)
        elif road_kind == "highway":
            distance = (dr**2 + dc**2)**0.5   # Euclidean distance
            if distance < 1.0:
                distance = 1.0
        else:
            raise ValueError(f"Unknown road kind: {road_kind}")

        travel_times = build_travel_times(distance, speed, profile,
                                          noise_min, noise_max)
        graph.add_edge(u, v, distance, travel_times)
        edge_counter += 1

        if verbose:
            kind_label = {"local_straight": "local road",
                          "local_diagonal": "diagonal shortcut",
                          "highway": "highway"}
            label = kind_label.get(road_kind, road_kind)
            print(f"    Edge {edge_counter:>6}: Node {u} <-> Node {v}  "
                  f"({label}, {distance:.2f} km)")

        return True

    # 2. Add 4-connected local roads (right + down only to avoid duplicates)
    if verbose:
        print(f"\n  Phase 2/4: Adding local roads...")
    local_before = edge_counter
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                add_road_by_cells(r, c, r, c + 1, local_speed,
                                  0.8, 1.2, "local_straight")
            if r + 1 < rows:
                add_road_by_cells(r, c, r + 1, c, local_speed,
                                  0.8, 1.2, "local_straight")
    local_count = edge_counter - local_before
    if verbose:
        print(f"  -> {local_count} local roads created.")

    # 3. Add diagonal shortcuts (~20 %)
    if verbose:
        print(f"\n  Phase 3/4: Adding diagonal shortcuts (~{int(diag_prob*100)}% chance per cell)...")
    diag_before = edge_counter
    for r in range(rows):
        for c in range(cols):
            if random.random() > diag_prob:
                continue

            candidates = []
            if c + 1 < cols and r + 1 < rows:
                candidates.append((r + 1, c + 1))
            if c - 1 >= 0 and r + 1 < rows:
                candidates.append((r + 1, c - 1))

            if candidates:
                rr, cc = random.choice(candidates)
                add_road_by_cells(r, c, rr, cc, local_speed,
                                  0.8, 1.2, "local_diagonal")
    diag_count = edge_counter - diag_before
    if verbose:
        print(f"  -> {diag_count} diagonal shortcuts created.")

    # 4. Add highway edges
    if verbose:
        print(f"\n  Phase 4/4: Adding highway express routes...")
    all_cells = list(cell_to_id.keys())
    highway_before = edge_counter
    added = 0
    attempts = 0
    max_attempts = highway_edges * 25

    while added < highway_edges and attempts < max_attempts:
        attempts += 1
        (r1, c1) = random.choice(all_cells)
        (r2, c2) = random.choice(all_cells)

        if (r1, c1) == (r2, c2):
            continue

        # Enforce long-range
        manhattan = abs(r1 - r2) + abs(c1 - c2)
        if manhattan < min_highway_grid_dist:
            continue

        ok = add_road_by_cells(r1, c1, r2, c2, highway_speed,
                               0.90, 1.05, "highway")
        if ok:
            added += 1
    highway_count = edge_counter - highway_before
    if verbose:
        print(f"  -> {highway_count} highways created.")

    # Build coordinate map: node_id -> (row, col)
    graph.coord_map = {}
    for (r, c), node_id in cell_to_id.items():
        graph.coord_map[str(node_id)] = (r, c)

    if verbose:
        print(f"\n  === Generation Summary ===")
        print(f"    Total nodes: {graph.node_count()}")
        print(f"    Total edges: {graph.edge_count()}")
        print(f"      - Local roads:       {local_count}")
        print(f"      - Diagonal shortcuts: {diag_count}")
        print(f"      - Highways:           {highway_count}")

    return graph


if __name__ == "__main__":
    graph = generate_graph(
        rows=70,
        cols=70,
        diag_prob=0.20,
        highway_edges=900,
        seed=42,
        id_mode="str"
    )

    print(f"Nodes: {graph.node_count()}")
    print(f"Edges: {graph.edge_count()}")
    graph.save("graph.json")
    print("Graph saved to graph.json")