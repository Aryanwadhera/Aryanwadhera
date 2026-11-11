#!/usr/bin/env python3
"""Render the profile README's SVG cards into cards/.

Reads data/profile.json (refreshed daily by .github/workflows/profile-cards.yml)
and writes one self-contained SVG per card:

    hero.svg, tile-website.svg, tile-linkedin.svg, tile-instagram.svg,
    company.svg, activity.svg, graph.svg

Usage:
    python scripts/render_cards.py           # animated cards (what the Action commits)
    STATIC=1 python scripts/render_cards.py  # final frame only, for screenshots

Needs fonttools (pip install fonttools brotli) to subset Inter.

The cards are shown through <img> tags, so each SVG only uses what works there:
a <style> block with CSS keyframes and Inter embedded as base64 WOFF. There are no
scripts, no external requests and no SMIL. SMIL cannot be turned off by
prefers-reduced-motion; CSS animations can, so every card carries that rule.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "profile.json"
FONT_DIR = ROOT / "fonts"
PORTRAIT_FILE = ROOT / "assets" / "portrait.jpg"  # optional
OUT_DIR = ROOT / "cards"

STATIC = os.environ.get("STATIC") == "1"

# Colours from the personal site: Black, plus its Gray scale.
INK = "#000000"
MUTED = "#737373"       # Gray 500, secondary text
SURFACE = "#F5F5F5"     # Gray 100, card borders
RULE = "#E5E5E5"
CARD_BG = "#FFFFFF"
BRAND = "#000000"       # bars and contribution graph; the site is monochrome
RAMP = ["#F5F5F5", "#D4D4D4", "#737373", "#404040", "#000000"]

HERO_NAME = "Aryan Wadhera"
HERO_LINE = "CEO & Managing Partner, The Moonlit Company · Pre-law at IVC"

TILES = [
    ("tile-website", "Website", "aryanwadhera.tech"),
    ("tile-linkedin", "LinkedIn", "linkedin.com/in/aryanwadhera"),
    ("tile-instagram", "Instagram", "@aryanwadhera_"),
]
STAGGER = 0.3  # seconds between cards, so the page plays top to bottom
EASE = "cubic-bezier(.2,.7,.2,1)"

FONT_FILES = {400: "Inter-Regular.ttf", 500: "Inter-Medium.ttf", 600: "Inter-SemiBold.ttf"}
SUBSET_UNICODES = "U+0020-007E,U+00A0-00FF,U+2013-2014,U+2018-201D,U+2022,U+2026,U+2192,U+2197"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ONE_DAY = dt.timedelta(days=1)

FONT_B64: dict[int, str] = {}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def subset_fonts(tmp: Path) -> None:
    """Subset Inter to the Latin range we use and embed it as base64 WOFF."""
    pyftsubset = shutil.which("pyftsubset")
    for weight, name in FONT_FILES.items():
        out = tmp / f"{weight}.woff"
        args = [
            f"--unicodes={SUBSET_UNICODES}",
            "--flavor=woff",
            "--no-hinting",
            "--layout-features=kern,liga,calt,tnum",
            f"--output-file={out}",
            str(FONT_DIR / name),
        ]
        cmd = [pyftsubset, *args] if pyftsubset else [sys.executable, "-m", "fontTools.subset", *args]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            sys.exit(f"font subsetting failed for {name}: {exc}\nInstall with: pip install fonttools brotli")
        FONT_B64[weight] = base64.b64encode(out.read_bytes()).decode("ascii")


class Card:
    """One SVG card. `order` is its position on the page; it sets the stagger."""

    def __init__(self, name: str, width: int, height: int, title: str, desc: str, order: int):
        self.name = name
        self.w = width
        self.h = height
        self.title = title
        self.desc = desc
        self.t0 = order * STAGGER
        self.parts: list[str] = []
        self.weights: set[int] = set()

    def anim(self, kind: str, offset: float = 0.0, dur: float = 0.7) -> str:
        """Return a style attribute (with a leading space) that starts `kind` at t0+offset."""
        if STATIC:
            return ""
        return f' style="animation:{kind} {dur}s {EASE} {self.t0 + offset:.2f}s both"'

    def frame(self, stroke: str = SURFACE) -> None:
        self.rect(0.5, 0.5, self.w - 1, self.h - 1, 24, CARD_BG, stroke=stroke)

    def rect(self, x, y, w, h, rx, fill, stroke=None, anim: str = "", cls: str = "") -> None:
        stroke_attr = f' stroke="{stroke}"' if stroke else ""
        class_attr = f' class="{cls}"' if cls else ""
        self.parts.append(
            f'<rect{class_attr} x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}"{stroke_attr}{anim}/>'
        )

    def text(self, x, y, s, size=14, weight=400, fill=INK, anchor="start", anim="", extra="") -> None:
        self.weights.add(weight)
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{extra}{anim}>{esc(s)}</text>'
        )

    def add(self, markup: str) -> None:
        self.parts.append(markup)

    def render(self) -> str:
        faces = "".join(
            f"@font-face{{font-family:Inter;font-style:normal;font-weight:{w};"
            f'src:url(data:font/woff;base64,{FONT_B64[w]}) format("woff")}}'
            for w in sorted(self.weights)
        )
        css = (
            faces
            + "text{font-family:Inter,-apple-system,'Helvetica Neue',Arial,sans-serif}"
            + "@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
            + "@keyframes fade{from{opacity:0}to{opacity:1}}"
            + "@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}"
            + ".grow{transform-box:fill-box;transform-origin:50% 100%}"
            + "@media (prefers-reduced-motion:reduce){"
            + "*,*::before,*::after{animation:none!important;transition:none!important}}"
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{esc(self.title)}</title><desc id="d">{esc(self.desc)}</desc>'
            f"<style>{css}</style>" + "".join(self.parts) + "</svg>\n"
        )


# ---------- data ----------

def summarize(days: list[tuple[dt.date, int]]) -> dict:
    counts = dict(days)
    end = days[-1][0]
    window_start = end - dt.timedelta(days=364)  # 365 days including `end`
    in_year = [(d, c) for d, c in days if d >= window_start]
    total = sum(c for _, c in in_year)
    active = sum(1 for _, c in in_year if c > 0)

    # Current streak: counts back from today, or from yesterday if today is still empty.
    cursor = end if counts[end] > 0 else end - ONE_DAY
    streak = 0
    while counts.get(cursor, 0) > 0:
        streak += 1
        cursor -= ONE_DAY

    longest = run = 0
    prev = None
    for d, c in days:
        if c > 0:
            run = run + 1 if prev is not None and d - prev == ONE_DAY else 1
            longest = max(longest, run)
            prev = d
        else:
            run, prev = 0, None

    busiest_date, busiest_count = max(in_year, key=lambda t: t[1])

    # Last 12 calendar months, ending with the month of `end`.
    buckets: list[tuple[int, int]] = []
    y, m = end.year, end.month
    for _ in range(12):
        buckets.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    buckets.reverse()
    monthly = {k: 0 for k in buckets}
    for d, c in days:
        if (d.year, d.month) in monthly:
            monthly[(d.year, d.month)] += c

    return {
        "end": end,
        "total": total,
        "active": active,
        "window_days": len(in_year),
        "streak": streak,
        "longest": longest,
        "busiest_date": busiest_date,
        "busiest_count": busiest_count,
        "monthly": [(k, monthly[k]) for k in buckets],
    }


def level_fn(values: list[int]):
    """Map a day's count to 0-4 using quartiles of the non-zero days."""
    nonzero = sorted(v for v in values if v > 0)
    if len(nonzero) >= 4:
        q1, q2, q3 = statistics.quantiles(nonzero, n=4, method="inclusive")
    else:
        q1, q2, q3 = 1, 3, 6

    def level(v: int) -> int:
        if v <= 0:
            return 0
        if v <= q1:
            return 1
        if v <= q2:
            return 2
        if v <= q3:
            return 3
        return 4

    return level


