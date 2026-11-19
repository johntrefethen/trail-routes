"""Validate the trail graph against known routes.

Usage
-----
    python scripts/validate.py [--routes ROUTES_JSON] [--manual-edges EDGES_JSON]

The routes JSON file (default: scripts/known_routes.json) has the shape::

    [
      {
        "name": "Horsetooth Rock Loop",
        "waypoints": [[40.5241,-105.1810], [40.5190,-105.1750], [40.5241,-105.1810]],
        "expected_distance_km": 9.7,
        "expected_gain_m": 366
      },
      ...
    ]

Each waypoint is [lat, lon].  The script finds the nearest graph node to each
waypoint and routes between them in sequence using Dijkstra (weight=distance_m).

Manual edges (optional) can be added to patch missing connectors::

    [
      {
        "from": [40.5241, -105.1810],
        "to":   [40.5200, -105.1760],
        "distance_m": 350,
        "gain_m": 20,
        "loss_m": 5,
        "note": "informal connector near Horsetooth Rock summit"
      }
    ]
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from trail_graph.build_graph import load_graph
from trail_graph.geometry import haversine_m

import networkx as nx

GRAPH_PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "trail_graph.gpickle"
DEFAULT_ROUTES = Path(__file__).resolve().parent / "known_routes.json"


def nearest_node(G: nx.MultiGraph, lat: float, lon: float) -> int:
    """Return the graph node ID closest (Euclidean proxy) to (lat, lon)."""
    best_id = None
    best_dist = math.inf
    for nid, attrs in G.nodes(data=True):
        d = haversine_m(lat, lon, attrs["lat"], attrs["lon"])
        if d < best_dist:
            best_dist = d
            best_id = nid
    return best_id, best_dist


def route_between(G: nx.MultiGraph, start_id: int, end_id: int):
    """Return (node_path, total_distance_m, total_gain_m, missing_elevation_edges)."""
    try:
        path = nx.shortest_path(G, start_id, end_id, weight="distance_m")
    except nx.NetworkXNoPath:
        return None, None, None, None
    except nx.NodeNotFound as exc:
        print(f"  Node not found: {exc}", file=sys.stderr)
        return None, None, None, None

    total_dist = 0.0
    total_gain = 0.0
    missing = 0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        # MultiGraph: pick the edge with minimum distance_m
        edge_data = min(G[u][v].values(), key=lambda d: d.get("distance_m", math.inf))
        total_dist += edge_data.get("distance_m", 0.0)
        gain = edge_data.get("gain_m")
        if gain is None:
            missing += 1
        else:
            total_gain += gain

    return path, total_dist, total_gain, missing


def add_manual_edges(G: nx.MultiGraph, edges_path: Path) -> None:
    manual = json.loads(edges_path.read_text())
    added = 0
    for me in manual:
        from_lat, from_lon = me["from"]
        to_lat, to_lon = me["to"]
        from_id, _ = nearest_node(G, from_lat, from_lon)
        to_id, _ = nearest_node(G, to_lat, to_lon)
        G.add_edge(
            from_id,
            to_id,
            distance_m=me.get("distance_m", haversine_m(from_lat, from_lon, to_lat, to_lon)),
            gain_m=me.get("gain_m"),
            loss_m=me.get("loss_m"),
            tags={"note": me.get("note", "manual edge")},
            coords=[(from_lat, from_lon), (to_lat, to_lon)],
            osm_way_id=None,
        )
        added += 1
    print(f"Added {added} manual edge(s) from {edges_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate trail graph against known routes.")
    parser.add_argument(
        "--routes",
        type=Path,
        default=DEFAULT_ROUTES,
        help=f"JSON file with known routes (default: {DEFAULT_ROUTES})",
    )
    parser.add_argument(
        "--manual-edges",
        type=Path,
        default=None,
        help="JSON file with manual connector edges to add before routing",
    )
    args = parser.parse_args()

    if not GRAPH_PATH.exists():
        print(f"Graph not found at {GRAPH_PATH}. Run 'make build-graph' first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading graph …")
    G = load_graph(GRAPH_PATH)
    print(f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    if args.manual_edges and args.manual_edges.exists():
        add_manual_edges(G, args.manual_edges)

    if not args.routes.exists():
        print(f"\nNo routes file found at {args.routes}.")
        print("Create it with the following template and fill in expected values:")
        template = [
            {
                "name": "Horsetooth Rock Loop",
                "waypoints": [[40.5241, -105.1810], [40.5190, -105.1750], [40.5241, -105.1810]],
                "expected_distance_km": 9.7,
                "expected_gain_m": 366,
            },
            {
                "name": "Soderberg-Mill Creek Loop",
                "waypoints": [[40.5500, -105.1600], [40.5450, -105.1500], [40.5500, -105.1600]],
                "expected_distance_km": 8.0,
                "expected_gain_m": 300,
            },
        ]
        print(json.dumps(template, indent=2))
        sys.exit(0)

    routes = json.loads(args.routes.read_text())
    print(f"\nValidating {len(routes)} route(s) …\n")

    all_ok = True
    for route in routes:
        name = route["name"]
        waypoints = route["waypoints"]
        exp_dist_km = route.get("expected_distance_km")
        exp_gain_m = route.get("expected_gain_m")

        print(f"Route: {name}")

        node_ids = []
        for wp in waypoints:
            nid, snap_dist = nearest_node(G, wp[0], wp[1])
            node_ids.append(nid)
            if snap_dist > 500:
                print(f"  WARNING: nearest node is {snap_dist:.0f} m away from waypoint {wp} — may be a data gap")

        # Route through each consecutive pair of waypoints.
        total_dist = 0.0
        total_gain = 0.0
        total_missing = 0
        route_found = True

        for i in range(len(node_ids) - 1):
            path, dist, gain, missing = route_between(G, node_ids[i], node_ids[i + 1])
            if path is None:
                print(f"  NO PATH found between waypoint {i} and {i+1} "
                      f"(node {node_ids[i]} → {node_ids[i+1]})")
                print(f"  Consider adding a manual edge with --manual-edges.")
                route_found = False
                all_ok = False
                break
            total_dist += dist
            total_gain += gain
            total_missing += missing

        if not route_found:
            continue

        dist_km = total_dist / 1000.0

        def pct_diff(computed, expected):
            if expected and expected != 0:
                return (computed - expected) / expected * 100
            return float("nan")

        dist_diff = pct_diff(dist_km, exp_dist_km)
        gain_diff = pct_diff(total_gain, exp_gain_m)

        exp_dist_str = f"expected ~{exp_dist_km} km, " if exp_dist_km else ""
        exp_gain_str = f"expected ~{exp_gain_m} m, " if exp_gain_m else ""

        print(f"  Distance:  {dist_km:.1f} km  ({exp_dist_str}diff {dist_diff:+.1f}%)")
        print(f"  Gain:      {total_gain:.0f} m   ({exp_gain_str}diff {gain_diff:+.1f}%)")
        print(f"  Missing elevation: {total_missing} edges")

        if exp_dist_km and abs(dist_diff) > 10:
            print(f"  WARN: distance error > 10% — check waypoints or graph connectivity")
            all_ok = False
        if exp_gain_m and abs(gain_diff) > 20:
            print(f"  WARN: gain error > 20% — check elevation data or segment count")
            all_ok = False

        print()

    if all_ok:
        print("All routes within acceptable error bounds.")
    else:
        print("One or more routes failed validation — see warnings above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
