#!/usr/bin/env python3
"""git log feed: merge blog posts and Mastodon toots into one `git log --graph`
style history and write it into README.md between the FEED markers.

Blog posts sit on the main line; toots are commits on a side branch that
merges back. Rendered as a <pre> block so the links stay clickable on GitHub.
Standard library only.

Usage:
  python3 scripts/feed.py [--readme README.md] [--limit 8]
"""
import argparse
import hashlib
import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import escape, unescape

BLOG = "https://blog.mornati.net/rss.xml"
MASTODON = "https://techhub.social/@mmornati.rss"
START, END = "<!-- FEED:START -->", "<!-- FEED:END -->"
MAX_TEXT = 72


def fetch(url, kind):
    """Return [(datetime, kind, text, link)]; empty list if the feed is unreachable."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "marco-os-feed"})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"warning: {kind} feed unavailable ({e})")
        return []
    items = []
    for item in root.iter("item"):
        link, pub = item.findtext("link"), item.findtext("pubDate")
        # Blog items have titles; toots only have an HTML description.
        text = item.findtext("title") or item.findtext("description") or ""
        text = unescape(text)
        text = re.sub(r"</?(p|br)[^>]*>", " ", text)   # block breaks become spaces
        text = re.sub(r"<[^>]+>", "", text)            # inline tags (Mastodon splits links into spans)
        text = re.sub(r"^RE:\s*", "", text.strip())
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if link and pub and text:
            items.append((parsedate_to_datetime(pub), kind, text, link))
    return items


def clip(text, limit=MAX_TEXT):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def render(entries):
    """Draw the graph: blog on column 0, runs of toots on a branch at column 2."""
    lines = []
    on_branch = False
    for i, (when, kind, text, link) in enumerate(entries):
        sha = hashlib.sha1(link.encode()).hexdigest()[:7]
        head = ("HEAD -&gt; toots, " if kind == "toot" else "HEAD -&gt; main, ") if i == 0 else ""
        body = (f'<b>{sha}</b> {when:%Y-%m-%d} ({head}{kind}) '
                f'<a href="{escape(link)}">{escape(clip(text), quote=False)}</a>')
        if kind == "toot":
            if not on_branch and i > 0:
                lines.append("|\\")
            lines.append(f"| * {body}")
            on_branch = True
        else:
            if on_branch:
                lines.append("|/")
                on_branch = False
            lines.append(f"* {body}")
    if on_branch:
        lines.append("|/")
    lines.append("* <i>… older history on <a href=\"https://blog.mornati.net\">blog.mornati.net</a></i>")
    return "<pre>\n" + "\n".join(lines) + "\n</pre>"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--readme", default="README.md")
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args()

    entries = fetch(BLOG, "blog") + fetch(MASTODON, "toot")
    if not entries:
        print("no entries fetched, leaving README untouched")
        return
    entries.sort(key=lambda e: e[0], reverse=True)
    block = render(entries[:args.limit])

    readme = open(args.readme).read()
    a, b = readme.index(START) + len(START), readme.index(END)
    updated = readme[:a] + "\n" + block + "\n" + readme[b:]
    if updated != readme:
        open(args.readme, "w").write(updated)
        print(f"updated {args.readme}")
    else:
        print("no changes")


if __name__ == "__main__":
    main()