def short_date(d: dt.date) -> str:
    return f"{MONTHS[d.month - 1]} {d.day}"


def truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# ---------- cards ----------

def hero(portrait_b64: str | None) -> Card:
    c = Card("hero", 830, 200, HERO_NAME, HERO_LINE, order=0)
    c.frame()
    x = 40
    if portrait_b64:
        c.add(
            '<defs><clipPath id="portrait"><rect x="40" y="36" width="128" height="128" rx="32"/>'
            "</clipPath></defs>"
        )
        c.add(
            f'<image{c.anim("fade", 0.0, 0.8)} x="40" y="36" width="128" height="128" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait)" '
            f'href="data:image/jpeg;base64,{portrait_b64}"/>'
        )
        x = 200
    c.text(x, 96, HERO_NAME, size=40, weight=600, extra=' letter-spacing="-0.8"', anim=c.anim("rise", 0.1))
    c.text(x, 134, HERO_LINE, size=16, weight=500, fill=MUTED, anim=c.anim("rise", 0.25))
    return c


def tile(name: str, label: str, sub: str, order: int) -> Card:
    c = Card(name, 270, 150, label, sub, order=order)
    c.frame()
    c.add(
        f'<g fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" transform="translate(222 22)"{c.anim("fade", 0.3, 0.6)}>'
        '<path d="M4 14 L14 4 M6 4 H14 V12"/></g>'
    )
    c.text(24, 70, label, size=20, weight=600, anim=c.anim("rise", 0.1))
    c.text(24, 96, sub, size=14, weight=500, fill=MUTED, anim=c.anim("rise", 0.18))
    return c


