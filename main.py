"""
main.py — Entry point for the Smart Path Finder.

Provides an interactive CLI to generate/load graphs and run routing queries.
"""

from graph import Graph
from generator import generate_graph
from cache import (PathCache, run_query_cached, identify_hubs,
                   precompute_hub_paths, simulate_weekly_update)
from query import parse_query, format_result


def print_help():
    print("""
    Available commands:
        query <source> <destination> [avoid_nodes n1,n2,...] [avoid_edges e1-e2,e3-e4,...] [departure <hour>]
            Run a routing query

        stats
            Show graph statistics and cache info

        save <filename>
            Save current graph to file

        update
            Simulate weekly travel time update (invalidate cache and re-precompute hubs)

        help
            Show this help message

        quit
            Exit the program
    """)


def main():
    print("=== Smart Path Finder ===\n")

    # A. Load or generate graph
    print("Choose option:")
    print("   1. Generate new graph")
    print("   2. Load from file")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        print("\nGenerating graph (70x70 grid + highways)...")
        graph = generate_graph(
            rows=70,
            cols=70,
            diag_prob=0.20,
            highway_edges=900,
            seed=42,
            id_mode="str"
        )
        print(f"Generated: {graph.node_count()} nodes, {graph.edge_count()} edges")

    elif choice == "2":
        filename = input("Enter filename: ").strip()
        try:
            graph = Graph.load(filename)
            print(f"Loaded: {graph.node_count()} nodes, {graph.edge_count()} edges")
        except Exception as e:
            print(f"Error loading graph: {e}")
            return
    else:
        print("Invalid choice. Exiting.")
        return

    # B. Initialize cache and hubs
    cache = PathCache()
    print("\nIdentifying hub nodes...")
    hubs = identify_hubs(graph, top_n=30)
    print(f"Identified {len(hubs)} hubs: {hubs}")

    print("\nPrecomputing hub paths (this may take a while)...")
    count = precompute_hub_paths(graph, cache, hubs, departure_hours=[0, 8, 12, 18])
    print(f"Precomputed {count} paths. Cache size: {cache.size()}\n")

    # C. Main command loop
    print("Type 'help' for commands or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            command = user_input.split()[0].lower()

            if command == "quit" or command == "exit":
                print("Goodbye!")
                break

            elif command == "help":
                print_help()

            elif command == "stats":
                print(f"Graph: {graph.node_count()} nodes, {graph.edge_count()} edges")
                print(f"Cache: {cache.size()} entries")

            elif command == "save":
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: save <filename>")
                else:
                    filename = parts[1]
                    graph.save(filename)
                    print(f"Graph saved to {filename}")

            elif command == "update":
                print("Simulating weekly travel time update...")
                simulate_weekly_update(graph, cache, hubs,
                                       departure_hours=[0, 8, 12, 18])

            elif command == "query":
                handle_query(user_input, graph, cache)

            else:
                print(f"Unknown command: {command}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

        except Exception as e:
            print(f"Error: {e}")


def handle_query(user_input, graph, cache):
    """Parse and execute a query, showing both distance and time results."""
    import time

    query = parse_query(user_input)

    if query is None:
        print("Invalid query format.")
        print("Example: query 0_0 69_69 avoid_nodes 30_30,35_35 departure 8")
        return

    # Run distance query
    start = time.perf_counter()
    result_distance, hit_distance = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "distance", query.avoid_nodes, query.avoid_edges
    )
    time_distance = time.perf_counter() - start

    # Run time query
    start = time.perf_counter()
    result_time, hit_time = run_query_cached(
        graph, cache, query.source, query.destination,
        query.departure_hour, "time", query.avoid_nodes, query.avoid_edges
    )
    time_time = time.perf_counter() - start

    # Display results
    print()
    print(format_result("distance", result_distance))
    print(f"[Computed in {time_distance*1000:.2f} ms, cache {'HIT' if hit_distance else 'MISS'}]\n")

    print(format_result("time", result_time))
    print(f"[Computed in {time_time*1000:.2f} ms, cache {'HIT' if hit_time else 'MISS'}]\n")


if __name__ == "__main__":
    main()