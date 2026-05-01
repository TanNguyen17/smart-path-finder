"""
main.py — Entry point for the Smart Path Finder.
"""

import time
from graph import Graph
from generator import generate_graph
from cache import (PathCache, run_query_cached, identify_hubs,
                   precompute_hub_paths, simulate_weekly_update)
from query import parse_query, format_result

def node_to_human(node_id):
    """
    Converts machine IDs like '23_24' to 'Row 23, Col 24'.
    Provides better spatial context for the user.
    """
    try:
        r, c = node_id.split('_')
        return f"Row {r}, Col {c}"
    except (ValueError, AttributeError):
        return node_id

HELP_MENUS = {
    "startup": """
==============================
STARTUP HELP
==============================
1. Generate New Graph: Creates a synthetic grid map.
   You will be asked for the number of rows and columns.
   Includes diagonal paths and high-speed 'highways'.
2. Load from File: Enter the path to a saved .graph file.
quit: Exit the program.
==============================
""",
    "main": """
==================================================
COMMAND REFERENCE
==================================================
query <src> <dest> [options]
    Finds paths between nodes (e.g., query 5_5 10_10).
    Optional parameters:
      avoid_nodes n1,n2   - Skip specific nodes.
      avoid_edges n1-n2   - Skip specific road segments.
      departure <hour>    - Set time (0-23) for traffic.

map_info
    Show node naming rules and map size.

examples
    Show copy-ready example queries.

sample_nodes
    Show sample node IDs for this map.
    
check_node <node>
    Check whether a node exists and list its neighbors.

stats
    Displays nodes, edges, and cache performance.

save <filename>
    Exports the current graph data.

update
    Simulates a new week of traffic data and resets cache.

help
    Shows this command list.

quit / exit
    Close the program.
==================================================
COORDINATE TIP: Nodes are named 'Row_Col' (e.g., 0_0 is top-left).
==================================================
"""
}

def print_help(menu_type):
    print(HELP_MENUS.get(menu_type, ""))

def infer_grid_size(graph):
    """
    Attempt to determine the grid dimensions (rows/cols) from node IDs.
    Caches the result on the graph object to avoid repeated O(V) scans.
    """
    # Check if already cached on graph
    rows = getattr(graph, "_inferred_rows", None)
    cols = getattr(graph, "_inferred_cols", None)

    if rows is not None and cols is not None:
        return rows, cols

    # Fallback to checking graph attributes if they exist
    rows = getattr(graph, "rows", None)
    cols = getattr(graph, "cols", None)
    if rows and cols:
        graph._inferred_rows = rows
        graph._inferred_cols = cols
        return rows, cols 
    
    max_row = -1
    max_col = -1
    for node in graph.nodes:
        if "_" not in node:
            continue 
        left, right = node.split("_", 1)
        if left.isdigit() and right.isdigit():
            max_row = max(max_row, int(left))
            max_col = max(max_col, int(right))
    
    if max_row >= 0 and max_col >= 0:
        graph._inferred_rows = max_row + 1
        graph._inferred_cols = max_col + 1
        return graph._inferred_rows, graph._inferred_cols
    return None, None

def print_map_info(graph, week_id):
    """Display comprehensive information about the current graph state."""
    rows, cols = infer_grid_size(graph)
    print("Map information:")
    print(f"  - Nodes: {graph.node_count()}")
    print(f"  - Roads: {graph.edge_count()}")
    print(f"  - Traffic data version: week_{getattr(graph, 'data_version', 1)}")
    print(f"  - Node naming format: row_Col")
    if rows and cols:
        print(f"  Grid size: {rows} rows x {cols} columns")
        print(f"  Valid row range: 0-{rows - 1}")
        print(f"  Valid column range: 0-{cols - 1}")
        print("  Examples:")
        print(f"   0_0 = top-left")
        print(f"   0_{cols - 1} = top-right")
        print(f"   {rows-1}_0 = bottom-left")
        print(f"   {rows-1}_{cols-1} = bottom-right")
        print(f"   {rows // 2}_{cols // 2} = center")

