#!/usr/bin/env python3
"""Build real GPX tracks by routing waypoints through BRouter (OSM path geometry).

Never hand-draw a track between waypoints — a straight line between two points is
not a trail. BRouter snaps to actual OSM ways and returns elevation, so the result
is a track a watch can actually navigate.

Usage:  build_gpx.py routes.json [outdir]

routes.json:
  [{"id": "kornock", "name": "Kornock Runde",
    "waypoints": [[lat,lon], [lat,lon], ...],      # ORDERED, traces the route
    "profile": "hiking-beta"}]                      # optional

Profiles: hiking-beta (trails), trekking, fastbike, shortest.

Prints measured distance / ascent per route. ALWAYS compare these against the
published figures from the tour site. If they disagree by more than ~10%, one of
you is wrong — find out which before shipping.
"""
import json, sys, time, math, os, re
import urllib.request, urllib.parse

BR = "https://brouter.de/brouter"


def route(wps, profile="hiking-beta"):
    lonlats = "|".join(f"{lon},{lat}" for lat, lon in wps)
    url = f"{BR}?{urllib.parse.urlencode({'lonlats': lonlats, 'profile': profile, 'alternativeidx': 0, 'format': 'gpx'})}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return r.read().decode()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(4 * (attempt + 1))


def parse(gpx):
    """BRouter writes lon BEFORE lat. Getting this backwards silently inflates
    east-west distance by ~1/cos(lat) — about +25% at Alpine latitudes. It looks
    plausible, which is what makes it dangerous. Elevations that don't match the
    terrain are the tell."""
    return [(float(la), float(lo), float(el))
            for lo, la, el in re.findall(
                r'<trkpt lon="([-\d.]+)" lat="([-\d.]+)"><ele>([-\d.]+)</ele>', gpx)]


def stats(pts):
    d = 0.0
    for (la1, lo1, _), (la2, lo2, _) in zip(pts, pts[1:]):
        p1, p2 = math.radians(la1), math.radians(la2)
        dp, dl = p2 - p1, math.radians(lo2 - lo1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        d += 6371000 * 2 * math.asin(math.sqrt(a))
    asc, ref = 0.0, pts[0][2]          # 3 m hysteresis kills DEM noise
    for _, _, e in pts:
        if e > ref + 3:
            asc += e - ref; ref = e
        elif e < ref:
            ref = e
    eles = [e for _, _, e in pts]
    return d / 1000, asc, min(eles), max(eles)


def main():
    routes = json.load(open(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else "gpx"
    os.makedirs(out, exist_ok=True)
    summary = []
    for r in routes:
        prof = r.get("profile", "hiking-beta")
        gpx = route(r["waypoints"], prof)
        pts = parse(gpx)
        if len(pts) < 5:
            print(f"!! {r['id']}: routing failed ({len(pts)} pts) — check waypoint "
                  f"order and that they sit near real paths", file=sys.stderr)
            continue
        km, asc, lo, hi = stats(pts)
        gpx = re.sub(r"<name>brouter_[^<]*</name>", f"<name>{r['name']}</name>", gpx)
        open(f"{out}/{r['id']}.gpx", "w").write(gpx)
        summary.append({"id": r["id"], "km": round(km, 1), "ascent": round(asc),
                        "min_ele": round(lo), "max_ele": round(hi)})
        print(f"{r['id']:30s} {km:5.1f} km  +{asc:4.0f} m  ({lo:.0f}-{hi:.0f} m)")
        time.sleep(1)
    json.dump(summary, open(f"{out}/_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
