#!/usr/bin/env python3
"""Boot screen: a neofetch-style terminal card with live GitHub numbers.

Each line types itself out once on load (SMIL, so it runs inside a README
<img>), then the cursor keeps blinking. Writes dark and light variants.
Standard library only.

Usage:
  GITHUB_TOKEN=... python3 scripts/boot.py [--user mmornati] [--out assets/boot]
"""
import argparse
import os
from datetime import date, datetime, timezone
from html import escape

from gh import fetch_profile, fetch_repos, gql
from trail import FONT, streaks

# Static identity lines. Everything else comes from the API.
HOST = "marco@mornati.net"
PROMPT_USER, PROMPT_HOST = "marco", "decathlon"
IDENTITY = [
    ("OS", "Director of Engineering @ Decathlon Digital"),
    ("Kernel", "Happiness-Driven Development 3.0"),
    ("Shell", "Claude Code · Cursor · Copilot · MCP"),
]
IGNORED_LANGUAGES = {"HTML", "CSS", "SCSS", "Less", "Dockerfile", "Makefile", "Shell"}

ASCII = [
    "         /\\",
    "        /  \\      /\\",
    "   /\\  /    \\    /  \\",
    "  /  \\/  o   \\  /    \\",
    " /   /  /|\\   \\/      \\",
    "/   /    |     \\   /\\  \\",
    "   /    / \\     \\_/  \\",
    " _/______________\\____\\_",
    "",
    "   M O R N A T I   O S",
]

THEMES = {
    "dark": {"bg": "#010409", "frame": "#30363d", "fg": "#e6edf3", "muted": "#8b949e",
             "key": "#6c7cff", "accent": "#ffb547", "prompt": "#3fb950", "path": "#6c7cff"},
    "light": {"bg": "#f6f8fa", "frame": "#d1d9e0", "fg": "#1f2328", "muted": "#59636e",
              "key": "#3643ba", "accent": "#bc4c00", "prompt": "#1a7f37", "path": "#3643ba"},
}
SWATCH = ["#0d1117", "#3643ba", "#6c7cff", "#3fb950", "#ffb547", "#f85149", "#bc8cff", "#e6edf3"]

W = 960
LINE = 21          # line height
TOP = 78           # first info line baseline
INFO_X = 330       # left edge of the key/value column
TYPE_STEP = 0.14   # seconds between lines


def fetch(user, token):
    profile = fetch_profile(user, token)
    repos = fetch_repos(user, token)

    # All-time contributions: one aliased field per year (the API caps a range at one year).
    since = int(profile["createdAt"][:4])
    fields = " ".join(
        f'y{y}:contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z")'
        "{contributionCalendar{totalContributions}}"
        for y in range(since, date.today().year + 1))
    years = gql(f"query($login:String!){{user(login:$login){{{fields}}}}}", token, {"login": user})["user"]
    all_time = sum(v["contributionCalendar"]["totalContributions"] for v in years.values())
    return profile, repos, all_time


def uptime(created):
    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    months = (now.year - start.year) * 12 + now.month - start.month - (now.day < start.day)
    return f"{months // 12} years, {months % 12} months (since {start:%b %Y})"


def languages(repos, top=5):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in IGNORED_LANGUAGES:
                continue
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])[:top]
    return [(n, s / total * 100, colors[n]) for n, s in ranked]