def print_examples(graph):
    """Show copy-ready example queries tailored to the current map size."""
    rows, cols = infer_grid_size(graph)
    if not rows or not cols:
        print("Example: query A B departure 8")
        return  
    
    print("Example queries:")
    print(f"  query 0_0 {rows - 1}_{cols - 1} departure 8")
    print(f"  query {rows // 4}_{cols // 4} {rows - 5}_{cols - 10} departure 17")
    print(f"  query {rows//2}_{cols//2} 0_0 avoid_nodes {rows//4}_{cols//4}")
    print(f"  query 0_0 {rows - 1}_{cols - 1} avoid_nodes {rows // 2}_{cols // 2} departure 8")
    print(f"  query 0_0 {rows - 1}_{cols - 1} avoid_edges 0_0-0_1 departure 8")

def print_sample_nodes(graph):
    """Print a set of valid node IDs to help the user get started."""
    rows, cols = infer_grid_size(graph)
    if not rows or not cols: 
        print("Sample nodes:", ", ".join(sorted(list(graph.nodes))[:10]))
        return 
    
    samples = [
        "0_0",
        f"{rows // 4}_{cols // 4}",
        f"{rows // 2}_{cols // 2}",
        f"{rows - 5}_{cols - 10}",
        f"{rows - 1}_{cols - 1}"
    ]
    print("Sample nodes:")
    for node in samples: 
        exists = "exists" if node in graph.nodes else "missing"
        print(f" {node} ({exists})")

def check_node(graph, node):
    """Verify if a node exists and display its immediate connections."""
    node = str(node)
    if node not in graph.nodes:
        print(f"Node '{node}' does not exist.")
        rows, cols = infer_grid_size(graph)
        if rows and cols:
            print(f"Use row_col format. Valid ranges: row 0-{rows - 1}, column 0-{cols - 1}.")
        return
    
    neighbors = graph.get_neighbors(node)
    print(f"Node {node} exists.")
    print(f"Connected roads: {len(neighbors)}")
    print("Neighbors:", ", ".join(neighbor for neighbor, _, _ in neighbors[:12]))
    if len(neighbors) > 12:
        print(f"... and {len(neighbors) - 12} more")

def handle_query(user_input, graph, cache):
    """Parse and execute a query, showing both distance and time results."""
    query = parse_query(user_input)

    if query is None:
        print("\n[!] Invalid query format.")
        print("Example: query 0_0 69_69 avoid_nodes 30_30,35_35 departure 8")
        print("Type 'help' for a full breakdown of parameters.")
        return

    # Visual confirmation of the human-readable location
    print(f"\n--- Route: {node_to_human(query.source)} → {node_to_human(query.destination)} ---")
    if query.departure_hour is not None:
        print(f"Departure Time: {query.departure_hour}:00")

    # Run and display Distance query comparison
    # 1. Standard Dijkstra calculation
    start_std = time.perf_counter()
    res_std, hit_std = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "distance_std", query.avoid_nodes, query.avoid_edges
    )
    time_std = (time.perf_counter() - start_std) * 1000

    # 2. Bidirectional Dijkstra calculation
    start_bidir = time.perf_counter()
    res_bidir, hit_bidir = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "distance", query.avoid_nodes, query.avoid_edges
    )
    time_bidir = (time.perf_counter() - start_bidir) * 1000
    
    # Result Display
    # A. Standard Dijkstra Output
    print(format_result("distance", res_std, label="Shortest distance path (Standard Dijkstra)"))
    print(f"└─ [Time: {time_std:.2f}ms | Cache: {'HIT' if hit_std else 'MISS'}]")

    # B. Bidirectional Dijkstra Output
    print(f"\n{format_result('distance', res_bidir, label='Shortest distance path (Bidirectional Dijkstra)')}")
    print(f"└─ [Time: {time_bidir:.2f}ms | Cache: {'HIT' if hit_bidir else 'MISS'}]")

    # Run and display Time query
    start_time = time.perf_counter()
    res_time, hit_time = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "time", query.avoid_nodes, query.avoid_edges
    )
    time_time = (time.perf_counter() - start_time) * 1000
    
    print(f"\n{format_result('time', res_time)}")
    print(f"└─ [Time: {time_time:.2f}ms | Cache: {'HIT' if hit_time else 'MISS'}]\n")