def activity(days: list[tuple[dt.date, int]]) -> Card:
    st = summarize(days)
    c = Card(
        "activity", 830, 360, "Contributions",
        f"{st['total']:,} contributions in the last year. Monthly totals, streak, active days and busiest day.",
        order=3,
    )
    c.frame()
    c.text(40, 50, "Contributions", size=18, weight=600, anim=c.anim("rise", 0.05))
    c.text(790, 50, f"{st['total']:,} in the last year", size=14, weight=500, fill=MUTED,
           anchor="end", anim=c.anim("rise", 0.05))

    stats = [
        ("Current streak", f"{st['streak']} days"),
        ("Longest streak", f"{st['longest']} days"),
        ("Active days", f"{st['active']} of {st['window_days']}"),
        ("Busiest day", f"{st['busiest_count']} on {short_date(st['busiest_date'])}"),
    ]
    for i, (label, value) in enumerate(stats):
        x = 40 + i * 190
        c.text(x, 98, label, size=13, weight=500, fill=MUTED, anim=c.anim("rise", 0.15 + i * 0.04))
        c.text(x, 130, value, size=24, weight=600, anim=c.anim("rise", 0.2 + i * 0.04))
    c.rect(40, 154, 750, 1, 0, RULE, anim=c.anim("fade", 0.3, 0.4))

    base, max_h, slot, bar_w = 316, 120, 750 / 12, 34
    peak = max((v for _, v in st["monthly"]), default=0) or 1
    for i, ((y, m), value) in enumerate(st["monthly"]):
        x = 40 + i * slot + (slot - bar_w) / 2
        h = round(value / peak * max_h, 2)
        c.add(
            f'<rect class="grow" x="{x:.2f}" y="{base - h:.2f}" width="{bar_w}" height="{h}" '
            f'rx="6" fill="{BRAND}"{c.anim("grow", 0.9 + i * 0.05, 0.8)}/>'
        )
        if value:
            c.text(x + bar_w / 2, base - h - 8, value, size=12, weight=500, fill=MUTED,
                   anchor="middle", anim=c.anim("fade", 1.2 + i * 0.05, 0.5))
        c.text(x + bar_w / 2, 342, MONTHS[m - 1], size=12, weight=500, fill=MUTED, anchor="middle",
               anim=c.anim("fade", 0.9 + i * 0.05, 0.5))
    return c


