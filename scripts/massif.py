#!/usr/bin/env python3
"""The Mornati Massif: public repos drawn as a topographic hiking map.

Each repo is a summit. Height is stars (1 star = 10 m), horizontal position
is the creation date, so the map is also a timeline. A dashed GR-style trail
links the summits in creation order and a runner walks it. Writes dark and
light variants. Standard library only.

Usage:
  GITHUB_TOKEN=... python3 scripts/massif.py [--user mmornati] [--out assets/massif]
"""
import argparse
import math
import os
from datetime import date, datetime
from html import escape

from gh import fetch_repos
from trail import FONT

THEMES = {
    "dark": {"bg": "#0b1310", "grid": "#1a2820", "contour": "#c8873a", "summit_fill": "#ffb547",
             "fg": "#e6edf3", "muted": "#8b949e", "height": "#ffb547", "trail": "#f85149",
             "halo": "#0b1310", "runner": "#ffb547"},
    "light": {"bg": "#fbfcf8", "grid": "#e3e8df", "contour": "#a0522d", "summit_fill": "#a0522d",
              "fg": "#1f2328", "muted": "#59636e", "height": "#a0522d", "trail": "#cf222e",
              "halo": "#fbfcf8", "runner": "#e8590c"},
}

W, H = 960, 440
L, R, TOP, AXIS = 60, 60, 70, 404
LANES = [112, 172, 232, 292, 352]   # summit rows, so labels never collide
MIN_GAP = 175                       # min distance between summits sharing a row
SUMMITS = 12                        # most-starred repos that make it onto the map
METRES_PER_STAR = 10