def main():
    print("=== Smart Path Finder CLI ===")
    print("An advanced routing engine with traffic-aware caching.")
    
    # A. Initial State: Load or Generate
    graph = None
    while not graph:
        print("\n[1] Generate New Graph\n[2] Load Graph from File\nType 'help' for info or 'quit' to exit.")

        choice = input("startup > ").strip().lower()

        if choice == 'help':
            print_help("startup")
        elif choice == '1':
            # Prompt for grid size
            try:
                rows_input = input("Enter number of rows (default 70): ").strip()
                cols_input = input("Enter number of columns (default 70): ").strip()
                rows = int(rows_input) if rows_input else 70
                cols = int(cols_input) if cols_input else 70
                if rows < 2 or cols < 2:
                    print("Error: Rows and columns must be at least 2.")
                    continue
            except ValueError:
                print("Error: Please enter valid integers.")
                continue

            # Scale highway edges proportionally to grid area
            highway_edges = max(10, int(900 * (rows * cols) / (70 * 70)))
            print(f"\nGenerating graph ({rows}x{cols} grid + {highway_edges} highways)...")
            graph = generate_graph(rows=rows, cols=cols, diag_prob=0.20, highway_edges=highway_edges, seed=42, id_mode="str")
            print(f"Ready: {graph.node_count()} nodes, {graph.edge_count()} edges.")
        elif choice == '2':
            filename = input("Enter filename: ").strip()
            try:
                graph = Graph.load(filename)
                print(f"Success: Loaded {graph.node_count()} nodes.")
            except Exception as e:
                print(f"Error: {e}. (Type 'help' for startup tips)")
        elif choice in ['quit', 'exit']:
            print("Goodbye!")
            return
        else:
            print("Unknown selection. Type 'help' if you're stuck.")

    # B. System Initialization
    cache = PathCache()
    print("\nIdentifying transit hubs...")
    # Scale hubs based on map size: roughly 30 hubs per 4900 nodes, capped between 10 and 50
    node_count = graph.node_count()
    num_hubs = max(10, min(50, int(30 * node_count / 4900)))
    hubs = identify_hubs(graph, top_n=num_hubs)
    print(f"Hubs active: {len(hubs)} (proportional to map size)")

    print("Precomputing traffic patterns for hubs...")
    count = precompute_hub_paths(graph, cache, hubs, departure_hours=[0, 8, 12, 18])
    print(f"Cache primed with {count} entries.")
    print("\nSystem online. Type 'help' to see available commands.")

    # C. Main Loop
    while True:
        try:
            user_input = input("smart_path > ").strip()
            if not user_input:
                continue

            parts = user_input.split()
            command = parts[0].lower()

            if command in ["quit", "exit"]:
                print("Exiting Smart Path Finder. Drive safe!")
                break
            elif command == "help":
                print_help("main")
            elif command == "map_info":
                print_map_info(graph, None)
            elif command == "examples":
                print_examples(graph)
            elif command == "sample_nodes":
                print_sample_nodes(graph)
            elif command == "check_node":
                if len(parts) < 2:
                    print("Usage: check_node <node>")
                else:
                    check_node(graph, parts[1])
            elif command == "update":
                summary = simulate_weekly_update(
                    graph, cache, hubs, departure_hours=[0, 8, 12, 18], seed=graph.data_version
                )
                print("Weekly travel-time update complete.")
                print(f"Old data version: week_{summary['old_version']}")
                print(f"New data version: week_{summary['new_version']}")
                print(f"Updated roads: {summary['updated_edges']}")
                print(f"Cache entries removed: {summary['cache_entries_removed']}")
                print(f"Precomputed hub paths: {summary['precomputed_paths']}")
                print(f"Current cache size: {summary['cache_size']}")
            elif command == "stats":
                print(f"\n--- System Stats ---")
                print(f"Nodes in Memory: {graph.node_count()}")
                print(f"Edges in Memory: {graph.edge_count()}")
                print(f"Cache Entries:   {cache.size()}")
                print(f"Active Hubs:     {len(hubs)}\n")
            elif command == "save":
                if len(parts) < 2:
                    print("Usage: save <filename>")
                else:
                    graph.save(parts[1])
                    print(f"Graph successfully saved to {parts[1]}")

            elif command == "query":
                handle_query(user_input, graph, cache)
            else:
                print(f"Command '{command}' not recognized. Type 'help' for a list of commands.")

        except KeyboardInterrupt:
            print("\nForced exit. Goodbye!")
            break
        except Exception as e:
            print(f"Runtime Error: {e}")

if __name__ == "__main__":
    main()