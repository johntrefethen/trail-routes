"""Preset trailhead definitions for the Larimer County corridor.

Coordinates are approximate parking-lot positions. The routing node is
found at startup by snapping to the nearest graph node.

NOTE: Verify these coordinates against current satellite imagery before
publishing. OSM junction nodes may be hundreds of metres from the actual
parking lot; that is expected — routing starts at the nearest trail node.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .geometry import haversine_m


@dataclass
class Trailhead:
    id: str
    name: str
    lat: float          # approximate parking-lot lat
    lon: float          # approximate parking-lot lon
    node_id: int = field(default=0, repr=False)   # nearest graph node (set at startup)
    node_lat: float = field(default=0.0, repr=False)
    node_lon: float = field(default=0.0, repr=False)
    snap_m: float = field(default=0.0, repr=False)  # distance from lot to graph node


# Approximate trailhead parking-lot coordinates.
# Update these if you get more precise GPS readings.
_DEFS: list[tuple] = [
    ("htmo",        "Horsetooth Mountain Open Space", 40.5241, -105.1811),
    ("soderberg",   "Soderberg Open Space",           40.5365, -105.1920),
    ("lory_timber", "Lory State Park (Timber)",       40.5783, -105.1951),
    ("maxwell",     "Maxwell Natural Area",            40.5468, -105.1517),
    ("blue_sky",    "Blue Sky / Coyote Ridge",         40.4650, -105.1527),
]

TRAILHEADS: list[Trailhead] = [
    Trailhead(id=tid, name=name, lat=lat, lon=lon)
    for tid, name, lat, lon in _DEFS
]

_by_id: dict[str, Trailhead] = {t.id: t for t in TRAILHEADS}


def get(trailhead_id: str) -> Trailhead | None:
    return _by_id.get(trailhead_id)


def snap_to_graph(G: nx.MultiGraph) -> None:
    """Snap every trailhead to its nearest graph node. Call once at startup."""
    for th in TRAILHEADS:
        best_id, best_d = None, float("inf")
        for nid, attrs in G.nodes(data=True):
            d = haversine_m(th.lat, th.lon, attrs["lat"], attrs["lon"])
            if d < best_d:
                best_d, best_id = d, nid
        th.node_id = best_id
        th.node_lat = G.nodes[best_id]["lat"]
        th.node_lon = G.nodes[best_id]["lon"]
        th.snap_m = best_d
