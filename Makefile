all: fetch-osm build-graph add-elevation validate

fetch-osm:
	python scripts/fetch_osm.py

build-graph:
	cd backend && python -c "from trail_graph.build_graph import build_graph; \
	  build_graph('data/raw_osm.json', 'data/trail_graph.gpickle')"

add-elevation:
	python scripts/add_elevation.py

validate:
	python scripts/validate.py