def build_lines(profile, repos, all_time):
    public = [r for r in repos if not r["isPrivate"]]
    stars = sum(r["stargazerCount"] for r in public)
    cal = profile["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    longest, current = streaks(days)
    recent = sorted((r for r in public if not r["isArchived"]), key=lambda r: r["pushedAt"], reverse=True)[:3]

    return [
        *IDENTITY[:1],
        ("Uptime", uptime(profile["createdAt"])),
        *IDENTITY[1:],
        ("Repos", f"{len(public)}"),
        ("Stars", f"{stars:,}"),
        ("Followers", f"{profile['followers']['totalCount']:,}"),
        ("Contributions", f"{cal['totalContributions']:,} this year · {all_time:,} all-time"),
        ("Streak", f"{current} days current · {longest} days longest"),
        ("Processes", ", ".join(r["name"] for r in recent)),
    ], languages(repos)


def reveal(i, width, height, y):
    """A clip rect that widens once, like the line being typed."""
    begin = 0.3 + i * TYPE_STEP
    return (f'<clipPath id="c{i}"><rect x="{INFO_X}" y="{y - height + 5}" width="0" height="{height}">'
            f'<animate attributeName="width" from="0" to="{width}" begin="{begin:.2f}s" dur="0.35s" '
            f'fill="freeze" calcMode="linear"/></rect></clipPath>')


def render(info, langs, theme):
    c = THEMES[theme]
    rows = len(info) + 5  # header, rule, info, languages label, bar, swatch
    h = TOP + rows * LINE + 50
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" '
      f'role="img" aria-labelledby="t" font-family="{FONT}" font-size="14">')
    a(f'<title id="t">marco@decathlon neofetch: {escape(" · ".join(f"{k}: {v}" for k, v in info))}</title>')
    a(f'<style>.k{{fill:{c["key"]};font-weight:700}} .v{{fill:{c["fg"]}}} .m{{fill:{c["muted"]}}}'
      f' .cur{{animation:b 1s steps(1) infinite}} @keyframes b{{50%{{opacity:0}}}}'
      f' @media (prefers-reduced-motion:reduce){{.cur{{animation:none}}}}</style>')

    defs, body = [], []
    a(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="12" fill="{c["bg"]}" stroke="{c["frame"]}"/>')
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        a(f'<circle cx="{24 + i * 20}" cy="22" r="6" fill="{col}"/>')
    a(f'<text x="{W / 2}" y="27" text-anchor="middle" class="m" font-size="12">{PROMPT_USER}@{PROMPT_HOST}: ~</text>')

    def prompt(y, cmd):
        return (f'<text x="24" y="{y}" xml:space="preserve"><tspan fill="{c["prompt"]}">{PROMPT_USER}@{PROMPT_HOST}</tspan>'
                f'<tspan class="m">:</tspan><tspan fill="{c["path"]}">~</tspan><tspan class="m">$ </tspan>'
                f'<tspan class="v">{cmd}</tspan></text>')

    a(prompt(56, "neofetch --runner"))

    # ASCII art column.
    for i, line in enumerate(ASCII):
        weight = ' font-weight="700"' if "M O R" in line else ""
        a(f'<text x="24" y="{TOP + 18 + i * 17}" fill="{c["accent"]}" font-size="13" xml:space="preserve"{weight}>'
          f'{escape(line)}</text>')

    # Info column, one clipped line at a time.
    lines = [f'<tspan fill="{c["accent"]}" font-weight="800">{HOST.split("@")[0]}</tspan>'
             f'<tspan class="m">@</tspan><tspan fill="{c["accent"]}" font-weight="800">{HOST.split("@")[1]}</tspan>',
             f'<tspan class="m">{"─" * 44}</tspan>']
    lines += [f'<tspan class="k">{k}</tspan><tspan class="m">: </tspan><tspan class="v">{escape(v)}</tspan>'
              for k, v in info]
    lines.append('<tspan class="k">Languages</tspan><tspan class="m">: </tspan><tspan class="v">'
                 + escape("  ".join(f"{n} {p:.0f}%" for n, p, _ in langs)) + "</tspan>")
    clip_w = W - INFO_X - 20
    for i, content in enumerate(lines):
        y = TOP + i * LINE
        defs.append(reveal(i, clip_w, LINE, y))
        body.append(f'<g clip-path="url(#c{i})"><text x="{INFO_X}" y="{y}" xml:space="preserve">{content}</text></g>')

    # Language bar and colour swatch, revealed like the last two lines.
    i = len(lines)
    y = TOP + i * LINE - 10
    defs.append(reveal(i, clip_w, LINE + 4, y + 14))
    x, bar_w = INFO_X, clip_w - 10
    segs = []
    total = sum(p for _, p, _ in langs) or 1
    for n, p, col in langs:
        w = bar_w * p / total
        segs.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="10" rx="2" fill="{col}"/>')
        x += w
    body.append(f'<g clip-path="url(#c{i})">{"".join(segs)}</g>')
    i += 1
    y = TOP + i * LINE - 8
    defs.append(reveal(i, clip_w, LINE, y + 14))
    sw = "".join(f'<rect x="{INFO_X + k * 26}" y="{y}" width="26" height="14" fill="{col}"/>' for k, col in enumerate(SWATCH))
    body.append(f'<g clip-path="url(#c{i})">{sw}</g>')

    a(f'<defs>{"".join(defs)}</defs>')
    out.extend(body)

    py = h - 22
    done = 0.3 + (i + 1) * TYPE_STEP
    a(f'<g opacity="0">{prompt(py, "")}'
      f'<rect class="cur" x="{24 + 20 * 8.43:.0f}" y="{py - 13}" width="8" height="16" fill="{c["fg"]}"/>'
      f'<set attributeName="opacity" to="1" begin="{done:.2f}s" fill="freeze"/></g>')
    a('</svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("GITHUB_USER", "mmornati"))
    p.add_argument("--out", default="assets/boot")
    args = p.parse_args()

    profile, repos, all_time = fetch(args.user, os.environ["GITHUB_TOKEN"])
    info, langs = build_lines(profile, repos, all_time)
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"boot-{theme}.svg")
        with open(path, "w") as f:
            f.write(render(info, langs, theme))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
