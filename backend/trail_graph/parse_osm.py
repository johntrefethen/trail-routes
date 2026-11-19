import json
from pathlib import Path


def load(path: str | Path) -> tuple[dict, list]:
    """Parse a raw Overpass JSON file (fetched with ``out geom;``).

    Returns
    -------
    nodes : dict
        Mapping of OSM node ID (int) → (lat, lon).  Built from the inline
        geometry of every way; we only store nodes we actually see on a way.
    ways : list
        Each entry is a dict::

            {
                "id": <osm way id>,
                "tags": {<tag dict>},
                "node_ids": [<ordered node ids>],
                "coords":   [(lat, lon), ...]   # same length as node_ids
            }
    """
    raw = json.loads(Path(path).read_text())

    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict] = []

    for element in raw.get("elements", []):
        if element["type"] != "way":
            continue

        node_ids: list[int] = element.get("nodes", [])
        geometry: list[dict] = element.get("geometry", [])

        # ``out geom;`` inlines geometry as [{lat, lon}, ...] in the same order
        # as the nodes array.
        if len(node_ids) != len(geometry):
            # Malformed element – skip rather than crash.
            continue

        coords: list[tuple[float, float]] = []
        for nid, geom in zip(node_ids, geometry):
            lat, lon = float(geom["lat"]), float(geom["lon"])
            nodes[nid] = (lat, lon)
            coords.append((lat, lon))

        ways.append(
            {
                "id": element["id"],
                "tags": element.get("tags", {}),
                "node_ids": node_ids,
                "coords": coords,
            }
        )

    return nodes, ways
