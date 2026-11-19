"""Build a routable trail graph from raw OSM data.

Algorithm
---------
1. Identify *split nodes*: any node that is an endpoint of a way, OR appears
   in more than one way (junction).
2. Walk each way's ordered node list; each time we hit a split node we emit a
   segment (edge) and start a new segment from that node.
3. Store segments as edges in a ``networkx.MultiGraph`` so that two trails
   sharing the same junction nodes can still be represented as separate,
   parallel edges.
"""

from __future__ import annotations

import pickle
from collections import Counter
from pathlib import Path

import networkx as nx

from .geometry import haversine_m
from .parse_osm import load as load_osm


def _find_split_nodes(ways: list[dict]) -> set[int]:
    """Return the set of OSM node IDs that must be graph nodes.

    A node is a split point if:
    - it is the first or last node of any way (endpoint), OR
    - it appears in 2 or more *distinct* ways (junction).
    """
    endpoint_ids: set[int] = set()
    appearance_count: Counter[int] = Counter()

    for way in ways:
        node_ids = way["node_ids"]
        if not node_ids:
            continue
        endpoint_ids.add(node_ids[0])
        endpoint_ids.add(node_ids[-1])
        # Count how many ways each interior node appears in
        for nid in node_ids:
            appearance_count[nid] += 1

    junction_ids = {nid for nid, count in appearance_count.items() if count >= 2}
    return endpoint_ids | junction_ids


def _split_way_into_segments(
    way: dict,
    split_nodes: set[int],
) -> list[dict]:
    """Return a list of segments (sub-paths) for one OSM way.

    Each segment dict::

        {
            "node_ids": [start_id, ..., end_id],
            "coords":   [(lat, lon), ...],
            "distance_m": float,
        }
    """
    node_ids = way["node_ids"]
    coords = way["coords"]

    if len(node_ids) < 2:
        return []

    segments: list[dict] = []
    seg_node_ids: list[int] = [node_ids[0]]
    seg_coords: list[tuple[float, float]] = [coords[0]]

    for i in range(1, len(node_ids)):
        nid = node_ids[i]
        coord = coords[i]
        seg_node_ids.append(nid)
        seg_coords.append(coord)

        if nid in split_nodes and i < len(node_ids) - 1:
            # Emit current segment and start the next one from this node.
            dist = sum(
                haversine_m(seg_coords[j][0], seg_coords[j][1],
                            seg_coords[j + 1][0], seg_coords[j + 1][1])
                for j in range(len(seg_coords) - 1)
            )
            segments.append(
                {
                    "node_ids": seg_node_ids,
                    "coords": seg_coords,
                    "distance_m": dist,
                }
            )
            seg_node_ids = [nid]
            seg_coords = [coord]

    # Final (or only) segment
    if len(seg_node_ids) >= 2:
        dist = sum(
            haversine_m(seg_coords[j][0], seg_coords[j][1],
                        seg_coords[j + 1][0], seg_coords[j + 1][1])
            for j in range(len(seg_coords) - 1)
        )
        segments.append(
            {
                "node_ids": seg_node_ids,
                "coords": seg_coords,
                "distance_m": dist,
            }
        )

    return segments


def build_graph(raw_osm_path: str | Path, output_path: str | Path) -> nx.MultiGraph:
    """Parse *raw_osm_path*, build the graph, persist to *output_path*, return it."""
    raw_osm_path = Path(raw_osm_path)
    output_path = Path(output_path)

    print(f"Loading OSM data from {raw_osm_path} …")
    nodes, ways = load_osm(raw_osm_path)
    print(f"  {len(ways):,} ways, {len(nodes):,} nodes")

    print("Detecting split/junction nodes …")
    split_nodes = _find_split_nodes(ways)
    print(f"  {len(split_nodes):,} split nodes")

    print("Building graph …")
    G = nx.MultiGraph()

    # Add every split node as a graph node.
    for nid in split_nodes:
        if nid in nodes:
            lat, lon = nodes[nid]
            G.add_node(nid, lat=lat, lon=lon, osm_id=nid)

    edge_count = 0
    for way in ways:
        segments = _split_way_into_segments(way, split_nodes)
        for seg in segments:
            u = seg["node_ids"][0]
            v = seg["node_ids"][-1]
            if u not in G or v not in G:
                # Both endpoints must be split nodes; skip malformed segments.
                continue
            G.add_edge(
                u,
                v,
                distance_m=seg["distance_m"],
                osm_way_id=way["id"],
                tags=way["tags"],
                coords=seg["coords"],
                gain_m=None,
                loss_m=None,
            )
            edge_count += 1

    print(f"  {G.number_of_nodes():,} graph nodes, {edge_count:,} edges")

    # Warn about isolated nodes (they won't affect routing but are suspicious).
    isolated = list(nx.isolates(G))
    if isolated:
        print(f"  WARNING: {len(isolated):,} isolated nodes (no edges) — may indicate data gaps")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        pickle.dump(G, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Graph saved to {output_path}")

    return G


def load_graph(path: str | Path) -> nx.MultiGraph:
    """Load a previously built graph from a pickle file."""
    with open(path, "rb") as fh:
        return pickle.load(fh)
