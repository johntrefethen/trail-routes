"""API endpoints for trail route search."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trail_graph import trailheads as th_module
from trail_graph.search import search_routes, RouteResult

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TrailheadOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    node_lat: float
    node_lon: float
    snap_m: float


class RouteOut(BaseModel):
    rank: int
    route_type: str
    distance_km: float
    gain_m: float
    loss_m: float
    trail_names: list[str]
    coords: list[list[float]]          # [[lat, lon], ...]
    elevation_profile: list[list[float]]  # [[dist_m, gain_m], ...]
    score: float


class SearchResponse(BaseModel):
    trailhead: TrailheadOut
    routes: list[RouteOut]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/trailheads", response_model=list[TrailheadOut])
def get_trailheads():
    """List all preset trailheads."""
    return [
        TrailheadOut(
            id=th.id,
            name=th.name,
            lat=th.lat,
            lon=th.lon,
            node_lat=th.node_lat,
            node_lon=th.node_lon,
            snap_m=th.snap_m,
        )
        for th in th_module.TRAILHEADS
    ]


@router.get("/routes/search", response_model=SearchResponse)
def search(
    trailhead_id: Annotated[str, Query(description="Trailhead ID from /api/trailheads")],
    target_dist_km: Annotated[float, Query(gt=0, le=100, description="Target distance in km")],
    target_gain_m: Annotated[float | None, Query(ge=0, le=5000, description="Target elevation gain in metres (optional)")] = None,
    route_type: Annotated[str, Query(description='"loop" or "out-and-back"')] = "loop",
    max_results: Annotated[int, Query(ge=1, le=10)] = 5,
):
    """Search for routes matching the given distance and gain targets."""
    # Import here to avoid circular import at module load time.
    from main import get_graph
    G = get_graph()

    th = th_module.get(trailhead_id)
    if th is None:
        raise HTTPException(status_code=404, detail=f"Unknown trailhead '{trailhead_id}'")
    if th.node_id == 0:
        raise HTTPException(status_code=503, detail="Graph not yet loaded")
    if route_type not in ("loop", "out-and-back"):
        raise HTTPException(status_code=400, detail='route_type must be "loop" or "out-and-back"')

    target_dist_m = target_dist_km * 1000.0
    raw: list[RouteResult] = search_routes(
        G,
        start_node=th.node_id,
        target_dist_m=target_dist_m,
        target_gain_m=target_gain_m,
        route_type=route_type,
        max_results=max_results,
    )

    routes_out = [
        RouteOut(
            rank=i + 1,
            route_type=r.route_type,
            distance_km=round(r.distance_m / 1000, 2),
            gain_m=round(r.gain_m),
            loss_m=round(r.loss_m),
            trail_names=r.trail_names,
            coords=[[lat, lon] for lat, lon in r.coords],
            elevation_profile=[[d, g] for d, g in r.elevation_profile],
            score=round(r.score, 4),
        )
        for i, r in enumerate(raw)
    ]

    return SearchResponse(
        trailhead=TrailheadOut(
            id=th.id,
            name=th.name,
            lat=th.lat,
            lon=th.lon,
            node_lat=th.node_lat,
            node_lon=th.node_lon,
            snap_m=th.snap_m,
        ),
        routes=routes_out,
    )
