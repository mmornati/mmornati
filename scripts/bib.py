#!/usr/bin/env python3
"""Race bib header: name, role and stack printed on a pinned race number.

The bib is paper-coloured with a transparent surround, so one SVG works on
both GitHub themes. Static content: edit the constants below.

Usage:
  python3 scripts/bib.py [--out assets/bib]
"""
import argparse
import os
from html import escape

from trail import FONT

NUMBER = "2009"                       # the year Marco joined GitHub
NAME = "MARCO MORNATI"
RACE = "GITHUB ULTRA · OPEN SOURCE DIVISION"
WAVE = "BIB #2009"
DETAILS = [("CAT", "DIRECTOR OF ENGINEERING"), ("CLUB", "DECATHLON DIGITAL"),
           ("MOTTO", "HAPPINESS-DRIVEN DEV")]
SPONSORS = ["JAVA", "PYTHON", "QUARKUS", "SPRING", "K8S", "TERRAFORM", "GCP", "HOME ASSISTANT"]
CHIP = "mmornati"

W, H = 960, 300
PAPER, INK, MUTED, BAND, ACCENT = "#f6f4ee", "#1f2328", "#59636e", "#3643ba", "#ffb547"


def barcode(text, x, y, height):
    """Timing-chip barcode: the username's bits as bars."""
    bits = "".join(f"{ord(ch):08b}" for ch in text)
    return "".join(f'<rect x="{x + i * 3.4:.1f}" y="{y}" width="{2.6 if i % 3 == 0 else 2}" height="{height}" fill="{INK}"/>'
                   for i, b in enumerate(bits) if b == "1")


def pin(x, y):
    return (f'<g transform="translate({x},{y}) rotate(-20)">'
            f'<ellipse rx="22" ry="5" fill="none" stroke="#9aa3ad" stroke-width="2.4"/>'
            f'<circle cx="-22" r="4.2" fill="#c3cad1"/></g>')


def render():
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="t" font-family="{FONT}">')
    a(f'<title id="t">Race bib {NUMBER}: {NAME}, {DETAILS[0][1].title()} at {DETAILS[1][1].title()}</title>')
    a('<defs><filter id="shadow" x="-5%" y="-5%" width="110%" height="120%">'
      '<feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity=".28"/></filter></defs>')
    a(f'<g transform="rotate(-1.2 {W / 2} {H / 2})">')
    a(f'<rect x="40" y="22" width="880" height="256" rx="10" fill="{PAPER}" filter="url(#shadow)"/>')
    a(f'<path d="M40,32 a10,10 0 0 1 10,-10 h860 a10,10 0 0 1 10,10 v34 h-880 z" fill="{BAND}"/>')
    a(f'<text x="104" y="51" fill="#ffffff" font-size="15" font-weight="800" letter-spacing="2">{escape(RACE)}</text>')
    a(f'<text x="856" y="51" fill="{ACCENT}" font-size="13" font-weight="800" text-anchor="end">{WAVE}</text>')

    a(f'<text x="62" y="190" fill="{INK}" font-size="132" font-weight="800" letter-spacing="-6">{NUMBER}</text>')
    a(f'<text x="590" y="112" fill="{INK}" font-size="30" font-weight="800">{escape(NAME)}</text>')
    for i, (k, v) in enumerate(DETAILS):
        a(f'<text x="590" y="{138 + i * 20}" fill="{MUTED}" font-size="12.5">'
          f'<tspan font-weight="700">{k}</tspan> · {escape(v)}</text>')
    a(barcode(CHIP, 590, 198, 34))
    a(f'<text x="590" y="244" fill="{MUTED}" font-size="9">TIMING CHIP · @{CHIP}</text>')

    x = 62
    for s in SPONSORS:
        w = len(s) * 8 + 20
        a(f'<rect x="{x}" y="226" width="{w}" height="22" rx="3" fill="{BAND}"/>'
          f'<text x="{x + w / 2}" y="241" fill="#ffffff" font-size="10.5" font-weight="700" text-anchor="middle">{s}</text>')
        x += w + 8
        if x > 520:  # sponsors stay left of the barcode
            break
    a(f'<line x1="50" x2="910" y1="262" y2="262" stroke="{MUTED}" stroke-dasharray="4 4" opacity=".5"/>')
    a(f'<text x="480" y="273" fill="{MUTED}" font-size="8" text-anchor="middle" letter-spacing="2">'
      f'✂ · DETACH FOR FINISHER MEDAL · ✂</text>')
    a(pin(70, 36) + pin(890, 36) + pin(70, 262) + pin(890, 262))
    a('</g></svg>')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="assets/bib")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "bib.svg")
    with open(path, "w") as f:
        f.write(render())
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