def graph(days: list[tuple[dt.date, int]]) -> Card:
    st = summarize(days)
    counts = dict(days)
    end = st["end"]
    start = end - dt.timedelta(days=(end.isoweekday() % 7) + 52 * 7)  # Sunday, 53 weeks back
    level = level_fn([c for d, c in days if d >= end - dt.timedelta(days=364)])

    c = Card("graph", 830, 216, "Contribution graph",
             f"{st['total']:,} contributions in the last year", order=4)
    c.frame()
    c.text(40, 44, "Contribution graph", size=16, weight=600, anim=c.anim("rise", 0.05))
    c.text(790, 44, f"{st['total']:,} contributions in the last year", size=13, weight=500,
           fill=MUTED, anchor="end", anim=c.anim("rise", 0.05))

    x0, y0, pitch, cell = 40, 86, 14, 11
    last_label_col = -10
    for col in range(53):
        col_days = [start + dt.timedelta(days=col * 7 + row) for row in range(7)]
        cells = []
        for row, d in enumerate(col_days):
            if d > end:
                break
            cells.append(
                f'<rect x="{x0 + col * pitch}" y="{y0 + row * pitch}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{RAMP[level(counts.get(d, 0))]}"/>'
            )
        if not cells:
            continue
        # Sweep left to right: each week column fades in after the one before it.
        c.add(f"<g{c.anim('fade', 0.3 + col * 0.02, 0.5)}>" + "".join(cells) + "</g>")
        first_of_month = next((d for d in col_days if d.day == 1 and d <= end), None)
        if first_of_month and col - last_label_col >= 3:
            c.text(x0 + col * pitch, y0 - 10, MONTHS[first_of_month.month - 1], size=11, weight=500,
                   fill=MUTED, anim=c.anim("fade", 0.3 + col * 0.02, 0.5))
            last_label_col = col

    legend_y = y0 + 7 * pitch - 3 + 14
    c.text(670, legend_y + 3, "Less", size=12, weight=500, fill=MUTED, anchor="end")
    for i, color in enumerate(RAMP):
        c.rect(676 + i * 14, legend_y - 9, cell, cell, 2, color)
    c.text(750, legend_y + 3, "More", size=12, weight=500, fill=MUTED)
    return c


def company() -> Card:
    c = Card("company", 830, 120, "The Moonlit Company", "CEO & Managing Partner, moonlit.company", order=2)
    c.frame()
    c.add(
        f'<g fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" transform="translate(766 40)"{c.anim("fade", 0.3, 0.6)}>'
        '<path d="M4 14 L14 4 M6 4 H14 V12"/></g>'
    )
    c.text(40, 56, "The Moonlit Company", size=22, weight=600, anim=c.anim("rise", 0.1))
    c.text(40, 84, "CEO & Managing Partner · moonlit.company", size=15, weight=500, fill=MUTED,
           anim=c.anim("rise", 0.18))
    return c


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    by_date = {dt.date.fromisoformat(d["date"]): int(d["count"]) for d in data["days"]}
    if not by_date:
        sys.exit("data/profile.json has no contribution days")
    days = sorted(by_date.items())

    portrait_b64 = None
    if PORTRAIT_FILE.exists():
        portrait_b64 = base64.b64encode(PORTRAIT_FILE.read_bytes()).decode("ascii")

    with tempfile.TemporaryDirectory() as tmp:
        subset_fonts(Path(tmp))

    cards: list[Card] = [hero(portrait_b64)]
    cards += [tile(name, label, sub, order=1) for name, label, sub in TILES]
    cards.append(company())
    cards.append(activity(days))
    cards.append(graph(days))

    OUT_DIR.mkdir(exist_ok=True)
    written = set()
    for card in cards:
        path = OUT_DIR / f"{card.name}.svg"
        path.write_text(card.render(), encoding="utf-8")
        written.add(path.name)
    for stale in OUT_DIR.glob("*.svg"):
        if stale.name not in written:
            stale.unlink()

    mode = "static final frame" if STATIC else "animated"
    print(f"Rendered {len(cards)} cards ({mode}) into {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
