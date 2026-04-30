"""
main.py — Entry point for the Smart Path Finder.

Menu-driven CLI application with guided prompts and context-specific help.
"""

import time
from datetime import datetime
from graph import Graph
from generator import generate_graph
from algorithms import dijkstra_distance, dijkstra_time, bidirectional_dijkstra_distance
from cache import (PathCache, run_query_cached, identify_hubs,
                   precompute_hub_paths)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def node_to_human(node_id, coord_map=None):
    """
    Convert a node ID to a human-readable string.
    Shows both the ID and its grid coordinates if available.
    """
    if coord_map and node_id in coord_map:
        r, c = coord_map[node_id]
        return f"Node {node_id} (Row {r}, Col {c})"
    # Fallback: try to parse old "r_c" format
    try:
        r, c = node_id.split('_')
        return f"Node {node_id} (Row {r}, Col {c})"
    except (ValueError, AttributeError):
        return f"Node {node_id}"


def is_help(user_input):
    """Check if user typed a help command."""
    return user_input.lower() in ('h', 'help')


def read_int(prompt, min_val=None, max_val=None, default=None):
    """Read an integer from the user with optional bounds and default."""
    while True:
        raw = input(prompt).strip()
        if is_help(raw):
            return 'help'
        if raw == '' and default is not None:
            return default
        try:
            val = int(raw)
            if min_val is not None and val < min_val:
                print(f"  Value must be at least {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"  Value must be at most {max_val}.")
                continue
            return val
        except ValueError:
            print("  Please enter a valid number.")


# ---------------------------------------------------------------------------
# Welcome Banner
# ---------------------------------------------------------------------------

def print_welcome():
    """Print the welcome banner with app introduction."""
    print("=" * 50)
    print("         SMART PATH FINDER")
    print("    A traffic-aware routing system")
    print("=" * 50)
    print()
    print("Welcome! This app finds the best route between")
    print("two locations on a city road network.")
    print()
    print("How the map works:")
    print("  - The city is represented as a grid of")
    print("    intersections (like city blocks).")
    print("  - Each intersection has a unique Node ID")
    print("    (e.g., 1, 2, ..., 4900) and a grid location")
    print("    shown as (Row, Col) — think of these as")
    print("    latitude and longitude coordinates.")
    print("  - Roads connecting intersections are 'edges',")
    print("    each with a distance and a travel time that")
    print("    changes by hour — just like real traffic.")
    print("  - Some roads are express 'highways' that link")
    print("    distant parts of the city for faster travel.")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Help Messages (context-specific)
# ---------------------------------------------------------------------------

def print_startup_help():
    print("\n" + "=" * 50)
    print("STARTUP HELP")
    print("=" * 50)
    print()
    print("[1] Generate New Map")
    print("    Creates a new city grid from scratch.")
    print("    You only need to enter the grid size")
    print("    (rows x columns). All roads are generated")
    print("    automatically: local roads, diagonal shortcuts,")
    print("    and highway express routes.")
    print("    Example: A 70x70 grid creates 4,900")
    print("    intersections, numbered 1 to 4,900.")
    print()
    print("[2] Load Map from File")
    print("    Opens a previously saved map (JSON file).")
    print("    Example: graph.json")
    print()
    print("[0] Exit — Close the application.")
    print()
    print("KEY CONCEPTS:")
    print("  Node    = An intersection, identified by a")
    print("            unique number (its Node ID).")
    print("  (Row, Col) = The grid coordinates of a node,")
    print("            like latitude/longitude on a real map.")
    print("  Edge    = A road connecting two intersections.")
    print("  Highway = A fast express road between distant nodes.")
    print("  Travel time changes by hour (like real traffic).")
    print("=" * 50 + "\n")


def print_main_help():
    print("\n" + "=" * 50)
    print("MAIN MENU HELP")
    print("=" * 50)
    print()
    print("[1] Find Route")
    print("    Finds the shortest-distance path and the")
    print("    shortest-time path between two intersections.")
    print("    Clean output matching the project spec.")
    print()
    print("[2] Find Route (Detailed)")
    print("    Runs all 3 algorithms (dijkstra_distance,")
    print("    dijkstra_time, bidirectional_dijkstra_distance)")
    print("    and shows performance metrics (nodes explored,")
    print("    query time, cache hit/miss).")
    print()
    print("[3] View Graph Stats")
    print("    Shows map summary: number of intersections,")
    print("    roads, cached routes, and key hubs.")
    print()
    print("[4] Search Edges from a Node")
    print("    Look up all roads connected to a specific")
    print("    intersection. Enter its Node ID to explore.")
    print()
    print("[5] Save Graph")
    print("    Exports the current map to a JSON file.")
    print("    You can reload it later with 'Load Map'.")
    print()
    print("[H] Help — Shows this guide (available everywhere).")
    print("[0] Exit — Close the application.")
    print()
    print("NODES: Each intersection has a unique Node ID")
    print("  (a number). Use [3] Search Edges to explore")
    print("  which nodes connect to a given intersection.")
    print("=" * 50 + "\n")


def print_find_route_help():
    print("\n" + "-" * 50)
    print("FIND ROUTE HELP")
    print("-" * 50)
    print()
    print("This guides you to find the best route between")
    print("two intersections on the map.")
    print()
    print("You will enter:")
    print("  Source node      — Node ID where you start")
    print("  Destination node — Node ID where you want to go")
    print("  Avoid nodes      — Node IDs to skip (optional)")
    print("                     e.g., 500,612")
    print("  Avoid edges      — Roads to skip (optional)")
    print("                     e.g., 500-501,612-613")
    print("  Departure hour   — Hour of day 0-23 (affects traffic)")
    print("                     8 = 8:00 AM, 17 = 5:00 PM")
    print()
    print("The system runs 3 algorithms:")
    print("  1. Dijkstra (Shortest Distance)")
    print("  2. Dijkstra (Shortest Time — traffic-aware)")
    print("  3. Bidirectional Dijkstra (Shortest Distance,")
    print("     searches from both ends for efficiency)")
    print()
    print("Then it recommends the best route by distance")
    print("and the best route by travel time.")
    print("-" * 50 + "\n")


def print_search_edges_help():
    print("\n" + "-" * 50)
    print("SEARCH EDGES HELP")
    print("-" * 50)
    print()
    print("Enter any Node ID to see all roads connected")
    print("to that intersection.")
    print()
    print("For each road, you will see:")
    print("  - The neighboring node (ID and coordinates)")
    print("  - The road distance (km)")
    print("  - The travel time at a specific hour")
    print("  - Whether it is a highway (long-distance road)")
    print()
    print("You can also specify a departure hour (0-23)")
    print("to see how travel times vary with traffic.")
    print("-" * 50 + "\n")


# ---------------------------------------------------------------------------
# Startup Menu
# ---------------------------------------------------------------------------

def prompt_generate():
    """Guide the user through generating a new map. Returns a Graph or None."""
    print("\n--- Generate New Map ---")
    print("A grid-based city map where each cell is an intersection.")
    print("You only need to specify the grid size — all roads")
    print("(local, diagonal, highways) are generated automatically.")
    print("Type 'h' for help at any prompt.\n")

    rows = read_int("Enter number of rows (e.g., 70): ", min_val=2)
    if rows == 'help':
        print_startup_help()
        return None

    cols = read_int("Enter number of columns (e.g., 70): ", min_val=2)
    if cols == 'help':
        print_startup_help()
        return None

    total_nodes = rows * cols
    # Auto-calculate highway count: ~18% of total nodes (same ratio as original 900/4900)
    highway_edges = int(total_nodes * 0.18)

    print(f"\nGenerating {rows}x{cols} city map ({total_nodes} intersections)...")

    graph = generate_graph(
        rows=rows, cols=cols,
        diag_prob=0.20,
        highway_edges=highway_edges,
        seed=42, id_mode="seq",
        verbose=True
    )

    print()
    print("  Use [3] Search Edges to explore any node's connections.")
    print("\nMap created successfully!\n")
    return graph


def prompt_load():
    """Guide the user through loading a map file. Returns a Graph or None."""
    print("\n--- Load Map from File ---")
    filename = input("Enter filename (e.g., graph.json): ").strip()
    if is_help(filename):
        print_startup_help()
        return None
    if not filename:
        print("  No filename entered.")
        return None
    try:
        graph = Graph.load(filename)
        print(f"  Loaded map: {graph.node_count()} nodes, {graph.edge_count()} edges.")
        if graph.coord_map:
            print("  Coordinate map loaded (nodes have grid positions).")
        print()
        return graph
    except FileNotFoundError:
        print(f"  Error: File '{filename}' not found.")
        return None
    except Exception as e:
        print(f"  Error loading file: {e}")
        return None


def startup_menu():
    """Display the startup menu and return a loaded Graph."""
    graph = None
    while graph is None:
        print("\n[1] Generate New Map")
        print("[2] Load Map from File")
        print("[H] Help")
        print("[0] Exit")

        choice = input("\nstartup > ").strip().lower()

        if choice == '1':
            graph = prompt_generate()
        elif choice == '2':
            graph = prompt_load()
        elif is_help(choice):
            print_startup_help()
        elif choice == '0':
            return None
        else:
            print("  Invalid choice. Type 'h' for help.")

    return graph


# ---------------------------------------------------------------------------
# System Initialization
# ---------------------------------------------------------------------------

def initialize_system(graph):
    """
    Identify hubs and precompute paths. Returns (cache, hubs).
    Shows non-tech-friendly progress messages.
    """
    coord_map = graph.coord_map

    print("\n" + "=" * 50)
    print("SETTING UP THE ROUTING SYSTEM")
    print("=" * 50)

    # Step 1: Hub identification
    print("\nStep 1/2: Finding the busiest intersections...")
    print("  (These are 'hubs' — major crossroads where")
    print("   many roads meet, like key city intersections.)")
    hubs = identify_hubs(graph, top_n=30)
    print(f"  Found {len(hubs)} major hubs.")
    hub_examples = ', '.join(node_to_human(h, coord_map) for h in hubs[:3])
    print(f"  Examples: {hub_examples}, ...")

    # Step 2: Precompute hub paths
    print("\nStep 2/2: Pre-calculating common routes between hubs...")
    print("  (This caches popular routes so future lookups")
    print("   are near-instant — like a GPS pre-loading maps.)")

    cache = PathCache()
    count = precompute_hub_paths(graph, cache, hubs, departure_hours=[0, 8, 12, 18],
                                 verbose=False)
    print(f"  Cached {count} routes across 4 time periods")
    print("  (midnight, 8:00 AM, noon, 6:00 PM).")

    print("\n" + "=" * 50)
    print("System is ready! Type 'h' for help at any time.")
    print("=" * 50)

    return cache, hubs


# ---------------------------------------------------------------------------
# Main Menu Features
# ---------------------------------------------------------------------------

def collect_query_inputs(graph):
    """Shared guided input collection for route queries. Returns dict or None."""
    print("Enter nodes by their Node ID.")
    print("Type 'h' for help.\n")

    # --- Source ---
    source = input("Enter source Node ID: ").strip()
    if is_help(source):
        print_find_route_help()
        return None
    if source not in graph.nodes:
        print(f"  Node '{source}' does not exist on the map.")
        return None

    # --- Destination ---
    destination = input("Enter destination Node ID: ").strip()
    if is_help(destination):
        print_find_route_help()
        return None
    if destination not in graph.nodes:
        print(f"  Node '{destination}' does not exist on the map.")
        return None

    if source == destination:
        print("  Source and destination are the same node.")
        return None

    # --- Avoid nodes ---
    avoid_input = input("Avoid any nodes? (comma-separated IDs, or Enter to skip): ").strip()
    if is_help(avoid_input):
        print_find_route_help()
        return None
    avoid_nodes = set()
    if avoid_input:
        avoid_nodes = set(n.strip() for n in avoid_input.split(',') if n.strip())

    # --- Avoid edges ---
    avoid_edge_input = input("Avoid any edges? (e.g., 500-501, or Enter to skip): ").strip()
    if is_help(avoid_edge_input):
        print_find_route_help()
        return None
    avoid_edges = set()
    if avoid_edge_input:
        for edge_str in avoid_edge_input.split(','):
            edge_str = edge_str.strip()
            if '-' in edge_str:
                u, v = edge_str.split('-', 1)
                avoid_edges.add((u.strip(), v.strip()))

    # --- Departure hour ---
    current_hour = datetime.now().hour
    departure = read_int(f"Departure hour (0-23, default {current_hour} — current time): ",
                         min_val=0, max_val=23, default=current_hour)
    if departure == 'help':
        print_find_route_help()
        return None

    return {
        "source": source,
        "destination": destination,
        "avoid_nodes": avoid_nodes,
        "avoid_edges": avoid_edges,
        "departure": departure,
    }


def handle_find_route(graph, cache):
    """Spec-compliant output: 2 paths (min distance, min time), clean format."""
    coord_map = graph.coord_map

    print("\n" + "=" * 50)
    print("FIND ROUTE")
    print("=" * 50)

    query = collect_query_inputs(graph)
    if query is None:
        return

    source = query["source"]
    destination = query["destination"]
    avoid_nodes = query["avoid_nodes"]
    avoid_edges = query["avoid_edges"]
    departure = query["departure"]

    src_label = node_to_human(source, coord_map)
    dst_label = node_to_human(destination, coord_map)
    print(f"\nSearching: {src_label} -> {dst_label}", end="")
    if departure != 0:
        print(f" (departure: {departure}:00)", end="")
    print("\n")

    # Path 1: Shortest distance
    res_dist, _ = run_query_cached(
        graph, cache, source, destination,
        departure, "distance", avoid_nodes, avoid_edges
    )

    print("--- Path 1: Shortest Distance (dijkstra_distance) ---")
    if res_dist is None:
        print("  No path found.")
    else:
        path_display = " -> ".join(res_dist["path"])
        print(f"  Path ({len(res_dist['path'])} nodes): {path_display}")
        print(f"  Total distance:  {res_dist['total_distance']:.2f} km")
        print(f"  Total time:      {res_dist['total_time']:.2f} hours")
    print()

    # Path 2: Shortest time
    res_time, _ = run_query_cached(
        graph, cache, source, destination,
        departure, "time", avoid_nodes, avoid_edges
    )

    print("--- Path 2: Shortest Time (dijkstra_time) ---")
    if res_time is None:
        print("  No path found.")
    else:
        path_display = " -> ".join(res_time["path"])
        print(f"  Path ({len(res_time['path'])} nodes): {path_display}")
        print(f"  Total distance:  {res_time['total_distance']:.2f} km")
        print(f"  Total time:      {res_time['total_time']:.2f} hours")

    print("=" * 50 + "\n")


def handle_find_route_detailed(graph, cache):
    """Detailed output: all 3 algorithms with performance metrics."""
    coord_map = graph.coord_map

    print("\n" + "=" * 50)
    print("FIND ROUTE (DETAILED)")
    print("=" * 50)

    query = collect_query_inputs(graph)
    if query is None:
        return

    source = query["source"]
    destination = query["destination"]
    avoid_nodes = query["avoid_nodes"]
    avoid_edges = query["avoid_edges"]
    departure = query["departure"]

    src_label = node_to_human(source, coord_map)
    dst_label = node_to_human(destination, coord_map)
    print(f"\nSearching: {src_label} -> {dst_label}", end="")
    if departure != 0:
        print(f" (departure: {departure}:00)", end="")
    print("\n")

    algorithms = [
        ("dijkstra_distance", "distance"),
        ("dijkstra_time", "time"),
        ("bidirectional_dijkstra_distance", "bidirectional"),
    ]

    results = []

    for name, mode in algorithms:
        start_t = time.perf_counter()

        if mode == "distance":
            result, hit = run_query_cached(
                graph, cache, source, destination,
                departure, "distance", avoid_nodes, avoid_edges
            )
        elif mode == "time":
            result, hit = run_query_cached(
                graph, cache, source, destination,
                departure, "time", avoid_nodes, avoid_edges
            )
        elif mode == "bidirectional":
            result = bidirectional_dijkstra_distance(
                graph, source, destination,
                avoid_nodes, avoid_edges, departure
            )
            hit = False

        elapsed = (time.perf_counter() - start_t) * 1000
        results.append((name, mode, result, elapsed, hit))

    # --- Display results ---
    for name, mode, result, elapsed, hit in results:
        print(f"--- {name} ---")
        if result is None:
            print("  No path found.")
        else:
            path = result["path"]
            print(f"  Total distance:  {result['total_distance']:.2f} km")
            print(f"  Total time:      {result['total_time']:.2f} hours")
            print(f"  Nodes explored:  {result['nodes_explored']}")

            path_display = " -> ".join(path)
            print(f"  Path ({len(path)} nodes): {path_display}")

        cache_label = "HIT" if hit else "MISS"
        print(f"  [Query time: {elapsed:.2f} ms | Cache: {cache_label}]")
        print()

    # --- Best routes summary ---
    distance_results = [(name, r) for name, mode, r, _, _ in results
                        if r is not None and mode in ("distance", "bidirectional")]
    time_results = [(name, r) for name, mode, r, _, _ in results
                    if r is not None and mode == "time"]

    print("=" * 50)
    print("BEST ROUTES")
    print("=" * 50)

    if distance_results:
        best_dist = min(distance_results, key=lambda x: x[1]["total_distance"])
        print(f"  Best by DISTANCE: {best_dist[0]}")
        print(f"    -> {best_dist[1]['total_distance']:.2f} km, "
              f"{best_dist[1]['total_time']:.2f} hours")
    else:
        print("  Best by DISTANCE: No path found")

    if time_results:
        best_time = min(time_results, key=lambda x: x[1]["total_time"])
        print(f"  Best by TIME:     {best_time[0]}")
        print(f"    -> {best_time[1]['total_distance']:.2f} km, "
              f"{best_time[1]['total_time']:.2f} hours")
    else:
        print("  Best by TIME:     No path found")

    print("=" * 50 + "\n")


def handle_view_stats(graph, cache, hubs):
    """Display graph statistics."""
    print("\n--- Graph Statistics ---")
    print(f"  Nodes (intersections): {graph.node_count()}")
    print(f"  Edges (roads):         {graph.edge_count()}")
    print(f"  Cached routes:         {cache.size()}")
    print(f"  Active hubs:           {len(hubs)}")
    print()


def handle_search_edges(graph):
    """Search and display all edges from a given node."""
    coord_map = graph.coord_map

    print("\n--- Search Edges from a Node ---")
    print("Type 'h' for help.\n")

    node_id = input("Enter Node ID: ").strip()
    if is_help(node_id):
        print_search_edges_help()
        return

    if node_id not in graph.nodes:
        print(f"  Node '{node_id}' does not exist on the map.")
        return

    current_hour = datetime.now().hour
    departure = read_int(f"Departure hour for travel times (0-23, default {current_hour} — current time): ",
                         min_val=0, max_val=23, default=current_hour)
    if departure == 'help':
        print_search_edges_help()
        return

    neighbors = graph.adjacent.get(node_id, [])
    if not neighbors:
        print(f"  {node_to_human(node_id, coord_map)} has no connections.")
        return

    print(f"\n--- Edges from {node_to_human(node_id, coord_map)} (at {departure}:00) ---")

    for i, (neighbor, distance, travel_times) in enumerate(neighbors, 1):
        travel_time = travel_times[departure]
        label = "  [Highway]" if distance > 5.0 else ""
        neighbor_label = node_to_human(neighbor, coord_map)
        print(f"  [{i}] -> {neighbor_label:35s} | "
              f"Dist: {distance:7.2f} km | "
              f"Time: {travel_time:.4f} hrs{label}")

    print(f"\n  Total connections: {len(neighbors)}")

    # Option to view full 24-hour travel times for a specific edge
    while True:
        detail = input("\nView full 24-hour travel times for an edge? "
                       "(enter edge number, or Enter to go back): ").strip()
        if not detail:
            break
        if is_help(detail):
            print_search_edges_help()
            continue
        try:
            idx = int(detail)
            if idx < 1 or idx > len(neighbors):
                print(f"  Please enter a number between 1 and {len(neighbors)}.")
                continue
            neighbor, distance, travel_times = neighbors[idx - 1]
            neighbor_label = node_to_human(neighbor, coord_map)
            label = " [Highway]" if distance > 5.0 else ""
            print(f"\n  Edge: {node_to_human(node_id, coord_map)} <-> {neighbor_label}"
                  f"  ({distance:.2f} km{label})")
            print(f"  {'Hour':>6}  {'Travel Time (hrs)':>18}")
            print(f"  {'-'*28}")
            for hour in range(24):
                marker = " <-- current" if hour == departure else ""
                print(f"  {hour:>5}:00  {travel_times[hour]:>18.4f}{marker}")
        except ValueError:
            print("  Please enter a valid number.")
    print()


def handle_save(graph):
    """Save the graph to a file."""
    print("\n--- Save Graph ---")
    filename = input("Enter filename (e.g., my_map.json): ").strip()
    if is_help(filename):
        print("  Usage: Enter a filename to save the current map.")
        print("  The file will be saved in JSON format.")
        print("  You can reload it later using 'Load Map' at startup.\n")
        return
    if not filename:
        print("  No filename entered.")
        return
    try:
        graph.save(filename)
        print(f"  Graph saved to '{filename}'.\n")
    except Exception as e:
        print(f"  Error saving: {e}\n")


# ---------------------------------------------------------------------------
# Main Menu Loop
# ---------------------------------------------------------------------------

def main_menu_loop(graph, cache, hubs):
    """Run the main menu loop."""
    while True:
        print("\n============ MAIN MENU =============")
        print("[1] Find Route")
        print("[2] Find Route (Detailed)")
        print("[3] View Graph Stats")
        print("[4] Search Edges from a Node")
        print("[5] Save Graph")
        print("[H] Help")
        print("[0] Exit")
        print("====================================")

        choice = input("\nmenu > ").strip().lower()

        try:
            if choice == '1':
                handle_find_route(graph, cache)
            elif choice == '2':
                handle_find_route_detailed(graph, cache)
            elif choice == '3':
                handle_view_stats(graph, cache, hubs)
            elif choice == '4':
                handle_search_edges(graph)
            elif choice == '5':
                handle_save(graph)
            elif is_help(choice):
                print_main_help()
            elif choice == '0':
                print("\nExiting Smart Path Finder. Drive safe!")
                break
            else:
                print("  Invalid choice. Type 'h' for help.")
        except KeyboardInterrupt:
            print("\n\nExiting Smart Path Finder. Goodbye!")
            break
        except Exception as e:
            print(f"\n  Error: {e}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    print_welcome()

    try:
        graph = startup_menu()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        return

    if graph is None:
        print("\nGoodbye!")
        return

    try:
        cache, hubs = initialize_system(graph)
    except KeyboardInterrupt:
        print("\n\nSetup interrupted. Goodbye!")
        return

    main_menu_loop(graph, cache, hubs)


if __name__ == "__main__":
    main()
