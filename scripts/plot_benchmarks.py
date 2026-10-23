"""Render the README benchmark charts as static SVG (light and dark) from result files.

Run `uv run python scripts/plot_benchmarks.py` after re-running the benchmarks; every
number, including the numbers in titles, comes from `benchmarks/`, never typed into a
chart. No plotting dependency: plain SVG.

Each chart's form follows its data: number tiles for the headline, a unit grid (one
square per question) for answer outcomes, a heatmap for text x method, lines for
library growth and model size, dot plots for dev/heldout pairs, 100% stacked bars for
where misses land, and before -> after arrows. Palette: validated categorical slots
1-5 in fixed order and a one-hue blue ramp, separately stepped for light and dark.
Light-mode aqua, yellow and pink are below 3:1 on the surface, so every mark carries a
value label or a counted legend entry. Marks carry <title> tooltips where SVG is opened
directly.
"""

import json
import math
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "benchmarks"
BENCH = ROOT / "benchmarks"
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "card": "#f2f1ed",
        "text": "#0b0b0b",
        "secondary": "#52514e",
        "grid": "#e4e3df",
        "context": ["#9b9992", "#c9c7c0"],
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
        # Sequential blue, near-zero light (receding to the surface) -> dark.
        "ramp": ["#e3eefc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"],
    },
    "dark": {
        "surface": "#1a1a19",
        "card": "#232321",
        "text": "#f0efec",
        "secondary": "#c3c2b7",
        "grid": "#383835",
        "context": ["#8a8983", "#5d5c58"],
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
        # Near-zero dark (receding to the dark surface) -> bright.
        "ramp": ["#1b2432", "#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"],
    },
}
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
METHODS = [
    ("hybrid", "Hybrid (chat default)"),
    ("lexical", "Keyword (BM25)"),
    ("dense", "Semantic (BGE-small)"),
]


def load(path):
    path = BENCH / path
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def t(x, y, s, theme, size=12, weight=400, fill=None, anchor="start"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" fill="{fill or theme["text"]}">{escape(str(s))}</text>'
    )


def tip(text):
    return f"<title>{escape(text)}</title>" if text else ""


def bar(x, y, w, h, color, title=""):
    """4px rounded data-end, square at the baseline."""
    if w <= 0:
        return ""
    r = min(4, w / 2, h / 2)
    return (
        f'<path d="M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} '
        f'a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z" fill="{color}">{tip(title)}</path>'
    )


def dot(x, y, color, theme, r=6, title="", hollow=False):
    fill, ring = (theme["surface"], color) if hollow else (color, theme["surface"])
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{ring}" '
        f'stroke-width="2">{tip(title)}</circle>'
    )


def legend(items, theme, x=24, y=74):
    out = []
    for label, color, kind in items:
        if kind == "dot":
            out.append(dot(x + 6, y - 4, color, theme, r=5))
        elif kind == "ring":
            out.append(dot(x + 6, y - 4, color, theme, r=4, hollow=True))
        elif kind == "line":
            out.append(
                f'<line x1="{x}" y1="{y - 4}" x2="{x + 14}" y2="{y - 4}" stroke="{color}" '
                'stroke-width="2.5" stroke-linecap="round"/>'
            )
        else:
            out.append(f'<rect x="{x}" y="{y - 10}" width="12" height="12" rx="3" fill="{color}"/>')
        out.append(t(x + 20, y, label, theme, 12, fill=theme["secondary"]))
        x += 20 + int(6.6 * len(label)) + 26
    return "".join(out)


def save(name, title, subtitle, body, width, height, theme_name):
    theme = THEMES[theme_name]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" '
        f'viewBox="0 0 {width} {height:.0f}" font-family="{FONT}" role="img" '
        f'aria-labelledby="t d">\n<title id="t">{escape(title)}</title>'
        f'<desc id="d">{escape(subtitle)}</desc>\n'
        f'<rect width="{width}" height="{height:.0f}" rx="10" fill="{theme["surface"]}"/>\n'
        + t(24, 32, title, theme, 18, 700)
        + t(24, 51, subtitle, theme, 12, fill=theme["secondary"])
        + "\n"
        + body
        + "\n</svg>\n"
    )
    (OUT / f"{name}-{theme_name}.svg").write_text(svg, encoding="utf-8")


HEAT_LOW = 0.2  # heatmap scale starts here; the legend says so


