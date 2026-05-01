"""
query.py — Query parsing and result formatting.

Supports the following query syntax:
    query <source> <destination> [avoid_nodes n1,n2,...] [avoid_edges u-v,...] [departure <hour>]
"""

from dataclasses import dataclass


@dataclass
class Query:
    """Parsed routing query."""
    source: str
    destination: str
    avoid_nodes: set
    avoid_edges: set
    departure_hour: int


def parse_query(query_string):
    """
    Parse a query string into a Query object.

    Returns None if the format is invalid.
    """
    parts = query_string.strip().split()

    if len(parts) < 3:
        return None

    if parts[0].lower() != "query":
        return None

    source = str(parts[1])
    destination = str(parts[2])
    avoid_nodes = set()
    avoid_edges = set()
    departure_hour = 0

    i = 3
    while i < len(parts):
        arg = parts[i].lower()

        if arg == "avoid_nodes":
            if i + 1 >= len(parts):
                return None
            node_list = parts[i + 1].split(",")
            avoid_nodes = set(str(n.strip()) for n in node_list if n.strip())
            i += 2

        elif arg == "avoid_edges":
            if i + 1 >= len(parts):
                return None
            edge_list = parts[i + 1].split(",")
            for edge_str in edge_list:
                edge_str = edge_str.strip()
                if "-" in edge_str:
                    u, v = edge_str.split("-", 1)
                    avoid_edges.add((str(u.strip()), str(v.strip())))
            i += 2

        elif arg == "departure":
            if i + 1 >= len(parts):
                return None

            try:
                departure_hour = int(parts[i + 1])
                if departure_hour < 0 or departure_hour > 23:
                    return None
            except ValueError:
                return None
            i += 2
        else:
            i += 1

    return Query(
        source=source,
        destination=destination,
        avoid_nodes=avoid_nodes,
        avoid_edges=avoid_edges,
        departure_hour=departure_hour
    )


def format_result(mode, result, label=None):
    """
    Format a routing result dict for display.

    Parameters
    ----------
    mode   : "distance" or "time"
    result : dict with keys path, total_distance, total_time, nodes_explored
             or None if no path was found
    label  : optional custom header string
    """
    if result is None:
        return f"=== No path found ({mode}) ===\n"

    path = result["path"]
    total_distance = result["total_distance"]
    total_travel_time = result["total_time"]
    nodes_explored = result["nodes_explored"]

    if label:
        header = f"=== {label} ==="
    elif mode == "distance":
        header = "=== Shortest distance path ==="
    elif mode == "time":
        header = "=== Quickest path ==="
    else:
        header = f"=== Path found ({mode}) ==="

    path_str = " -> ".join(path)

    output = f"{header}\n"
    output += f"Total distance: {total_distance:.2f} km\n"
    output += f"Total travel time: {total_travel_time:.2f} hours\n"
    output += f"Nodes explored: {nodes_explored}\n"
    output += f"Path ({len(path)} nodes): {path_str}\n"

    return output


if __name__ == "__main__":
    test_query = "query A B avoid_nodes C,D avoid_edges E-F departure 8"
    parsed = parse_query(test_query)
    print(parsed)