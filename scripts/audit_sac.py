#!/usr/bin/env python3
"""Audit GPX tracks against OpenStreetMap sac_scale — how many METRES of each
track sit on terrain too hard to run.

This is the step that catches what research gets wrong. Tour sites, guidebooks
and LLM research routinely call a route "runnable / T2" when OSM tags part of it
T3 or worse. Measuring it in metres — not "does it touch T3 yes/no" — is what
lets a human make the call: 600 m of T3 you walk; 1,800 m is a different route.

Usage:  audit_sac.py gpx/*.gpx

SAC scale:
  T1 hiking                     — runnable
  T2 mountain_hiking            — runnable, you'll walk the steep bits
  T3 demanding_mountain_hiking  — WALK. sure-footedness, possible exposure
  T4 alpine_hiking              — reject
  T5 demanding_alpine_hiking    — reject (grade I-II climbing)
  T6 difficult_alpine_hiking    — reject

Real finds from the Carinthia run: the "classic" Rosennock descent = 636 m of T3
(acceptable), a tempting Kornock ridge = 1,780 m of T3 (not a run), and the
Rosennock "3-peaks" variant = T5 scrambling while advertised as a normal tour.
"""
import re, math, json, sys, time, os
import urllib.request, urllib.parse

HARD = {"demanding_mountain_hiking": "T3", "alpine_hiking": "T4",
        "demanding_alpine_hiking": "T5", "difficult_alpine_hiking": "T6"}
NEAR = 20   # metres: how close a track point must be to count as "on" that way


def read(f):
    t = open(f).read()
    m = re.findall(r'<trkpt lon="([-\d.]+)" lat="([-\d.]+)"', t)          # BRouter
    if m:
        return [(float(la), float(lo)) for lo, la in m]
    m = re.findall(r'<trkpt lat="([-\d.]+)" lon="([-\d.]+)"', t)          # lat-first
    return [(float(la), float(lo)) for la, lo in m]


def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    x = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 6371000 * 2 * math.asin(math.sqrt(x))


def overpass(s, w, n, e):
    q = f'[out:json][timeout:90];way["sac_scale"]({s},{w},{n},{e});out tags geom;'
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": q}).encode(),
        headers={"User-Agent": "trail-route-planner/1.0"})   # Overpass 406s without a UA
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.loads(r.read())
        except Exception:
            if i == 4:
                raise
            time.sleep(15)          # Overpass rate-limits hard; be patient, not parallel


def audit(f):
    pts = read(f)
    la = [p[0] for p in pts]; lo = [p[1] for p in pts]
    d = overpass(min(la) - .004, min(lo) - .004, max(la) + .004, max(lo) + .004)
    hard = [(HARD[e["tags"]["sac_scale"]], [(p["lat"], p["lon"]) for p in e["geometry"]])
            for e in d["elements"] if e["tags"].get("sac_scale") in HARD]
    marks = []
    for tp in pts:
        lab = None
        for grade, geom in hard:
            if any(hav(tp, gp) < NEAR for gp in geom):
                lab = grade; break
        marks.append(lab)
    tot, by = 0.0, {}
    for i in range(len(pts) - 1):
        if marks[i] and marks[i + 1]:                 # both ends on it => really on it
            seg = hav(pts[i], pts[i + 1])
            tot += seg
            by[marks[i]] = by.get(marks[i], 0) + seg
    total = sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return tot, total, by


if __name__ == "__main__":
    for f in sys.argv[1:]:
        try:
            tot, total, by = audit(f)
        except Exception as ex:
            print(f"{os.path.basename(f):32s} ERROR {ex}"); continue
        name = os.path.basename(f)[:-4]
        if tot < 15:
            print(f"{name:32s} clean (T1/T2 only)  [{total/1000:.1f} km]")
        else:
            parts = " ".join(f"{g}:{int(m)}m" for g, m in sorted(by.items()))
            worst = max(by)
            flag = "REJECT" if worst >= "T4" else "walk it"
            print(f"{name:32s} {int(tot)} m hard of {int(total)} m "
                  f"({100*tot/total:.1f}%)  {parts}  -> {flag}")
        time.sleep(20)              # stay under Overpass rate limits
