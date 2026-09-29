#!/usr/bin/env python3
"""Commit Ultra-Trail: draw the last year of GitHub contributions as a trail
elevation profile, with blog posts as aid stations and an animated runner.

Writes one SVG per theme (dark/light) so the README can switch them with
<picture> + prefers-color-scheme. Standard library only.

Usage:
  GITHUB_TOKEN=... python3 scripts/trail.py [--user mmornati] [--out assets/trail]
  python3 scripts/trail.py --data fixture.json   # offline, raw GraphQL response
"""
import argparse
import json
import math
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import escape

GRAPHQL = "https://api.github.com/graphql"
QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
FEED = "https://blog.mornati.net/rss.xml"
FONT = "'JetBrains Mono','SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "dark": {
        "bg": "#0d1117", "sky_top": "#010409", "sky_bottom": "#0d1530",
        "fg": "#e6edf3", "muted": "#8b949e", "grid": "#21262d",
        "ridge": "#ffb547", "ridge_fill": "#ffb547", "range": "#6c7cff",
        "aid": "#6c7cff", "flag": "#f85149", "runner": "#ffb547", "stars": True,
    },
    "light": {
        "bg": "#ffffff", "sky_top": "#dce8ff", "sky_bottom": "#ffffff",
        "fg": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0",
        "ridge": "#3643ba", "ridge_fill": "#3643ba", "range": "#3643ba",
        "aid": "#e8590c", "flag": "#cf222e", "runner": "#e8590c", "stars": False,
    },
}

W, H = 960, 400
L, R, T = 40, 28, 92          # chart margins
CHART_BOTTOM = 280            # baseline of the ridge area
STATS_Y = 352                 # stats strip baseline
LABELLED = 5                  # aid stations that get a caption, newest first, spread out
LABEL_SPACING = 150           # min horizontal distance between captioned stations


