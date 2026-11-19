"""Add elevation gain/loss to every graph edge using USGS 3DEP data via py3dep.

Steps
-----
1. Load the graph from backend/data/trail_graph.gpickle.
2. For every edge, interpolate sample points every 50 m.
3. Collect all unique sample points (deduplicated to 5 d.p.).
4. Fetch elevations in one batch call via py3dep.
5. Walk each edge's elevation profile → compute gain_m and loss_m.
6. Re-persist the graph.
"""

import sys
from pathlib import Path

# Allow ``import trail_graph`` when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from trail_graph.build_graph import load_graph
from trail_graph.geometry import interpolate_points

import pickle

try:
    import py3dep
except ImportError:
    print("py3dep is not installed. Run: pip install py3dep", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

GRAPH_PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "trail_graph.gpickle"


def _round_coord(lat: float, lon: float, decimals: int = 5) -> tuple[float, float]:
    return round(lat, decimals), round(lon, decimals)


def main() -> None:
    if not GRAPH_PATH.exists():
        print(f"Graph not found at {GRAPH_PATH}. Run 'make build-graph' first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading graph from {GRAPH_PATH} …")
    G = load_graph(GRAPH_PATH)
    edges = list(G.edges(keys=True, data=True))
    print(f"  {G.number_of_nodes():,} nodes, {len(edges):,} edges")

    # --- Collect all unique sample points across every edge ---
    print("Interpolating sample points …")
    # Map from rounded coord → index into the master list
    coord_index: dict[tuple[float, float], int] = {}
    # Per-edge list of sample-point indices
    edge_sample_indices: list[list[int]] = []

    for _u, _v, _k, data in tqdm(edges, desc="Interpolating"):
        coords = data.get("coords", [])
        samples = interpolate_points(coords, interval_m=50)
        indices: list[int] = []
        for lat, lon in samples:
            key = _round_coord(lat, lon)
            if key not in coord_index:
                coord_index[key] = len(coord_index)
            indices.append(coord_index[key])
        edge_sample_indices.append(indices)

    all_coords = list(coord_index.keys())  # (lat, lon) in insertion order
    print(f"  {len(all_coords):,} unique sample points across {len(edges):,} edges")

    # --- Batch-fetch elevations ---
    print("Fetching elevations from USGS 3DEP …")
    # py3dep expects a list of (lon, lat) tuples or a dict; we pass (lon, lat).
    lonlat_coords = [(lon, lat) for lat, lon in all_coords]
    try:
        elevations = py3dep.elevation_bycoords(lonlat_coords, crs="epsg:4326")
    except Exception as exc:
        print(f"py3dep elevation fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # elevations is a list aligned with lonlat_coords
    elev_by_index: list[float] = list(elevations)
    print(f"  Received {len(elev_by_index):,} elevation values")

    # --- Compute gain/loss per edge ---
    print("Computing gain/loss per edge …")
    missing_elev_edges = 0

    for i, (u, v, k, data) in enumerate(tqdm(edges, desc="Computing gain/loss")):
        indices = edge_sample_indices[i]
        if not indices:
            missing_elev_edges += 1
            continue

        profile = [elev_by_index[idx] for idx in indices]

        # Filter out None or NaN values
        valid_profile = [e for e in profile if e is not None and e == e]
        if len(valid_profile) < 2:
            missing_elev_edges += 1
            continue

        gain = 0.0
        loss = 0.0
        for j in range(1, len(valid_profile)):
            diff = valid_profile[j] - valid_profile[j - 1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        G[u][v][k]["gain_m"] = round(gain, 1)
        G[u][v][k]["loss_m"] = round(loss, 1)

    print(f"  Edges missing elevation data: {missing_elev_edges:,}")

    # --- Re-persist ---
    with open(GRAPH_PATH, "wb") as fh:
        pickle.dump(G, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Graph with elevation saved to {GRAPH_PATH}")


if __name__ == "__main__":
    main()
