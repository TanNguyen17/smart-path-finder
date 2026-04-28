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

def print_startup_help():
    print("\n" + "="*30)
    print("STARTUP HELP")
    print("="*30)
    print("1. Generate New Graph: Creates a synthetic 70x70 grid.")
    print("   Includes diagonal paths and high-speed 'highways'.")
    print("2. Load from File: Enter the path to a saved .graph file.")
    print("quit: Exit the program.")
    print("="*30 + "\n")

def print_main_help():
    print("\n" + "="*50)
    print("COMMAND REFERENCE")
    print("="*50)
    print("query <src> <dest> [options]")
    print("    Finds paths between nodes (e.g., query 5_5 10_10).")
    print("    Optional parameters:")
    print("      avoid_nodes n1,n2   - Skip specific nodes.")
    print("      avoid_edges n1-n2   - Skip specific road segments.")
    print("      departure <hour>    - Set time (0-23) for traffic.")
    print("\nstats")
    print("    Displays nodes, edges, and cache performance.")
    print("\nsave <filename>")
    print("    Exports the current graph data.")
    print("\nupdate")
    print("    Simulates a new week of traffic data and resets cache.")
    print("\nhelp")
    print("    Shows this command list.")
    print("\nquit / exit")
    print("    Close the program.")
    print("="*50)
    print("COORDINATE TIP: Nodes are named 'Row_Col' (e.g., 0_0 is top-left).")
    print("="*50 + "\n")

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

    # Run and display Distance query
    start_dist = time.perf_counter()
    res_dist, hit_dist = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "distance", query.avoid_nodes, query.avoid_edges
    )
    time_dist = (time.perf_counter() - start_dist) * 1000
    
    print(format_result("distance", res_dist))
    print(f"└─ [Time: {time_dist:.2f}ms | Cache: {'HIT' if hit_dist else 'MISS'}]")

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
        print("\n[1] Generate 70x70 Graph")
        print("[2] Load Graph from File")
        print("Type 'help' for info or 'quit' to exit.")
        
        choice = input("startup > ").strip().lower()

        if choice == 'help':
            print_startup_help()
        elif choice == '1':
            print("\nGenerating graph (70x70 grid + highways)...")
            graph = generate_graph(rows=70, cols=70, diag_prob=0.20, highway_edges=900, seed=42, id_mode="str")
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
    hubs = identify_hubs(graph, top_n=30)
    print(f"Hubs active: {', '.join(hubs[:5])}... and {len(hubs)-5} more.")

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
                print_main_help()
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
            elif command == "update":
                print("Regenerating weekly travel times and clearing cache...")
                simulate_weekly_update(graph, cache, hubs, departure_hours=[0, 8, 12, 18])
                print("Update complete.")
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