#!/usr/bin/env python3
"""Finisher medals: a medal wall earned from real GitHub milestones.

Each medal is computed from the API and engraved with its proof; a medal
whose rule is not met is simply not drawn. Writes dark and light variants.
Standard library only.

Usage:
  GITHUB_TOKEN=... python3 scripts/medals.py [--user mmornati] [--out assets/medals]
"""
import argparse
import os
from datetime import datetime, timezone
from html import escape

from gh import fetch_profile, fetch_repos
from trail import FONT

GOLD, SILVER, BRONZE = "#f2b84b", "#c3cad1", "#cd8a4f"
RIBBONS = ["#f85149", "#3643ba"]
THEMES = {
    "dark": {"fg": "#e6edf3", "muted": "#8b949e", "stripe": "#e6edf3"},
    "light": {"fg": "#1f2328", "muted": "#59636e", "stripe": "#ffffff"},
}
W, H = 960, 250
FAST_START_DAYS = 90     # a repo this young with stars earns Fast Start
FAST_START_STARS = 5
ULTRA_YEARS = 10


def parse(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def best(repos, key, used):
    """Highest-scoring repo, preferring ones that have not won a medal yet."""
    fresh = [r for r in repos if r["name"] not in used]
    return max(fresh or repos, key=key)


def earn(profile, repos):
    """Return [(title, engraving, caption, subject, metal)] for every medal earned."""
    now = datetime.now(timezone.utc)
    public = [r for r in repos if not r["isPrivate"]]
    medals = []
    used = set()

    oldest = min(public, key=lambda r: r["createdAt"])
    used.add(oldest["name"])
    medals.append(("PIONEER", parse(oldest["createdAt"]).strftime("%Y"), "first repo", oldest["name"], SILVER))

    top = max(public, key=lambda r: r["stargazerCount"])
    if top["stargazerCount"]:
        used.add(top["name"])
        medals.append(("PODIUM", f'{top["stargazerCount"]} ★', "most starred", top["name"], GOLD))

    years = (now - parse(profile["createdAt"])).days // 365
    if years >= ULTRA_YEARS:
        medals.append(("ULTRA", f"{years} YRS", "on GitHub", f'since {parse(profile["createdAt"]):%b %Y}', GOLD))

    young = [r for r in public if (now - parse(r["createdAt"])).days <= FAST_START_DAYS
             and r["stargazerCount"] >= FAST_START_STARS]
    if young:
        r = max(young, key=lambda r: r["stargazerCount"])
        used.add(r["name"])
        days = max(1, (now - parse(r["createdAt"])).days)
        medals.append(("FAST START", f'{r["stargazerCount"]} ★', f"in {days} days", r["name"], BRONZE))

    forked = best(public, lambda r: r["forkCount"], used)
    if forked["forkCount"]:
        used.add(forked["name"])
        medals.append(("ENDURANCE", f'{forked["forkCount"]}', "forks", forked["name"], SILVER))

    long_run = best(public, lambda r: parse(r["pushedAt"]) - parse(r["createdAt"]), used)
    span = (parse(long_run["pushedAt"]) - parse(long_run["createdAt"])).days // 365
    if span >= 2:
        medals.append(("LONG RUN", f"{span} YRS", "of commits", long_run["name"], BRONZE))
    return medals


def render(medals, theme):
    c = THEMES[theme]
    col = W / len(medals)
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="t" font-family="{FONT}">')
    a('<title id="t">Finisher medals: ' + escape("; ".join(f"{t} {e} {cap} ({s})" for t, e, cap, s, _ in medals)) + '</title>')
    a('<defs><radialGradient id="shine" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".55"/>'
      '<stop offset=".5" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>')
    for i, (title, big, caption, subject, metal) in enumerate(medals):
        cx = col * i + col / 2
        delay = 0.15 * i
        # Ribbon, then the medal hanging from it, swinging gently.
        a(f'<g><animateTransform attributeName="transform" type="rotate" values="-2 {cx:.1f} 10;2 {cx:.1f} 10;-2 {cx:.1f} 10" '
          f'dur="{4 + i % 3}s" begin="{delay:.2f}s" repeatCount="indefinite"/>')
        a(f'<path d="M{cx - 24:.1f},6 L{cx - 8:.1f},78 L{cx + 8:.1f},78 L{cx + 24:.1f},6 Z" fill="{RIBBONS[i % 2]}"/>'
          f'<path d="M{cx - 7:.1f},6 L{cx:.1f},78 L{cx + 7:.1f},6 Z" fill="{c["stripe"]}" opacity=".85"/>')
        a(f'<circle cx="{cx:.1f}" cy="128" r="50" fill="{metal}"/>'
          f'<circle cx="{cx:.1f}" cy="128" r="50" fill="url(#shine)"/>'
          f'<circle cx="{cx:.1f}" cy="128" r="42" fill="none" stroke="#1a1200" stroke-opacity=".3" stroke-width="1.6" stroke-dasharray="3 3"/>')
        size = 19 if len(big) <= 6 else 16
        a(f'<text x="{cx:.1f}" y="124" fill="#1a1200" font-size="{size}" font-weight="800" text-anchor="middle">{escape(big)}</text>'
          f'<text x="{cx:.1f}" y="142" fill="#1a1200" font-size="8.5" text-anchor="middle" opacity=".8">{escape(caption)}</text>')
        a('</g>')
        a(f'<text x="{cx:.1f}" y="204" fill="{c["fg"]}" font-size="12" font-weight="800" text-anchor="middle" letter-spacing="1.5">{title}</text>')
        name = subject if len(subject) <= 24 else subject[:23] + "…"
        a(f'<text x="{cx:.1f}" y="221" fill="{c["muted"]}" font-size="9.5" text-anchor="middle">{escape(name)}</text>')
    a('</svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", default=os.environ.get("GITHUB_USER", "mmornati"))
    p.add_argument("--out", default="assets/medals")
    args = p.parse_args()
    token = os.environ["GITHUB_TOKEN"]
    medals = earn(fetch_profile(args.user, token), fetch_repos(args.user, token))
    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"medals-{theme}.svg")
        with open(path, "w") as f:
            f.write(render(medals, theme))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
