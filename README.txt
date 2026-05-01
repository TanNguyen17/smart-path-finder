=====================================
  Smart Path Finder - README
=====================================

1. ENVIRONMENT SETUP
--------------------
- Python 3.10 or higher is required.
- No external libraries are needed. All data structures and algorithms
  are implemented from scratch using only Python standard library modules
  (json, random, time, dataclasses).

2. HOW TO RUN
-------------
  python main.py

On startup you will be prompted to either:
  1) Generate a new graph: You can specify custom grid dimensions (e.g., 70x70).
     Includes diagonal paths and high-speed highway edges.
  2) Load a previously saved graph from a JSON file (e.g., graph.json).

After the graph is loaded, the system precomputes hub paths (scaling with 
map size) and enters an interactive command loop.

To run the evaluation benchmarks:
  python evaluation.py

3. INPUT FORMAT
---------------
Queries are entered at the interactive prompt using the following format:

  query <source> <destination> [avoid_nodes n1,n2,...] [avoid_edges u1-v1,u2-v2,...] [departure <hour>]

Parameters:
  source        - Source node ID (e.g., 0_0)
  destination   - Destination node ID (e.g., 69_69)
  avoid_nodes   - (Optional) Comma-separated list of node IDs to exclude
  avoid_edges   - (Optional) Comma-separated list of edges to exclude, each as u-v
  departure     - (Optional) Departure hour (0-23), defaults to 0

Examples:
  query 0_0 69_69
  query 0_0 30_30 departure 8
  query 10_10 50_50 avoid_nodes 30_30,35_35
  query 10_10 50_50 avoid_edges 20_20-21_20,30_30-31_30 departure 17

System Commands:
  map_info     - Show node naming rules and current map dimensions
  examples     - Show copy-ready example queries for this map
  sample_nodes - Show valid sample node IDs
  check_node <n> - Check node existence and list its neighbors
  stats        - Show graph and cache performance statistics
  save <f>     - Save the current graph to a JSON file
  update       - Simulate a weekly traffic-data update (invalidates cache)
  help         - Show full command list
  quit         - Exit the program

4. OUTPUT FORMAT
----------------
For each query, the system performs a comparative analysis:

  === Shortest distance path (Standard Dijkstra) ===
  Total distance: 97.14 km
  Total travel time: 3.42 hours
  Path: 0_0 -> 0_1 -> ... -> 69_69
  Nodes explored: 4500
  └─ [Time: 45.20ms | Cache: MISS]

  === Shortest distance path (Bidirectional Dijkstra) ===
  Total distance: 97.14 km
  Total travel time: 3.42 hours
  Path: 0_0 -> 0_1 -> ... -> 69_69
  Nodes explored: 2100
  └─ [Time: 22.15ms | Cache: MISS]

  === Quickest path (Time-Aware Dijkstra) ===
  Total distance: 102.30 km
  Total travel time: 2.81 hours
  Path: 0_0 -> 1_0 -> ... -> 69_69
  Nodes explored: 4800
  └─ [Time: 50.10ms | Cache: MISS]

5. FILE STRUCTURE
-----------------
  main.py         - Entry point and interactive command loop
  graph.py        - Graph data structure (adjacency list) with save/load
  heap.py         - Custom MinHeap with O(log V) decrease-key
  algorithms.py   - Dijkstra (distance, time) and Bidirectional Dijkstra
  query.py        - Query parser and result formatter
  generator.py    - Synthetic graph generator with traffic profiles
  cache.py        - Path caching and hub precomputation
  evaluation.py   - Benchmarking and empirical evaluation suite

6. DEMO VIDEO LINK
------------------
[INSERT DEMO VIDEO LINK HERE]
