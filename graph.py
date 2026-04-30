"""
graph.py — Weighted directed graph using an adjacency list.

Representation
--------------
Each node is a string identifier stored in ``self.nodes`` (a set).
``self.adjacent`` is a dict mapping each node to a list of
(neighbor, distance, travel_times) tuples.  Every edge is stored
in both directions (undirected graph).

Each edge carries:
    - distance       : a positive float (fixed, in abstract distance units)
    - travel_times   : a list of 24 positive floats, one per hour-of-day

Time complexity:
    add_edge        O(1) amortised
    get_neighbors   O(deg(v) × |avoid|)

Space complexity:  O(V + E)  — each edge stored twice (undirected)
"""

import json


class Graph:
    """Undirected weighted graph with time-varying edge traversal costs."""

    def __init__(self):
        self.adjacent = {}   # node_id -> [(neighbor, distance, [24 travel times])]
        self.nodes = set()   # set of all node IDs
        self.coord_map = {}  # node_id -> (row, col), optional grid coordinates

    def add_edge(self, u, v, distance, travel_times):
        """
        Add an undirected edge between nodes u and v.

        Parameters
        ----------
        u, v          : node identifiers (converted to str)
        distance      : positive float — fixed distance of the road
        travel_times  : list of exactly 24 positive floats
        """
        u, v = str(u), str(v)
        if u == v:
            raise ValueError("Cannot add edge from node to itself")

        if distance <= 0:
            raise ValueError("Distance must be positive")

        self._validate_travel_times(travel_times)

        if u not in self.nodes:
            self._add_node(u)

        if v not in self.nodes:
            self._add_node(v)

        distance = float(distance)
        travel_times = [float(x) for x in travel_times]

        self.adjacent[u].append((v, distance, travel_times))
        self.adjacent[v].append((u, distance, travel_times.copy()))

    def get_neighbors(self, node, avoid_nodes=None, avoid_edges=None):
        """
        Return reachable neighbors of *node*, filtering out avoided
        nodes and edges.

        Returns a list of (neighbor, distance, travel_times) tuples.
        """
        node = str(node)
        if node not in self.nodes:
            return []

        avoid_nodes = avoid_nodes or set()
        avoid_edges = avoid_edges or set()

        result = []

        for neighbor, distance, travel_times in self.adjacent[node]:
            if neighbor in avoid_nodes:
                continue
            if (node, neighbor) in avoid_edges or (neighbor, node) in avoid_edges:
                continue
            result.append((neighbor, distance, travel_times))
        return result

    def node_count(self):
        """Return the number of nodes."""
        return len(self.nodes)

    def edge_count(self):
        """Return the number of undirected edges."""
        return sum(len(lst) for lst in self.adjacent.values()) // 2

    def save(self, filepath):
        """Serialise the graph to a JSON file."""
        payload = {
            "nodes": list(self.nodes),
            "adjacent": {}
        }

        for u in self.nodes:
            payload["adjacent"][str(u)] = []
            for v, distance, travel_times in self.adjacent[u]:
                payload["adjacent"][str(u)].append({
                    "to": str(v),
                    "distance": distance,
                    "travel_times": travel_times
                })

        if self.coord_map:
            payload["coord_map"] = {
                str(k): list(v) for k, v in self.coord_map.items()
            }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    @classmethod
    def load(cls, filepath):
        """Deserialise a graph from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)

        graph = cls()

        for node in payload["nodes"]:
            graph._add_node(node)

        for u, edges in payload["adjacent"].items():
            u = str(u)
            graph.adjacent[u] = []
            for edge in edges:
                v = str(edge["to"])
                distance = float(edge["distance"])
                travel_times = [float(x) for x in edge["travel_times"]]
                graph.adjacent[u].append((v, distance, travel_times))

        if "coord_map" in payload:
            for k, v in payload["coord_map"].items():
                graph.coord_map[str(k)] = tuple(v)

        return graph

    def _add_node(self, node_id):
        if node_id not in self.nodes:
            self.nodes.add(node_id)
            self.adjacent[node_id] = []

    def _validate_travel_times(self, travel_times):
        if not isinstance(travel_times, list):
            raise TypeError("Travel times must be a list")
        if len(travel_times) != 24:
            raise ValueError("Travel times must contain exactly 24 values")
        for time in travel_times:
            if time <= 0:
                raise ValueError("Each travel time must be positive")


if __name__ == "__main__":
    g = Graph()
    g.add_edge(1, 2, 10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
    g.add_edge(2, 3, 20, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
    g.add_edge(3, 1, 30, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
    g.save("graph.json")
    g2 = Graph.load("graph.json")
    print(g2.node_count())
    print(g2.edge_count())
    print(g2.get_neighbors(1))
    print(g2.get_neighbors(2))
    print(g2.get_neighbors(3))