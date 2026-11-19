"""FastAPI application entry point for trail-routes.

Start with:
    cd backend
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trail_graph.build_graph import load_graph
from trail_graph import trailheads as th_module

GRAPH_PATH = Path(__file__).parent / "data" / "trail_graph.gpickle"

# Graph is loaded once at startup and shared across all requests.
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Loading graph from {GRAPH_PATH} …", flush=True)
    G = load_graph(GRAPH_PATH)
    print(f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    th_module.snap_to_graph(G)
    for th in th_module.TRAILHEADS:
        print(f"  {th.id}: node {th.node_id} snap={th.snap_m:.0f}m")
    _state["G"] = G
    yield
    _state.clear()


app = FastAPI(title="Trail Routes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers after app is created.
from routers.routes import router  # noqa: E402
app.include_router(router)


def get_graph():
    """Dependency / helper to retrieve the loaded graph."""
    return _state["G"]