def fetch_calendar(user, token):
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "commit-ultra-trail"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_posts(url):
    """Return [(date, title)] from an RSS feed; empty list if it is unreachable."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "commit-ultra-trail"})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:  # the trail still renders without aid stations
        print(f"warning: feed unavailable ({e})")
        return []
    posts = []
    for item in root.iter("item"):
        title, pub = item.findtext("title"), item.findtext("pubDate")
        if title and pub:
            posts.append((parsedate_to_datetime(pub).date(), title.strip()))
    return posts


def short(title, limit=20):
    """Shorten a post title to its leading phrase, cut on a word boundary."""
    head = re.split(r"[:,(]| - | — ", title)[0].strip()
    if len(head) <= limit:
        return head
    cut = head[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def streaks(days):
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    tail = days[:-1] if days and not days[-1][1] else days  # today may still be empty
    current = 0
    for _, n in reversed(tail):
        if not n:
            break
        current += 1
    return longest, current


def ridge_path(pts):
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        mx = (x0 + x1) / 2
        d += f" C{mx:.1f},{y0:.1f} {mx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    return d


def place_labels(stations, reserved, char=6.2):
    """Greedy two-row placement so aid-station labels never overlap each other
    or the reserved (start, end) spans of the START/FINISH captions on row 0."""
    taken = [list(reserved), []]
    placed = []
    for x, label in stations:  # newest first, so the latest post always gets a caption
        half = len(label) * char / 2 + 10
        x = min(max(x, L + half), W - R - half)  # keep the caption inside the frame
        span = (x - half, x + half)
        for row in (0, 1):
            if all(span[1] < a or span[0] > b for a, b in taken[row]):
                taken[row].append(span)
                placed.append((x, label, row))
                break
    return placed


def render(weeks, posts, theme_name):
    c = THEMES[theme_name]
    week_totals = [sum(n for _, n in w) for w in weeks]
    week_starts = [w[0][0] for w in weeks]
    days = [d for w in weeks for d in w]
    total = sum(week_totals)
    n = len(week_totals)

    iw, ih = W - L - R, CHART_BOTTOM - T
    peak = max(week_totals) or 1
    # 3-week smoothing reads as terrain; sqrt keeps quiet weeks visible as foothills.
    sm = [(week_totals[max(i - 1, 0)] + 2 * v + week_totals[min(i + 1, n - 1)]) / 4
          for i, v in enumerate(week_totals)]
    top = math.sqrt(max(sm) or 1)
    pts = [(L + i * iw / (n - 1), CHART_BOTTOM - math.sqrt(v) / top * ih * 0.92)
           for i, v in enumerate(sm)]
    ridge = ridge_path(pts)
    area = ridge + f" L{L + iw},{CHART_BOTTOM} L{L},{CHART_BOTTOM} Z"

    summit_i = week_totals.index(max(week_totals))
    sx, sy = pts[summit_i]
    summit_date = week_starts[summit_i]

    # Aid stations: one per week that had blog posts, labelled with the latest post.
    first = date.fromisoformat(week_starts[0])
    by_week = {}
    for d, title in posts:
        i = (d - first).days // 7
        if 0 <= i < n:
            by_week.setdefault(i, []).append((d, title))
    recent = []
    for i in sorted(by_week, reverse=True):
        if len(recent) < LABELLED and all(abs(pts[i][0] - pts[j][0]) >= LABEL_SPACING for j in recent):
            recent.append(i)
    stations = []
    for i in recent:
        items = sorted(by_week[i])
        label = short(items[-1][1]) + (f" +{len(items) - 1}" if len(items) > 1 else "")
        stations.append((pts[i][0], label))
    start_label = f"START · {datetime.fromisoformat(week_starts[0]):%b %Y}"
    finish_label = "FINISH · TODAY"
    reserved = [(L, L + len(start_label) * 6.2 + 12), (L + iw - len(finish_label) * 6.2 - 12, L + iw)]
    labels = place_labels(stations, reserved)

    active = sum(1 for _, v in days if v)
    longest, current = streaks(days)

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="t d" font-family="{FONT}">')
    a(f'<title id="t">Commit Ultra-Trail</title>')
    a(f'<desc id="d">{total} GitHub contributions over {n} weeks drawn as a trail elevation '
      f'profile. Summit: {max(week_totals)} contributions in the week of {summit_date}.</desc>')
    a('<defs>'
      f'<linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{c["sky_top"]}"/>'
      f'<stop offset="1" stop-color="{c["sky_bottom"]}"/></linearGradient>'
      f'<linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{c["ridge_fill"]}" stop-opacity=".38"/>'
      f'<stop offset="1" stop-color="{c["ridge_fill"]}" stop-opacity="0"/></linearGradient>'
      f'<radialGradient id="glow"><stop offset="0" stop-color="{c["runner"]}" stop-opacity=".6"/>'
      f'<stop offset="1" stop-color="{c["runner"]}" stop-opacity="0"/></radialGradient>'
      f'<linearGradient id="beam"><stop offset="0" stop-color="{c["runner"]}" stop-opacity=".7"/>'
      f'<stop offset="1" stop-color="{c["runner"]}" stop-opacity="0"/></linearGradient>'
      f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="12"/></clipPath>'
      '</defs>')
    a('<g clip-path="url(#frame)">')
    a(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')

    # Sky: twinkling stars at night, a sun by day.
    if c["stars"]:
        for i in range(46):
            x, y = (i * 97 + 13) % W, (i * 53) % 150 + 8
            r = 1.4 if i % 5 == 0 else 0.8
            a(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c["fg"]}" opacity=".5">'
              f'<animate attributeName="opacity" values=".15;.8;.15" dur="{3 + i % 4}s" '
              f'begin="{(i % 7) * 0.4:.1f}s" repeatCount="indefinite"/></circle>')
    # Keep the moon/sun away from the summit flag.
    mx = W * 0.56 if sx > W * 0.7 else W * 0.78 if sx < W * 0.5 else W * 0.3
    if c["stars"]:
        a(f'<circle cx="{mx:.0f}" cy="44" r="13" fill="{c["fg"]}" opacity=".85"/>'
          f'<circle cx="{mx + 6:.0f}" cy="39" r="12" fill="{c["sky_top"]}"/>')
    else:
        a(f'<circle cx="{mx:.0f}" cy="46" r="18" fill="#ffc53d" opacity=".9"/>')

    # Distant ranges for depth.
    for k in range(3):
        d = f"M{L - 40},{CHART_BOTTOM}"
        for x in range(0, iw + 81, 40):
            y = CHART_BOTTOM - 36 - k * 18 - abs(math.sin(x / (90 + k * 37) + k)) * (58 - k * 12)
            d += f" L{L - 40 + x},{y:.1f}"
        a(f'<path d="{d} L{W},{CHART_BOTTOM} Z" fill="{c["range"]}" opacity="{0.05 + k * 0.03:.2f}"/>')

    for f in (0.25, 0.5, 0.75, 1):
        y = CHART_BOTTOM - f * ih * 0.92
        a(f'<line x1="{L}" x2="{L + iw}" y1="{y:.1f}" y2="{y:.1f}" stroke="{c["grid"]}" stroke-dasharray="2 5"/>')

    # Header.
    a(f'<text x="{L}" y="34" fill="{c["fg"]}" font-size="16" font-weight="800" letter-spacing="1">'
      f'MORNATI COMMIT ULTRA</text>')
    a(f'<text x="{L}" y="52" fill="{c["muted"]}" font-size="11">{n} weeks · every contribution is a metre of climbing</text>')
    a(f'<text x="{W - R}" y="34" fill="{c["ridge"]}" font-size="16" font-weight="800" text-anchor="end">'
      f'D+ {total:,} m</text>')

    # Terrain.
    a(f'<path d="{area}" fill="url(#fill)"/>')
    a(f'<path id="ridge" d="{ridge}" fill="none" stroke="{c["ridge"]}" stroke-width="2.5" '
      f'stroke-linejoin="round" stroke-linecap="round"/>')
    a(f'<line x1="{L}" x2="{L + iw}" y1="{CHART_BOTTOM}" y2="{CHART_BOTTOM}" stroke="{c["grid"]}"/>')

    # Aid stations.
    for i in by_week:
        x, y = pts[i]
        if i in recent:
            a(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y:.1f}" y2="{CHART_BOTTOM}" stroke="{c["muted"]}" '
              f'stroke-dasharray="2 3" opacity=".7"/>')
        s = 4 if i in recent else 3
        a(f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s}" height="{2 * s}" fill="{c["bg"]}" '
          f'stroke="{c["aid"]}" stroke-width="{2 if i in recent else 1.5}" transform="rotate(45 {x:.1f} {y:.1f})"/>')
    for x, label, row in labels:
        y = CHART_BOTTOM + 16 + row * 14
        a(f'<text x="{x:.1f}" y="{y}" fill="{c["muted"]}" font-size="10" text-anchor="middle">'
          f'<tspan fill="{c["aid"]}">◆</tspan> {escape(label)}</text>')

    # Summit flag.
    a(f'<line x1="{sx:.1f}" x2="{sx:.1f}" y1="{sy:.1f}" y2="{sy - 24:.1f}" stroke="{c["fg"]}" stroke-width="1.5"/>'
      f'<path d="M{sx:.1f},{sy - 24:.1f} l15,5 l-15,5 z" fill="{c["flag"]}"/>')
    anchor = "end" if sx > W - 180 else "start" if sx < 180 else "middle"
    a(f'<text x="{sx:.1f}" y="{sy - 30:.1f}" fill="{c["fg"]}" font-size="11" font-weight="600" '
      f'text-anchor="{anchor}">SUMMIT · {max(week_totals)} · {datetime.fromisoformat(summit_date):%b %d}</text>')

    # Start and finish.
    a(f'<text x="{L}" y="{CHART_BOTTOM + 16}" fill="{c["muted"]}" font-size="10">{start_label}</text>')
    fx = L + iw
    a(f'<text x="{fx}" y="{CHART_BOTTOM + 16}" fill="{c["muted"]}" font-size="10" text-anchor="end">{finish_label}</text>')
    for j in range(4):  # checkered finish post
        for k in range(2):
            fill = c["fg"] if (j + k) % 2 == 0 else c["bg"]
            a(f'<rect x="{fx - 2 + k * 5}" y="{CHART_BOTTOM - 36 + j * 5}" width="5" height="5" fill="{fill}"/>')
    a(f'<line x1="{fx - 2}" x2="{fx - 2}" y1="{CHART_BOTTOM - 36}" y2="{CHART_BOTTOM}" stroke="{c["fg"]}"/>')

    # Runner with head torch, looping along the ridge.
    a('<g>'
      f'<circle r="28" fill="url(#glow)"/>'
      f'<path d="M4,-2 L34,-13 L34,9 Z" fill="url(#beam)"/>'
      f'<circle r="5" fill="{c["runner"]}" stroke="{c["bg"]}" stroke-width="2"/>'
      '<animateMotion dur="16s" repeatCount="indefinite" rotate="auto" calcMode="linear">'
      '<mpath href="#ridge" xlink:href="#ridge" xmlns:xlink="http://www.w3.org/1999/xlink"/></animateMotion>'
      '</g>')

    # Stats strip, like the summary screen of a GPS watch.
    stats = [
        ("DISTANCE", f"{n} wk"),
        ("ELEVATION", f"{total:,}"),
        ("ACTIVE DAYS", f"{active}/{len(days)}"),
        ("LONGEST STREAK", f"{longest} d"),
        ("CURRENT STREAK", f"{current} d"),
        ("AID STATIONS", f"{sum(len(v) for v in by_week.values())}"),
    ]
    a(f'<line x1="{L}" x2="{W - R}" y1="{STATS_Y - 34}" y2="{STATS_Y - 34}" stroke="{c["grid"]}"/>')
    col = (W - L - R) / len(stats)
    for i, (k, v) in enumerate(stats):
        x = L + i * col
        a(f'<text x="{x:.1f}" y="{STATS_Y - 8}" fill="{c["muted"]}" font-size="9.5" letter-spacing="1.2">{k}</text>'
          f'<text x="{x:.1f}" y="{STATS_Y + 16}" fill="{c["fg"]}" font-size="20" font-weight="800">{v}</text>')
    a(f'<text x="{W - R}" y="{H - 12}" fill="{c["muted"]}" font-size="9" text-anchor="end" opacity=".8">'
      f'updated {date.today():%Y-%m-%d}</text>')

    a('</g></svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("GITHUB_USER", "mmornati"))
    p.add_argument("--out", default="assets/trail")
    p.add_argument("--feed", default=FEED)
    p.add_argument("--data", help="raw GraphQL JSON instead of calling the API")
    args = p.parse_args()

    if args.data:
        raw = json.load(open(args.data))
    else:
        raw = fetch_calendar(args.user, os.environ["GITHUB_TOKEN"])
    cal = raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]
    posts = fetch_posts(args.feed) if args.feed else []

    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"trail-{theme}.svg")
        with open(path, "w") as f:
            f.write(render(weeks, posts, theme))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
