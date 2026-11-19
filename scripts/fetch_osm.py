"""Download trail data for the Larimer County corridor.

Default source: Geofabrik Colorado state PBF (~350 MB, reliable, no rate limits).
Alternative:    Overpass API live query (use --source overpass).

Geofabrik path
--------------
1. Download colorado-latest.osm.pbf to backend/data/ (skipped if already present).
2. Filter with osmium (pyosmium) for trail ways in the bounding box.
3. Write Overpass-compatible JSON to backend/data/raw_osm.json.

Overpass path
-------------
Live query with retry/backoff → backend/data/raw_osm.json.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

try:
    from tqdm import tqdm as _tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

BBOX = (40.44, -105.26, 40.65, -105.01)  # south, west, north, east
HIGHWAY_TAGS = {"path", "track", "footway", "bridleway"}

GEOFABRIK_URL = "https://download.geofabrik.de/north-america/us/colorado-latest.osm.pbf"

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
PBF_PATH = DATA_DIR / "colorado-latest.osm.pbf"
OUTPUT_PATH = DATA_DIR / "raw_osm.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = f"""
[out:json][timeout:120];
(
  way["highway"~"^(path|track|footway|bridleway)$"]
     ({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
);
out geom;
""".strip()

MAX_RETRIES = 3
BACKOFF_BASE = 10  # seconds


# ---------------------------------------------------------------------------
# Geofabrik source
# ---------------------------------------------------------------------------

def download_pbf(url: str, dest: Path) -> None:
    """Stream-download the PBF with a progress bar."""
    print(f"Downloading {url} …")
    resp = requests.get(url, stream=True, timeout=600)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    dest.parent.mkdir(parents=True, exist_ok=True)

    if HAS_TQDM and total:
        bar = _tqdm(total=total, unit="B", unit_scale=True, desc=dest.name)
    else:
        bar = None
        downloaded = 0

    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)
            if bar is not None:
                bar.update(len(chunk))
            else:
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded / 1e6:.0f} / {total / 1e6:.0f} MB  ({pct:.0f}%)",
                          end="", flush=True)

    if bar is not None:
        bar.close()
    else:
        print()

    size_mb = dest.stat().st_size / 1e6
    print(f"Saved {dest.name} ({size_mb:.0f} MB)")


def filter_pbf(pbf_path: Path, bbox: tuple, highway_tags: set) -> list:
    """Extract trail ways from a PBF file using pyosmium.

    Returns a list of elements in Overpass-compatible format
    (each has type, id, tags, nodes, geometry).
    """
    try:
        import osmium
    except ImportError:
        print("osmium is not installed. Run: pip install osmium", file=sys.stderr)
        sys.exit(1)

    south, west, north, east = bbox

    class TrailHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.elements = []

        def way(self, w):
            if w.tags.get("highway", "") not in highway_tags:
                return

            node_ids = []
            geometry = []
            for n in w.nodes:
                if not n.location.valid():
                    continue
                lat, lon = n.location.lat, n.location.lon
                node_ids.append(n.ref)
                geometry.append({"lat": lat, "lon": lon})

            if len(node_ids) < 2:
                return

            # Include the way if any node falls inside the bounding box.
            if not any(south <= g["lat"] <= north and west <= g["lon"] <= east
                       for g in geometry):
                return

            self.elements.append({
                "type": "way",
                "id": w.id,
                "tags": dict(w.tags),
                "nodes": node_ids,
                "geometry": geometry,
            })

    handler = TrailHandler()
    print(f"Filtering {pbf_path.name} for trail ways in bounding box …")
    print("  (This reads the full state extract — may take a minute.)")
    handler.apply_file(str(pbf_path), locations=True)
    return handler.elements


def fetch_geofabrik() -> None:
    if not PBF_PATH.exists():
        download_pbf(GEOFABRIK_URL, PBF_PATH)
    else:
        size_mb = PBF_PATH.stat().st_size / 1e6
        print(f"Found existing {PBF_PATH.name} ({size_mb:.0f} MB) — skipping download.")
        print("  Delete it and re-run to fetch a fresh copy.")

    elements = filter_pbf(PBF_PATH, BBOX, HIGHWAY_TAGS)

    node_ids: set[int] = set()
    for w in elements:
        node_ids.update(w["nodes"])

    OUTPUT_PATH.write_text(json.dumps({"elements": elements}))

    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"\nSummary:")
    print(f"  Ways:  {len(elements):,}")
    print(f"  Nodes: {len(node_ids):,}")
    print(f"  File:  {OUTPUT_PATH}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Overpass source
# ---------------------------------------------------------------------------

def fetch_with_retry(query: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Attempt {attempt}/{MAX_RETRIES} …", end=" ", flush=True)
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=180,
            )
            if response.status_code in (429, 504):
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                print(f"HTTP {response.status_code}. Waiting {wait}s before retry …")
                time.sleep(wait)
                continue
            response.raise_for_status()
            print("OK")
            return response.json()
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                print(f"\nFailed after {MAX_RETRIES} attempts: {exc}", file=sys.stderr)
                sys.exit(1)
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            print(f"Error: {exc}. Waiting {wait}s before retry …")
            time.sleep(wait)

    print("All retries exhausted.", file=sys.stderr)
    sys.exit(1)


def fetch_overpass() -> None:
    print(f"Querying Overpass API (bbox {BBOX}) …")
    data = fetch_with_retry(OVERPASS_QUERY)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data))

    elements = data.get("elements", [])
    ways = [e for e in elements if e["type"] == "way"]
    node_ids: set[int] = set()
    for way in ways:
        node_ids.update(way.get("nodes", []))

    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"\nSummary:")
    print(f"  Ways:  {len(ways):,}")
    print(f"  Nodes: {len(node_ids):,}")
    print(f"  File:  {OUTPUT_PATH}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch OSM trail data for the Larimer County corridor."
    )
    parser.add_argument(
        "--source",
        choices=["geofabrik", "overpass"],
        default="geofabrik",
        help="Data source: geofabrik (default, reliable) or overpass (live query)",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.source == "geofabrik":
        fetch_geofabrik()
    else:
        fetch_overpass()


if __name__ == "__main__":
    main()
