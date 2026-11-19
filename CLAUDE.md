# trail-routes

A website for a Northern Colorado trail running group (and anyone else) to build and pick routes before heading out. Planned home: a subdomain of eatrunmath.com (e.g. trails.eatrunmath.com) on an existing DigitalOcean droplet.

## Why this exists
The group knows the trails well but decides routes mid-run, and runners spread out and wait for each other at ad hoc points. The site should give everyone a set plan before leaving the parking lot, including regroup points.

## Core features
1. **Route builder (the heart of the project):** Pick a trailhead, a target distance, and a target elevation gain. The site searches the real trail network for loops and out-and-backs close to those numbers and shows a few options on a map.
2. **Saved routes:** Users can save and upload routes (GPX). Saved/favorite routes get boosted in search results.
3. **Regroup points:** Routes carry named waypoints (e.g. "wait at the Horsetooth Rock junction"). Suggest them automatically at major junctions or about every 2-3 miles; users can add or edit them. Show on the map and in a phone-friendly, printable cue sheet.
4. **Community:** Anyone can browse. Group members can add routes, upvote (one vote per person per route), and comment.
5. **Later idea:** estimate where fast and slow runners will be at each regroup point.

## Trailheads (preset start points)
- Soderberg Open Space (most common)
- Maxwell Natural Area
- Horsetooth Mountain Open Space lot
- Lory State Park, Timber trailhead
- Loveland-side lots near Coyote Ridge, connecting into Blue Sky and others

Verify exact trailhead coordinates against the map data; do not guess them.

## Coverage area
Larimer County trail corridor: Horsetooth Mountain, Soderberg, Lory State Park, Maxwell, Coyote Ridge, Blue Sky, Devil's Backbone, Reservoir Ridge and neighbors. Model it as ONE connected network, not park by park, since the group links between open spaces.

## Data plan
- **Trails:** OpenStreetMap via the Overpass API (paths/tracks tagged highway=path, track, footway within a bounding box of the corridor). Cross-check against Larimer County's open GIS trail data.
- **Graph:** Junctions are nodes; trail segments are edges with length and elevation gain/loss. Split ways at every shared node.
- **Elevation:** OSM lacks it. Sample USGS 3DEP DEM data (or a similar open DEM) along each segment, smooth it, and compute gain/loss. Gain figures will be approximate; calibrate against routes the group already knows.
- **Known weakness:** informal connector trails are often missing or mislabeled in OSM. First validation step: confirm the graph reproduces a handful of routes the group knows are real, and add manual edges where needed.
- **Raw downloads** (OSM extracts, DEM tiles) are large: keep them out of Git (.gitignore) and document how to re-fetch them with a script.

## Search approach
Start from a chosen trailhead node. Find loops and out-and-backs whose distance and gain are near the targets, avoid reusing segments (except for out-and-backs), and rank by closeness to the targets plus a boost for group-saved routes. Return the top few options with distance, gain, an elevation profile, and a map line.

## Stack (matches the sermon-archive project already on the same droplet)
- Backend: FastAPI (Python)
- Frontend: React + Vite, with a Leaflet or MapLibre map on OpenStreetMap tiles
- Database: a separate SQLite file for this app (not shared with the sermon archive). Revisit if write load grows.
- Deployment: Ubuntu droplet, Nginx reverse proxy, systemd service. Push to GitHub, droplet pulls and restarts.
- Keep this app fully separate from the sermon archive: own repo, own database, own service, own subdomain.

## Accounts
Assumption (change if needed): public browse is read-only; posting, voting, and commenting require an invite-only account for the group. Consider opening sign-up later with moderation. Anything open to the public needs rate limits and spam protection.

## Build order
1. Fetch trail data for the corridor, build the graph, and validate it against known routes. Do this first: the whole idea depends on data quality.
2. Route finder (distance + gain) with a map.
3. Saved routes, regroup points, GPX import/export, and the cue sheet.
4. Accounts, voting, and comments.
5. Deploy to the droplet.

## Working notes
- The owner (John) runs trails around Fort Collins and is comfortable with GitHub Desktop; explain Git steps plainly when they come up.
- Big files stay out of Git.
- Ask before changing anything on the droplet that could affect the existing sermon site.

## Open questions
- Exact subdomain (trails.eatrunmath.com?).
- Database confirmation: the sermon app's database type (Postgres vs SQLite) is unconfirmed; this app defaults to SQLite.
- Which trails or connectors the group wants prioritized for validation.
- Whether to support point-to-point routes with a shuttle (the group mostly runs loops from a trailhead).