def year_frac(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    return d.year + (d.timetuple().tm_yday - 1) / 365


def place(peaks, x_of):
    """Assign each summit a row: prefer a stable row from its name, else the first free one."""
    rows = {i: [] for i in range(len(LANES))}
    placed = []
    for p in sorted(peaks, key=lambda p: -p["stargazerCount"]):
        x = x_of(year_frac(p["createdAt"]))
        start = sum(map(ord, p["name"])) % len(LANES)
        for k in range(len(LANES)):
            row = (start + k) % len(LANES)
            if all(abs(x - ox) >= MIN_GAP for ox in rows[row]):
                rows[row].append(x)
                placed.append((p, x, LANES[row]))
                break
    return placed


def contour(cx, cy, rad, seed):
    d = ""
    for a in range(37):
        t = a / 36 * math.tau
        w = 1 + 0.12 * math.sin(t * 3 + seed) + 0.08 * math.cos(t * 5 + seed * 2)
        x, y = cx + math.cos(t) * rad * w * 1.25, cy + math.sin(t) * rad * w * 0.78
        d += f"{'L' if a else 'M'}{x:.1f},{y:.1f}"
    return d + "Z"


def render(repos, theme):
    c = THEMES[theme]
    public = [r for r in repos if not r["isPrivate"] and r["stargazerCount"] > 0]
    peaks = sorted(public, key=lambda r: -r["stargazerCount"])[:SUMMITS]
    first = math.floor(min(year_frac(r["createdAt"]) for r in public))
    last = date.today().year + 1
    x_of = lambda y: L + (y - first) / (last - first) * (W - L - R)
    placed = place(peaks, x_of)
    total_m = sum(p["stargazerCount"] for p, _, _ in placed) * METRES_PER_STAR

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="t d" font-family="{FONT}">')
    a('<title id="t">The Mornati Massif</title>')
    a('<desc id="d">Topographic map of public repositories. Summits: '
      + escape(", ".join(f'{p["name"]} {p["stargazerCount"] * METRES_PER_STAR} m' for p, _, _ in placed)) + '</desc>')
    a(f'<defs><clipPath id="frame"><rect width="{W}" height="{H}" rx="12"/></clipPath></defs>')
    a(f'<style>.lbl{{paint-order:stroke;stroke:{c["halo"]};stroke-width:4px;stroke-linejoin:round}}</style>')
    a('<g clip-path="url(#frame)">')
    a(f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>')

    # Map grid: one column per year, like the kilometre grid on a hiking map.
    for y in range(first, last + 1):
        x = x_of(y)
        a(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{TOP - 10}" y2="{AXIS - 14}" stroke="{c["grid"]}"/>')
    for y in range(TOP + 20, AXIS - 14, 60):
        a(f'<line x1="{L}" x2="{W - R}" y1="{y}" y2="{y}" stroke="{c["grid"]}"/>')

    # Contours, biggest rings first so smaller summits draw on top.
    for p, x, y in sorted(placed, key=lambda t: -t[0]["stargazerCount"]):
        rings = max(2, round(math.sqrt(p["stargazerCount"]) * 1.1))
        seed = sum(map(ord, p["name"])) % 7
        for r in range(rings, 0, -1):
            index = r % 5 == 0
            top = r == 1
            a(f'<path d="{contour(x, y, 8 + r * 8, seed)}" fill="{c["summit_fill"] if top else "none"}" '
              f'fill-opacity="{0.12 if top else 0}" stroke="{c["contour"]}" '
              f'stroke-opacity="{0.9 if index else 0.5}" stroke-width="{1.4 if index else 0.8}"/>')

    # The trail: summits linked in creation order, with a runner on it.
    path = sorted(placed, key=lambda t: t[1])
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for _, x, y in path)
    a(f'<path id="gr" d="{d}" fill="none" stroke="{c["trail"]}" stroke-width="1.8" stroke-dasharray="7 5" opacity=".9"/>')
    a(f'<g><circle r="9" fill="{c["runner"]}" opacity=".25"/><circle r="4" fill="{c["runner"]}"/>'
      '<animateMotion dur="24s" repeatCount="indefinite" calcMode="paced">'
      '<mpath href="#gr" xlink:href="#gr" xmlns:xlink="http://www.w3.org/1999/xlink"/></animateMotion></g>')

    # Summit markers and names.
    for p, x, y in placed:
        a(f'<path d="M{x:.1f},{y - 6:.1f} l6,10 h-12z" fill="{c["fg"]}"/>')
        a(f'<text class="lbl" x="{x:.1f}" y="{y + 20:.1f}" fill="{c["fg"]}" font-size="10.5" font-weight="700" '
          f'text-anchor="middle">{escape(p["name"])}</text>')
        a(f'<text class="lbl" x="{x:.1f}" y="{y + 32:.1f}" fill="{c["height"]}" font-size="10" '
          f'text-anchor="middle">{p["stargazerCount"] * METRES_PER_STAR:,} m</text>')

    # Legend and axis.
    a(f'<text x="{L}" y="34" fill="{c["fg"]}" font-size="16" font-weight="800" letter-spacing="1">THE MORNATI MASSIF</text>')
    a(f'<text x="{L}" y="52" fill="{c["muted"]}" font-size="11">{len(placed)} summits · 1 ★ = {METRES_PER_STAR} m · '
      f'contour interval {METRES_PER_STAR} m · trail in creation order</text>')
    a(f'<g transform="translate({W - R},34)"><path d="M-6,4 l6,-22 l6,22 l-6,-6 z" fill="{c["fg"]}"/>'
      f'<text x="-16" y="0" fill="{c["muted"]}" font-size="11" text-anchor="end">N</text></g>')
    step = 2 if last - first > 10 else 1
    for y in range(first, last, step):
        a(f'<text x="{x_of(y):.1f}" y="{AXIS + 10}" fill="{c["muted"]}" font-size="10" text-anchor="middle">{y}</text>')
    a(f'<text x="{W - R - 48}" y="34" fill="{c["height"]}" font-size="14" font-weight="800" text-anchor="end">'
      f'D+ {total_m:,} m</text>')
    a('</g></svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("GITHUB_USER", "mmornati"))
    p.add_argument("--out", default="assets/massif")
    args = p.parse_args()
    repos = fetch_repos(args.user, os.environ["GITHUB_TOKEN"])
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"massif-{theme}.svg")
        with open(path, "w") as f:
            f.write(render(repos, theme))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
