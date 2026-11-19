"""Route search algorithm for the trail graph.

Finds loop and out-and-back routes from a trailhead node that are close
to a target distance and optional target elevation gain.

Loop strategy
-------------
1. Run Dijkstra from the start to find all nodes within 1.4× target distance.
2. Identify "turnaround" candidates at 35–65 % of target distance.
3. For each candidate, attempt a return path that avoids the outbound edges
   (by returning None from a custom weight function for those edges).
4. Score each complete loop by distance deviation + gain deviation.
5. Deduplicate near-identical routes; return the top N.

Out-and-back strategy
---------------------
Find the node closest to target_dist/2 from start (by Dijkstra distance),
return the path there + same path reversed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import networkx as nx

from .geometry import haversine_m


@dataclass
class RouteResult:
    route_type: str                              # "loop" | "out-and-back"
    distance_m: float
    gain_m: float
    loss_m: float
    coords: list[tuple[float, float]]            # (lat, lon)
    trail_names: list[str]
    elevation_profile: list[tuple[float, float]] # (cumulative_dist_m, cumulative_gain_m)
    score: float = field(default=0.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_routes(
    G: nx.MultiGraph,
    start_node: int,
    target_dist_m: float,
    target_gain_m: float | None = None,
    route_type: str = "loop",
    max_results: int = 5,
) -> list[RouteResult]:
    """Return up to *max_results* routes sorted best-first."""
    if route_type == "out-and-back":
        return _find_out_and_backs(G, start_node, target_dist_m, target_gain_m, max_results)
    return _find_loops(G, start_node, target_dist_m, target_gain_m, max_results)


def nearest_node(G: nx.MultiGraph, lat: float, lon: float) -> int:
    """Return the graph node ID closest to (lat, lon)."""
    best_id, best_d = None, math.inf
    for nid, attrs in G.nodes(data=True):
        d = haversine_m(lat, lon, attrs["lat"], attrs["lon"])
        if d < best_d:
            best_d, best_id = d, nid
    return best_id


# ---------------------------------------------------------------------------
# Loop finder
# ---------------------------------------------------------------------------

def _find_loops(
    G: nx.MultiGraph,
    start_node: int,
    target_dist_m: float,
    target_gain_m: float | None,
    max_results: int,
) -> list[RouteResult]:
    cutoff = target_dist_m * 1.4

    # Shortest paths from start
    lengths, paths = nx.single_source_dijkstra(
        G, start_node, weight="distance_m", cutoff=cutoff
    )

    # Turnaround nodes: 35–65 % of target distance away
    turnarounds = [
        (node, d, paths[node])
        for node, d in lengths.items()
        if 0.35 * target_dist_m <= d <= 0.65 * target_dist_m
        and node != start_node
    ]

    if not turnarounds:
        return []

    # Prefer high-degree nodes (more outgoing trails = better loop chances);
    # break ties by closeness of outbound distance to target/2.
    turnarounds.sort(
        key=lambda x: (
            -G.degree(x[0]),
            abs(x[1] - target_dist_m / 2) / target_dist_m,
        )
    )
    turnarounds = turnarounds[:80]

    results: list[RouteResult] = []
    seen_node_sets: list[frozenset] = []

    for mid_node, out_dist, outbound in turnarounds:
        # Build the excluded-edge set from the outbound path.
        excluded: frozenset[tuple] = _outbound_edges(G, outbound)

        def _weight(u: int, v: int, d: dict, excl: frozenset = excluded) -> float | None:
            """Weight fn: skip outbound edges; return None to let NetworkX ignore edge."""
            best = None
            for k, attrs in d.items():
                if (u, v, k) not in excl and (v, u, k) not in excl:
                    w = attrs.get("distance_m")
                    if w is not None and (best is None or w < best):
                        best = w
            return best

        try:
            ret_len, return_path = nx.bidirectional_dijkstra(
                G, mid_node, start_node, weight=_weight
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXError):
            continue

        total_dist = out_dist + ret_len
        if abs(total_dist - target_dist_m) / target_dist_m > 0.25:
            continue

        full_path = outbound + return_path[1:]

        # Diversity check: skip routes that share > 70 % nodes with an earlier result.
        node_set = frozenset(full_path)
        if any(
            len(node_set & prev) / max(len(node_set), len(prev)) > 0.70
            for prev in seen_node_sets
        ):
            continue
        seen_node_sets.append(node_set)

        gain_m, loss_m, coords, trail_names = _extract_path_data(G, full_path)
        profile = _build_elevation_profile(G, full_path)
        score = _score(total_dist, gain_m, target_dist_m, target_gain_m)

        results.append(
            RouteResult(
                route_type="loop",
                distance_m=total_dist,
                gain_m=gain_m,
                loss_m=loss_m,
                coords=coords,
                trail_names=trail_names,
                elevation_profile=profile,
                score=score,
            )
        )

        if len(results) >= max_results * 3:
            break

    results.sort(key=lambda r: r.score)
    return results[:max_results]


# ---------------------------------------------------------------------------
# Out-and-back finder
# ---------------------------------------------------------------------------

def _find_out_and_backs(
    G: nx.MultiGraph,
    start_node: int,
    target_dist_m: float,
    target_gain_m: float | None,
    max_results: int,
) -> list[RouteResult]:
    cutoff = target_dist_m * 0.6
    lengths, paths = nx.single_source_dijkstra(
        G, start_node, weight="distance_m", cutoff=cutoff
    )

    # Find nodes near target_dist/2
    half = target_dist_m / 2
    candidates = sorted(
        [(node, d, paths[node]) for node, d in lengths.items() if node != start_node],
        key=lambda x: abs(x[1] - half),
    )[:max_results * 4]

    results: list[RouteResult] = []
    seen: list[frozenset] = []

    for dest_node, out_dist, outbound in candidates:
        total_dist = out_dist * 2
        if abs(total_dist - target_dist_m) / target_dist_m > 0.25:
            continue

        full_path = outbound + list(reversed(outbound[:-1]))
        node_set = frozenset(outbound)
        if any(len(node_set & prev) / max(len(node_set), len(prev)) > 0.70 for prev in seen):
            continue
        seen.append(node_set)

        gain_m, loss_m, coords, trail_names = _extract_path_data(G, full_path)
        profile = _build_elevation_profile(G, full_path)
        score = _score(total_dist, gain_m, target_dist_m, target_gain_m)

        results.append(
            RouteResult(
                route_type="out-and-back",
                distance_m=total_dist,
                gain_m=gain_m,
                loss_m=loss_m,
                coords=coords,
                trail_names=trail_names,
                elevation_profile=profile,
                score=score,
            )
        )
        if len(results) >= max_results:
            break

    results.sort(key=lambda r: r.score)
    return results[:max_results]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _outbound_edges(G: nx.MultiGraph, path: list[int]) -> frozenset[tuple]:
    """Return the set of (u, v, k) tuples used by *path* (minimum-weight edge per hop)."""
    edges = set()
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        best_k = min(
            G[u][v], key=lambda k: G[u][v][k].get("distance_m", math.inf)
        )
        edges.add((u, v, best_k))
        edges.add((v, u, best_k))
    return frozenset(edges)


def _extract_path_data(
    G: nx.MultiGraph, path: list[int]
) -> tuple[float, float, list[tuple[float, float]], list[str]]:
    """Return (gain_m, loss_m, coords, trail_names) for a node path."""
    coords: list[tuple[float, float]] = []
    gain_m = 0.0
    loss_m = 0.0
    trail_names: list[str] = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        best_k = min(G[u][v], key=lambda k: G[u][v][k].get("distance_m", math.inf))
        edge = G[u][v][best_k]

        # Coordinate list for this segment
        seg_coords: list[tuple[float, float]] = edge.get(
            "coords",
            [(G.nodes[u]["lat"], G.nodes[u]["lon"]), (G.nodes[v]["lat"], G.nodes[v]["lon"])],
        )

        # Align direction: ensure first coord is closest to our incoming position.
        if seg_coords:
            start_pos = (G.nodes[u]["lat"], G.nodes[u]["lon"])
            d_first = haversine_m(start_pos[0], start_pos[1], seg_coords[0][0], seg_coords[0][1])
            d_last = haversine_m(start_pos[0], start_pos[1], seg_coords[-1][0], seg_coords[-1][1])
            if d_last < d_first:
                seg_coords = list(reversed(seg_coords))

        # Determine gain/loss direction: if reversed, swap gain↔loss.
        forward = haversine_m(
            G.nodes[u]["lat"], G.nodes[u]["lon"],
            (edge.get("coords") or [(0, 0)])[0][0],
            (edge.get("coords") or [(0, 0)])[0][1],
        ) < 50  # within 50 m = same direction as stored

        if forward:
            gain_m += edge.get("gain_m") or 0.0
            loss_m += edge.get("loss_m") or 0.0
        else:
            gain_m += edge.get("loss_m") or 0.0
            loss_m += edge.get("gain_m") or 0.0

        # Merge coords (drop duplicate junction point).
        if coords:
            coords.extend(seg_coords[1:])
        else:
            coords.extend(seg_coords)

        # Trail name
        name = edge.get("tags", {}).get("name", "")
        if name and (not trail_names or trail_names[-1] != name):
            trail_names.append(name)

    return gain_m, loss_m, coords, trail_names


def _build_elevation_profile(
    G: nx.MultiGraph, path: list[int]
) -> list[tuple[float, float]]:
    """Return [(cumulative_dist_m, cumulative_gain_m), ...] along the path."""
    profile: list[tuple[float, float]] = [(0.0, 0.0)]
    cum_dist = 0.0
    cum_gain = 0.0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        best_k = min(G[u][v], key=lambda k: G[u][v][k].get("distance_m", math.inf))
        edge = G[u][v][best_k]
        seg_dist = edge.get("distance_m", 0.0)
        seg_gain = edge.get("gain_m") or 0.0
        cum_dist += seg_dist
        cum_gain += seg_gain
        profile.append((round(cum_dist, 1), round(cum_gain, 1)))

    return profile


def _score(
    dist_m: float,
    gain_m: float,
    target_dist_m: float,
    target_gain_m: float | None,
) -> float:
    dist_err = abs(dist_m - target_dist_m) / max(target_dist_m, 1)
    if target_gain_m and target_gain_m > 0:
        gain_err = abs(gain_m - target_gain_m) / target_gain_m
        return dist_err + 0.5 * gain_err
    return dist_err