def ramp(theme, v, lo=HEAT_LOW):
    """Continuous interpolation along the ramp's steps, from `lo` to 1."""
    steps = theme["ramp"]
    pos = max(0.0, min(1.0, (v - lo) / (1 - lo))) * (len(steps) - 1)
    i = min(len(steps) - 2, int(pos))
    f = pos - i
    a, b = steps[i], steps[i + 1]
    mix = [round(int(a[k : k + 2], 16) * (1 - f) + int(b[k : k + 2], 16) * f) for k in (1, 3, 5)]
    return "#" + "".join(f"{c:02x}" for c in mix)


def ink_on(hexcolor):
    r, g, b = (int(hexcolor[i : i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r**2.2 + 0.7152 * g**2.2 + 0.0722 * b**2.2
    return "#0b0b0b" if lum > 0.28 else "#f7f7f5"


def domain(values, pad=0.05):
    """A 0.1-aligned range around the values, within [0, 1]: dot plots encode position,
    not length, so they need no zero baseline."""
    lo = max(0.0, math.floor((min(values) - pad) * 10) / 10)
    hi = min(1.0, math.ceil((max(values) + pad) * 10) / 10)
    return lo, hi


def axis_x(x0, w, y0, y1, theme, ticks=(0, 0.25, 0.5, 0.75, 1), lo=0.0, hi=1.0):
    out = []
    for tick in ticks:
        x = x0 + (tick - lo) / (hi - lo) * w
        out.append(
            f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" stroke="{theme["grid"]}"/>'
        )
        out.append(t(x, y1 + 16, f"{tick:g}", theme, 11, fill=theme["secondary"], anchor="middle"))
    return "".join(out)


def label_width(labels, per_char=7.0):
    return int(per_char * max(len(c) for c in labels)) + 24


# ---------------------------------------------------------------- chart forms


def tiles(name, title, subtitle, items, theme_name, width=980):
    theme = THEMES[theme_name]
    gap, top, h = 14, 70, 112
    w = (width - 48 - gap * (len(items) - 1)) / len(items)
    body = []
    for i, (value, line1, line2) in enumerate(items):
        x = 24 + i * (w + gap)
        body.append(
            f'<rect x="{x:.1f}" y="{top}" width="{w:.1f}" height="{h}" rx="10" '
            f'fill="{theme["card"]}"/>'
        )
        body.append(
            f'<rect x="{x:.1f}" y="{top + 14}" width="4" height="{h - 28}" rx="2" '
            f'fill="{theme["series"][0]}"/>'
        )
        body.append(t(x + 20, top + 50, value, theme, 36, 700))
        body.append(t(x + 20, top + 76, line1, theme, 13, 600))
        body.append(t(x + 20, top + 95, line2, theme, 12, fill=theme["secondary"]))
    save(name, title, subtitle, "".join(body), width, top + h + 22, theme_name)


def pair_rows(name, title, subtitle, panels, labels, theme_name, width=980, arrows=False):
    """A row per category with two values, each panel on its own zoomed 0-1 range.

    Dot plot (dev and heldout dots joined by a line) or, with `arrows`, before (hollow,
    gray) -> after (filled, blue).
    """
    theme = THEMES[theme_name]
    lw0 = label_width(panels[0][1])
    col_w = (width - 24) / len(panels)
    top, row_h = 120, 34
    first = (theme["context"][0], "ring") if arrows else (theme["series"][0], "dot")
    second = (theme["series"][0] if arrows else theme["series"][1], "dot")
    body = [legend([(labels[0], *first), (labels[1], *second)], theme)]
    for k, (ptitle, cats, pairs) in enumerate(panels):
        x0 = 24 + k * col_w
        lw = lw0 if k == 0 else 16
        plot_w = col_w - lw - 70
        px = x0 + lw
        body.append(t(x0, top - 18, ptitle, theme, 14, 600))
        bottom = top + len(cats) * row_h
        lo, hi = domain([v for pair in pairs for v in pair])
        ticks = [round(lo + 0.1 * i, 1) for i in range(round((hi - lo) * 10) + 1)]
        body.append(axis_x(px, plot_w, top - 4, bottom - 6, theme, ticks, lo, hi))
        for i, (cat, (a, b)) in enumerate(zip(cats, pairs, strict=True)):
            y = top + i * row_h + row_h / 2 - 4
            if k == 0:
                body.append(
                    t(x0 + lw - 14, y + 4, cat, theme, 13, 700 if i == 0 else 400, anchor="end")
                )
            xa, xb = (px + (v - lo) / (hi - lo) * plot_w for v in (a, b))
            if arrows:
                if abs(xb - xa) > 16:
                    d = 1 if xb > xa else -1
                    body.append(
                        f'<line x1="{xa + 7 * d:.1f}" y1="{y}" x2="{xb - 10 * d:.1f}" y2="{y}" '
                        f'stroke="{theme["secondary"]}" stroke-width="1.5"/>'
                        f'<path d="M{xb - 11 * d:.1f},{y - 4} l{5 * d},4 l{-5 * d},4 z" '
                        f'fill="{theme["secondary"]}"/>'
                    )
                body.append(
                    dot(
                        xa,
                        y,
                        theme["context"][0],
                        theme,
                        r=5,
                        hollow=True,
                        title=f"{cat}, {labels[0]}: {a:.3f}",
                    )
                )
                body.append(
                    dot(xb, y, theme["series"][0], theme, title=f"{cat}, {labels[1]}: {b:.3f}")
                )
                text = f"{b:.2f}" if abs(b - a) < 0.005 else f"{a:.2f} → {b:.2f}"
                body.append(t(max(xa, xb) + 12, y + 4, text, theme, 12, 600))
                continue
            body.append(
                f'<line x1="{xa:.1f}" y1="{y}" x2="{xb:.1f}" y2="{y}" '
                f'stroke="{theme["context"][1]}" stroke-width="3"/>'
            )
            body.append(dot(xa, y, theme["series"][0], theme, title=f"{cat}, {labels[0]}: {a:.3f}"))
            body.append(dot(xb, y, theme["series"][1], theme, title=f"{cat}, {labels[1]}: {b:.3f}"))
            (xl, vl), (xh, vh) = sorted([(xa, a), (xb, b)])
            if abs(xa - xb) < 34:
                body.append(t(xh + 12, y + 4, f"{a:.2f} · {b:.2f}", theme, 12, 600))
            else:
                body.append(t(xl - 11, y + 4, f"{vl:.2f}", theme, 12, 600, anchor="end"))
                body.append(t(xh + 11, y + 4, f"{vh:.2f}", theme, 12, 600))
    save(
        name,
        title,
        subtitle,
        "".join(body),
        width,
        top + len(panels[0][1]) * row_h + 26,
        theme_name,
    )


def grouped(name, title, subtitle, cats, series, theme_name, width=860):
    """Grouped bars where only the first series is in color; the rest are gray context."""
    theme = THEMES[theme_name]
    colors = [theme["series"][0], *theme["context"]]
    lw = label_width(cats, 7.2)
    plot_w = width - lw - 90
    top, bar_h, gap, group_gap = 104, 14, 2, 14
    group_h = len(series) * (bar_h + gap) - gap
    body = [legend([(lab, colors[j], "box") for j, (lab, _) in enumerate(series)], theme)]
    height = len(cats) * (group_h + group_gap)
    body.append(axis_x(24 + lw, plot_w, top - 6, top + height - group_gap, theme))
    for i, cat in enumerate(cats):
        gy = top + i * (group_h + group_gap)
        body.append(t(24 + lw - 12, gy + group_h / 2 + 4, cat, theme, 13, anchor="end"))
        for j, (lab, values) in enumerate(series):
            v, y = values[i], gy + j * (bar_h + gap)
            w = v * plot_w
            body.append(bar(24 + lw, y, w, bar_h, colors[j], f"{cat}, {lab}: {v:.3f}"))
            body.append(
                t(
                    24 + lw + w + 6,
                    y + bar_h - 3,
                    f"{v:.2f}",
                    theme,
                    11,
                    700 if j == 0 else 400,
                    fill=theme["text"] if j == 0 else theme["secondary"],
                )
            )
    save(name, title, subtitle, "".join(body), width, top + height + 28, theme_name)


def heatmap(name, title, subtitle, rows, cols, values, theme_name, width=980, split=None):
    theme = THEMES[theme_name]
    lw = label_width(rows)
    gap = 16 if split else 0
    cell_w = min(150, (width - 48 - lw - gap) / len(cols))
    cell_h, top = 30, 128
    body = [t(24, 74, f"{HEAT_LOW:g}", theme, 11, fill=theme["secondary"])]
    for i, color in enumerate(theme["ramp"]):
        body.append(f'<rect x="{46 + i * 24}" y="64" width="24" height="12" fill="{color}"/>')
    body.append(
        t(
            52 + len(theme["ramp"]) * 24,
            74,
            "1   Recall@10, or share of answers",
            theme,
            11,
            fill=theme["secondary"],
        )
    )

    def cx(j):
        return 24 + lw + j * cell_w + (gap if split is not None and j >= split else 0)

    for j, col in enumerate(cols):
        for k, line in enumerate(col.split("\n")):
            body.append(
                t(cx(j) + cell_w / 2, top - 22 + k * 14, line, theme, 12, 600, anchor="middle")
            )
    for i, row in enumerate(rows):
        y = top + i * cell_h
        body.append(t(24 + lw - 12, y + cell_h / 2 + 4, row, theme, 13, anchor="end"))
        for j, v in enumerate(values[i]):
            color = ramp(theme, v)
            body.append(
                f'<rect x="{cx(j) + 1:.1f}" y="{y + 1}" width="{cell_w - 2:.1f}" '
                f'height="{cell_h - 2}" rx="3" fill="{color}">'
                f"{tip(row + ', ' + cols[j].replace(chr(10), ' ') + f': {v:.3f}')}</rect>"
            )
            body.append(
                t(
                    cx(j) + cell_w / 2,
                    y + cell_h / 2 + 4,
                    f"{v:.2f}",
                    theme,
                    12,
                    600,
                    fill=ink_on(color),
                    anchor="middle",
                )
            )
    save(name, title, subtitle, "".join(body), width, top + len(rows) * cell_h + 22, theme_name)


def lines(
    name,
    title,
    subtitle,
    panels,
    theme_name,
    xlabels,
    width=980,
    height=380,
    xlog=False,
    ylo=0.0,
    yhi=1.0,
):
    """Line panels; each panel has one y axis (never two)."""
    theme = THEMES[theme_name]
    col_w = (width - 24) / len(panels)
    top, bottom_pad = 110, 70
    plot_h = height - top - bottom_pad
    names = [s for s, _ in panels[0][2]]
    body = [legend([(s, theme["series"][j], "line") for j, s in enumerate(names)], theme)]

    def Y(v):
        return top + (yhi - v) / (yhi - ylo) * plot_h

    for k, (ptitle, xs, series) in enumerate(panels):
        x0 = 24 + k * col_w + 40
        plot_w = col_w - 40 - 30
        body.append(t(x0 - 40, top - 16, ptitle, theme, 14, 600))
        lo, hi = (math.log10(xs[0]), math.log10(xs[-1])) if xlog else (0, len(xs) - 1)

        def X(i, x0=x0, plot_w=plot_w, lo=lo, hi=hi, xs=xs):
            v = math.log10(xs[i]) if xlog else i
            return x0 + 50 + (v - lo) / ((hi - lo) or 1) * (plot_w - 100)

        tick = ylo
        while tick <= yhi + 1e-9:
            body.append(
                f'<line x1="{x0}" y1="{Y(tick):.1f}" x2="{x0 + plot_w}" y2="{Y(tick):.1f}" '
                f'stroke="{theme["grid"]}"/>'
            )
            body.append(
                t(
                    x0 - 8,
                    Y(tick) + 4,
                    f"{tick:.1f}",
                    theme,
                    11,
                    fill=theme["secondary"],
                    anchor="end",
                )
            )
            tick = round(tick + 0.1, 10)
        for i in range(len(xs)):
            for n, line in enumerate(xlabels[i].split("\n")):
                body.append(
                    t(
                        X(i),
                        top + plot_h + 20 + n * 14,
                        line,
                        theme,
                        11,
                        600 if n == 0 else 400,
                        fill=theme["text"] if n == 0 else theme["secondary"],
                        anchor="middle",
                    )
                )
        for j, (_, values) in enumerate(series):
            pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(values))
            body.append(
                f'<polyline points="{pts}" fill="none" stroke="{theme["series"][j]}" '
                'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            )
        for j, (sname, values) in enumerate(series):
            other = series[1 - j][1] if len(series) == 2 else None
            for i, v in enumerate(values):
                body.append(
                    dot(
                        X(i),
                        Y(v),
                        theme["series"][j],
                        theme,
                        r=5,
                        title=f"{xlabels[i].split(chr(10))[0]}, {sname}: {v:.3f}",
                    )
                )
                above = other is None or v > other[i] or (v == other[i] and j == 0)
                if other is not None and v == other[i] and j == 1:
                    continue  # equal values: one label serves both
                body.append(
                    t(
                        X(i),
                        Y(v) + (-13 if above else 22),
                        f"{v:.2f}",
                        theme,
                        12,
                        600,
                        anchor="middle",
                    )
                )
    save(name, title, subtitle, "".join(body), width, height, theme_name)


def stacked(name, title, subtitle, cats, kinds, counts, theme_name, width=980):
    """100% stacked bars; each segment labeled with its share when it fits."""
    theme = THEMES[theme_name]
    lw = label_width(cats, 7.2)
    plot_w = width - lw - 120
    top, bar_h, row_gap = 100, 28, 14
    body = [legend([(k, theme["series"][j], "box") for j, k in enumerate(kinds)], theme)]
    for i, cat in enumerate(cats):
        y = top + i * (bar_h + row_gap)
        total = sum(counts[i])
        body.append(t(24 + lw - 12, y + bar_h / 2 + 4, cat, theme, 13, anchor="end"))
        x = 24 + lw
        for j, c in enumerate(counts[i]):
            w = c / total * plot_w if total else 0
            if w > 0:
                body.append(
                    f'<rect x="{x:.1f}" y="{y}" width="{max(0, w - 2):.1f}" height="{bar_h}" '
                    f'rx="3" fill="{theme["series"][j]}">'
                    f"{tip(f'{cat}: {kinds[j]}, {c} of {total}')}</rect>"
                )
                if w > 40:
                    body.append(
                        t(
                            x + w / 2 - 1,
                            y + bar_h / 2 + 4,
                            f"{c / total:.0%}",
                            theme,
                            12,
                            700,
                            fill=ink_on(theme["series"][j]),
                            anchor="middle",
                        )
                    )
            x += w
        body.append(
            t(
                24 + lw + plot_w + 10,
                y + bar_h / 2 + 4,
                f"{total} misses",
                theme,
                12,
                fill=theme["secondary"],
            )
        )
    save(
        name,
        title,
        subtitle,
        "".join(body),
        width,
        top + len(cats) * (bar_h + row_gap) + 12,
        theme_name,
    )


def unit_grid(name, title, subtitle, groups, kinds, theme_name, width=980, per_line=46):
    """One square per question, a row per group, squares grouped by outcome."""
    theme = THEMES[theme_name]
    size, pitch = 12, 15
    lw = label_width([g for g, _ in groups], 7.2)
    totals = [sum(k == j for _, items in groups for k, _ in items) for j in range(len(kinds))]
    entries = [(f"{kinds[j]} {totals[j]}", theme["series"][j], "box") for j in range(len(kinds))]
    body = [legend(entries[:3], theme), legend(entries[3:], theme, y=96)]
    y = 118
    for gname, items in groups:
        items = sorted(items, key=lambda item: item[0])
        body.append(t(24 + lw - 12, y + 10, gname, theme, 13, anchor="end"))
        for n, (kind, title_text) in enumerate(items):
            x = 24 + lw + (n % per_line) * pitch
            body.append(
                f'<rect x="{x}" y="{y + (n // per_line) * pitch}" width="{size}" height="{size}" '
                f'rx="2.5" fill="{theme["series"][kind]}">{tip(title_text)}</rect>'
            )
        y += math.ceil(len(items) / per_line) * pitch + 12
    save(name, title, subtitle, "".join(body), width, y + 12, theme_name)


def count_bars(name, title, subtitle, cats, series, theme_name, width=980):
    """Horizontal bars of counts, one segment per series, the total at the bar's end."""
    theme = THEMES[theme_name]
    colors = [theme["series"][0], theme["series"][1], theme["context"][0]]
    lw = label_width(cats, 6.8)
    plot_w = width - lw - 90
    top, bar_h, gap = 100, 18, 10
    most = max(sum(values[i] for _, values in series) for i in range(len(cats)))
    body = [
        legend(
            [(lab, colors[j], "box") for j, (lab, vals) in enumerate(series) if any(vals)], theme
        )
    ]
    for i, cat in enumerate(cats):
        y = top + i * (bar_h + gap)
        body.append(t(24 + lw - 12, y + bar_h - 4, cat, theme, 13, anchor="end"))
        x = 24 + lw
        for j, (lab, values) in enumerate(series):
            w = values[i] / most * plot_w
            if w > 0:
                body.append(
                    f'<rect x="{x:.1f}" y="{y}" width="{max(0, w - 2):.1f}" height="{bar_h}" '
                    f'rx="3" fill="{colors[j]}">{tip(f"{cat}: {lab} {values[i]}")}</rect>'
                )
                if w > 24:
                    body.append(
                        t(
                            x + w / 2 - 1,
                            y + bar_h - 5,
                            values[i],
                            theme,
                            11,
                            700,
                            fill=ink_on(colors[j]),
                            anchor="middle",
                        )
                    )
            x += w
        total = sum(values[i] for _, values in series)
        body.append(t(x + 8, y + bar_h - 4, total, theme, 12, 600))
    save(
        name,
        title,
        subtitle,
        "".join(body),
        width,
        top + len(cats) * (bar_h + gap) + 14,
        theme_name,
    )


def refresh_citations():
    """Snapshot the library's citation summary into benchmarks/citations.json."""
    from pramana.citations import summary
    from pramana.corpus import Corpus

    data = summary(Corpus().store, limit=15)
    keep = ("document", "place", "verse", "by", "total")
    snapshot = {
        "label": "Printed scripture references in the library, resolved by pramana.citations",
        "references": data["references"],
        "status": data["status"],
        "passages": [{k: p[k] for k in keep} for p in data["passages"]],
    }
    path = BENCH / "citations.json"
    path.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the charts


TYPE_LABELS = {
    "fact": "Fact",
    "concept": "Concept",
    "objection": "Objection or reply",
    "comparison": "Comparison",
    "followup": "Follow-up",
    "out_of_corpus": "Out of corpus",
}


def short(label):
    for a, b in (
        ("+ ", "+"),
        (" (chat)", ""),
        ("Yoga Vasishtha", "Yoga Vāsiṣṭha"),
        ("Vivekachudamani (Madhavananda)", "Vivekacūḍāmaṇi"),
        ("Ashtavakra Gita", "Aṣṭāvakra Gītā"),
        (", searched", " searched"),
        (", excluded", " excluded"),
    ):
        label = label.replace(a, b)
    return label


SHORT_DOC = {
    "Brihadaranyaka Upanishad": "Bṛhadāraṇyaka",
    "Chandogya Upanishad": "Chāndogya",
    "Svetasvatara Upanishad": "Śvetāśvatara",
    "Mundaka Upanishad": "Muṇḍaka",
    "Taittiriya Upanishad": "Taittirīya",
    "Katha Upanishad": "Kaṭha",
    "Bhagavad Gita": "Gītā",
}


def cite_place(p):
    where = p["place"].replace("Adhyâya ", "")
    verse = f", {p['verse']}" if p["verse"] is not None else ""
    return f"{SHORT_DOC.get(p['document'], p['document'])} {where}{verse}"


def cite_count(p, key):
    return sum(v for a, v in p["by"].items() if key in a.lower())


def main():
    import sys

    OUT.mkdir(parents=True, exist_ok=True)
    if "--citations" in sys.argv:
        refresh_citations()
    cites = load("citations.json")
    v1 = load("advaita/results.json")
    history = load("advaita/history.json")
    spelling = load("advaita/spelling-results.json")
    chapter = load("results.json")
    v01 = load("results-baseline-v0.1.json")
    v2 = load("advaita/v2/results.json")
    models = load("advaita/v2/models.json")
    answers = load("advaita/v2/answers.json")
    dataset = load("advaita/v2/questions.json")
    names = [label for _, label in METHODS]
    metrics = (("Recall@10", "recall_at_10"), ("MRR@10", "mrr_at_10"))

    for theme in THEMES:
        if cites:
            rows = cites["passages"][:12]
            top = rows[0]
            verified = cites["status"].get("verified", 0)
            count_bars(
                "citations",
                f"{cite_place(top)} is the passage the commentaries cite most: "
                f"{top['total']} times",
                f"{cites['references']:,} printed references in Thibaut's translations resolve to "
                f"passages in the library; {verified:,} are checked against the quoted words",
                [cite_place(p) for p in rows],
                [
                    ("Śaṅkara", [cite_count(p, "sankara") for p in rows]),
                    ("Rāmānuja", [cite_count(p, "ramanuja") for p in rows]),
                    (
                        "Others",
                        [
                            p["total"] - cite_count(p, "sankara") - cite_count(p, "ramanuja")
                            for p in rows
                        ],
                    ),
                ],
                theme,
            )
        s = v1["strategies"]
        pair_rows(
            "passage",
            "v1: hybrid finds the most supporting passages, semantic search alone the fewest",
            f"The frozen {v1['questions']} questions · chat's All texts scope · "
            "AI-drafted, unreviewed",
            [
                (m, names, [(s[k]["dev"][key], s[k]["heldout"][key]) for k, _ in METHODS])
                for m, key in metrics
            ],
            [f"Dev ({v1['splits']['dev']})", f"Heldout ({v1['splits']['heldout']})"],
            theme,
        )
        runs = history["runs"]
        lines(
            "library-growth",
            "Every import moves recall; the Yoga Vāsiṣṭha became opt-in because of it",
            "Hybrid Recall@10 on the frozen v1 questions after each change to the library",
            [
                (
                    "Recall@10",
                    list(range(len(runs))),
                    [
                        ("Dev (30)", [r["recall"]["dev"] for r in runs]),
                        ("Heldout (20)", [r["recall"]["heldout"] for r in runs]),
                    ],
                )
            ],
            theme,
            [f"{short(r['label'])}\n{r['passages']:,} passages" for r in runs],
            ylo=0.5,
            yhi=0.8,
        )
        c, b = chapter["strategies"], v01["strategies"]
        pair_rows(
            "chapter",
            "Chapter benchmark: v0.1 → today, little change",
            "20 development-visible questions · Wilson's Vishnu Purana, edition-filtered",
            [(m, names, [(b[k][key], c[k][key]) for k, _ in METHODS]) for m, key in metrics],
            ["v0.1 (587 passages)", "Today"],
            theme,
            arrows=True,
        )
        on, off = spelling["strategies"], history["spelling"]["off"]
        pair_rows(
            "spelling",
            f"Spelling tolerance lifts keyword MRR from {off['lexical']:.2f} to "
            f"{on['lexical']['all']['mrr_at_10']:.2f}",
            "4 questions in modern spellings of old SBE forms (Naciketas for Nakiketas)",
            [
                (
                    "MRR@10",
                    ["Keyword (BM25)", "Hybrid (chat default)"],
                    [
                        (off["lexical"], on["lexical"]["all"]["mrr_at_10"]),
                        (off["hybrid"], on["hybrid"]["all"]["mrr_at_10"]),
                    ],
                )
            ],
            ["Off", "On"],
            theme,
            width=720,
            arrows=True,
        )
        if not v2:
            continue
        s2, n, hy = v2["strategies"], v2["splits"], v2["strategies"]["hybrid"]
        pair_rows(
            "v2-overview",
            f"Hybrid search puts the supporting passage in the top 10 for "
            f"{hy['all']['recall_at_10']:.0%} of questions",
            f"Benchmark v2 · {v2['questions']} answerable questions with exact gold spans · "
            "chat's scopes · AI-drafted, unreviewed",
            [
                (m, names, [(s2[k]["dev"][key], s2[k]["heldout"][key]) for k, _ in METHODS])
                for m, key in metrics
            ],
            [f"Dev ({n['dev']})", f"Heldout ({n['heldout']})"],
            theme,
        )
        types = [k for k in TYPE_LABELS if k in hy["by_type"]]
        hardest = min(types, key=lambda k: hy["by_type"][k]["recall_at_10"])
        grouped(
            "v2-by-type",
            f"{TYPE_LABELS[hardest]}s are hardest to retrieve "
            f"(hybrid {hy['by_type'][hardest]['recall_at_10']:.2f})",
            "Recall@10 by question type, all splits · follow-ups searched with their "
            "reference rewrite",
            [f"{TYPE_LABELS[k]} ({hy['by_type'][k]['questions']})" for k in types],
            [(lab, [s2[m]["by_type"][k]["recall_at_10"] for k in types]) for m, lab in METHODS],
            theme,
        )
        texts = sorted(hy["by_text"], key=lambda k: -hy["by_text"][k]["questions"])
        cols = ["Keyword\nR@10", "Semantic\nR@10", "Hybrid\nR@10"]
        grid = [
            [s2[m]["by_text"][k]["recall_at_10"] for m in ("lexical", "dense", "hybrid")]
            for k in texts
        ]
        if answers:
            cols.append("Answers citing\nthe gold passage")
            for row, k in zip(grid, texts, strict=True):
                row.append(answers["by_text"].get(k, {}).get("gold_cited") or 0.0)
        weakest = min(texts, key=lambda k: hy["by_text"][k]["recall_at_10"])
        strongest = max(texts, key=lambda k: hy["by_text"][k]["recall_at_10"])
        heatmap(
            "v2-by-text",
            f"Strongest on {strongest}, weakest on {weakest}",
            "Benchmark v2 by text, all splits · the text holding the gold span; "
            "comparisons need both thinkers'",
            [f"{k} ({hy['by_text'][k]['questions']})" for k in texts],
            cols,
            grid,
            theme,
            split=3,
        )
        kinds = ["other work", "right work, other chapter", "right chapter, other passage"]
        labels = [
            "Top hit in another work",
            "Right work, other chapter",
            "Right chapter, other passage",
        ]
        counts = [[s2[m]["failure_kinds"].get(k, 0) for k in kinds] for m, _ in METHODS]
        stacked(
            "v2-failures",
            f"{counts[0][0] / sum(counts[0]):.0%} of hybrid misses land in another work entirely",
            "Benchmark v2 · where the top hit landed when the gold span was not in the top 10",
            names,
            labels,
            counts,
            theme,
        )
        if models:
            rows = models["models"]
            keys = list(rows)
            params = [rows[k]["parameters"] for k in keys]
            first, last = (
                rows[k]["strategies"]["hybrid"]["all"]["recall_at_10"] for k in (keys[0], keys[-1])
            )
            lines(
                "models",
                f"{params[-1] / params[0]:.0f}× the parameters buys {last - first:+.3f} "
                "hybrid recall",
                "Benchmark v2, all splits · same passages, chunks and keyword index; only the "
                "embedding model differs",
                [
                    (
                        metric,
                        params,
                        [
                            (
                                "Hybrid (chat default)",
                                [rows[k]["strategies"]["hybrid"]["all"][key] for k in keys],
                            ),
                            (
                                "Semantic only",
                                [rows[k]["strategies"]["dense"]["all"][key] for k in keys],
                            ),
                        ],
                    )
                    for metric, key in metrics
                ],
                theme,
                [
                    f"{k.replace('bge-', 'BGE-')}{' (shipped)' if i == 0 else ''}\n"
                    f"{rows[k]['parameters'] / 1e6:.0f}M params, {rows[k]['dimensions']}d"
                    for i, k in enumerate(keys)
                ],
                xlog=True,
                ylo=0.3,
                yhi=0.8,
            )
        if not (answers and dataset):
            continue
        d, o = answers["details"], answers["overall"]
        outcome = [
            "Answered, cited the gold passage",
            "Answered from other passages",
            "Declined, as expected",
            "Declined though answerable",
            "Failed validation",
        ]

        def kind(r):
            if r["status"] == "error":
                return 4
            if r["expect"] != "grounded":
                return 2 if r["status"] != "grounded" else 1
            if r["status"] != "grounded":
                return 3
            return 0 if r["gold_cited"] == 1 else 1

        groups = [
            (
                f"{TYPE_LABELS[g]} ({sum(r['type'] == g for r in d)})",
                [(kind(r), f"{r['id']}: {outcome[kind(r)]}") for r in d if r["type"] == g],
            )
            for g in ("fact", "concept", "comparison", "objection", "followup", "out_of_corpus")
        ]
        answerable = [r for r in d if r["expect"] == "grounded"]
        ooc = [r for r in d if r["expect"] != "grounded"]
        answered = sum(r["status"] == "grounded" for r in answerable)
        declined = sum(r["status"] == "insufficient_evidence" for r in ooc)
        unit_grid(
            "outcomes",
            f"{answered} of {len(answerable)} answerable questions answered; "
            f"{declined} of {len(ooc)} off-topic ones declined",
            f"Every benchmark v2 question through chat with {answers['model']} · one square per "
            "question · structural checks, not correctness",
            groups,
            outcome,
            theme,
        )
        splits = answers["by_split"]
        rows = [
            (k, lab)
            for k, lab in (
                ("status_accuracy", "Expected outcome"),
                ("grounded_when_answerable", "Answered when answerable"),
                ("refused_when_out_of_corpus", "Declined when off-topic"),
                ("gold_cited", "Cited the gold passage"),
                ("evidence_on_thinker", "Evidence from the named thinker"),
            )
            if o.get(k) is not None
        ]
        pair_rows(
            "answers",
            f"Answers decline every off-topic question and cite the gold passage "
            f"{o['gold_cited']:.0%} of the time",
            f"{o['questions']} questions · {answers['model']} via local Ollama · "
            "structural checks, not correctness",
            [
                (
                    "Share of questions",
                    [lab for _, lab in rows],
                    [(splits["dev"][k] or 0, splits["heldout"][k] or 0) for k, _ in rows],
                )
            ],
            [f"Dev ({splits['dev']['questions']})", f"Heldout ({splits['heldout']['questions']})"],
            theme,
            width=860,
        )
        comps = [r for r in d if "perspectives_for_each_thinker" in r]
        tiles(
            "headline",
            "Benchmark v2 at a glance",
            f"{len(d)} AI-drafted, unreviewed questions over every text · run "
            f"{dataset.get('created', '')}",
            [
                (
                    f"{hy['all']['recall_at_10']:.2f}",
                    "Passage in the top 10",
                    f"hybrid search, {v2['questions']} questions",
                ),
                (
                    f"{declined} / {len(ooc)}",
                    "Off-topic questions declined",
                    "code, trivia, other traditions",
                ),
                (
                    f"{sum(r['perspectives_for_each_thinker'] for r in comps)} / {len(comps)}",
                    "Comparisons with both views",
                    "Śaṅkara and Rāmānuja, separately",
                ),
                (
                    f"{o['latency_seconds']['p50']:.1f} s",
                    "Median answer time",
                    f"{answers['model']} on a local GPU",
                ),
            ],
            theme,
        )
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
