---
name: trail-route-planner
description: Plan running/hiking/cycling routes for a trip or location — pick real routes, build navigable GPX from OSM trail geometry, audit them for terrain that is too hard to run, and publish a day-by-day page with maps, elevation profiles, GPX downloads and photos. Use when asked for routes/runs/hikes near a place or hotel, a running plan for a trip, "where can I run", GPX files, or a route guide.
---

# Trail route planner

Turn "find me runs near the hotel" into a verified, navigable plan.

The value is **not** the route names — an LLM can list those, and half of them are
wrong. The value is that every track is built from real trail geometry, measured,
and audited against terrain grades. Do not skip the verification steps; they are
the entire point.

## Ask first (these change everything)

1. **Level** — typical distance and comfortable climb. "10 km" and "25 km" produce
   different plans.
2. **Timing** — early morning before family? That kills anything gated behind a
   cable car (usually opens 09:00) or a toll road, no matter how beautiful.
3. **Radius** — how far will they drive? Then ask the trade-off explicitly:
   *further-but-beautiful vs. close-but-dull?* People almost always want the
   former, and the answer unlocks the best routes.
4. **Terrain tolerance** — is a short scrambly section acceptable, or must it be
   runnable throughout? Quantify it later (see the audit).

## Workflow

### 1. Research — in parallel, per area
Spawn subagents (one per base/region). Demand from each:
- **Ordered waypoint lists with lat,lon** — not just route names. You cannot build
  a GPX from a name.
- Distance, gain, surface, and honest runnability
- **Popularity evidence**: Komoot recommendation counts and ratings, Strava
  segments, race courses, "top trail run" mentions. Weight by this.
- **Verified drive times** (OSRM), tolls (cost *and* opening hour), lift hours.
- Explicit rejections with reasons.

Push them to check OSM `sac_scale` via Overpass, and to say "I could not verify"
rather than guess. Tell them not to invent coordinates.

**Local waymarked running networks are the jackpot.** Tourism boards often publish
numbered, signposted `Laufrunden` / running loops that no listicle mentions.
Search in the local language ("Laufstrecken <place>", "Trailrunning <place>").

### 2. Build GPX — never hand-draw
`scripts/build_gpx.py routes.json gpx/` routes the waypoints through **BRouter**,
which follows actual OSM ways and returns elevation.

**Cross-check every measured distance against the published figure.** They should
agree within ~10%. A mismatch means someone is wrong — find out who before shipping.

### 3. Audit the terrain — this is the step that saves you
`scripts/audit_sac.py gpx/*.gpx` reports **how many metres** of each track lie on
T3+ terrain.

Report it in metres, not yes/no, and let the human judge:
- **T1/T2** — runnable.
- **T3** — walk it. A few hundred metres is fine; 20% of the route is a different route.
- **T4+** — reject outright.

This routinely contradicts the research. Real results from one trip: a "perfect,
fully runnable T2" classic loop was 636 m of T3; a tempting summit ridge was 1,780 m
of T3 (20%); and a variant advertised as a normal tour was **T5 — grade I–II
climbing**. The stats on the trap routes look *ideal*, which is exactly why they
need measuring.

### 4. Photos
Wikimedia Commons only, with real licence + author + File: page. Verify each image
actually depicts the place — **skip a photo rather than mislabel one**, and caption
generically when only a regional fallback exists. Record credits in a JSON and
render them in the footer.

### 5. Publish
A day-per-route page. Per route: photo, distance / gain / time / drive metrics,
description, **interactive Leaflet map + inline SVG elevation profile**, GPX
download, source link.

- Give **every day a relaxed fallback** ("if the legs said no") with its own GPX —
  people get tired, and a plan with no bail-out gets abandoned.
- Keep a **route bank** of extras and a **"what we rejected and why"** table. The
  rejections have real value: they stop someone burning a morning on a route you
  already disproved.
- Lazy-init maps with IntersectionObserver; 20+ Leaflet maps on load is painful.

## Traps that will bite you

- **lat/lon order.** BRouter writes `lon` before `lat`; most other GPX writes `lat`
  first. Swapping them inflates east–west distance by ~1/cos(lat) — about **+25%**
  at Alpine latitudes. It produces plausible-looking numbers. The tell is elevations
  that don't match the terrain. *I shipped this bug and briefly "discovered" a 25%
  error in correct data.*
- **Leaflet `bringToBack()`** on a freshly-added polyline throws
  `Cannot read properties of undefined (reading 'parentNode')`, silently aborting
  the rest of your init. Draw the white casing line *first*, coloured line second.
- **Overpass** returns HTTP 406 without a `User-Agent`, and rate-limits hard —
  sleep ~20 s between queries, never parallelise.
- **Elevation gain** from DEM sampling over-reads. Prefer the official published
  ascent; use measured distance (which is reliable) to sanity-check.
- **Drive times are longer than they look.** Mountain roads are slow. Compute with
  OSRM; do not trust straight-line distance.
- **Cable cars and toll roads have opening hours** (often 08:00/09:00). A stunning
  route you cannot start at 06:00 is useless to an early-morning runner. A
  door-start route is worth a lot — say so.

## Non-negotiables

- Never invent coordinates or a trail. If unverified, say so on the page.
- Never present a hand-drawn line as a GPS track.
- State honestly where the plan is uncertain (unconfirmed toll hours, a hotel whose
  exact coordinates aren't in OSM, a photo that's a regional stand-in). Trust is the
  deliverable; a confidently wrong route sends someone onto a mountain.
