"""Render the README benchmark charts as static SVG (light and dark) from result files.

Run `uv run python scripts/plot_benchmarks.py` after re-running the benchmarks; every
number comes from `benchmarks/`, never typed into the chart. No plotting dependency:
plain SVG, grouped horizontal bars, values at the bar tips, one legend per chart.
Palette: validated categorical slots 1-2 (blue, orange) in both modes.
"""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "benchmarks"
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "text": "#0b0b0b",
        "secondary": "#52514e",
        "grid": "#e4e3df",
        "series": ["#2a78d6", "#eb6834"],
    },
    "dark": {
        "surface": "#1a1a19",
        "text": "#f0efec",
        "secondary": "#c3c2b7",
        "grid": "#383835",
        "series": ["#3987e5", "#d95926"],
    },
}
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
BAR, GAP, GROUP_GAP = 18, 2, 16


def bar(x, y, w, h, color):
    """4px rounded data-end, square at the baseline."""
    r = min(4, w / 2)
    if w <= 0:
        return ""
    return (
        f'<path d="M{x},{y} h{w - r} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r} '
        f'a{r},{r} 0 0 1 -{r},{r} h-{w - r} z" fill="{color}"/>'
    )


def panel(x0, y0, width, title, categories, series, theme, fmt="{:.2f}"):
    """A grouped horizontal bar panel on a 0-1 scale; returns (svg, height)."""
    # Size the label column to the longest label (~7px per character at 13px).
    label_w = max(190, int(7.2 * max(len(c) for c in categories)) + 24)
    plot_w = width - label_w - 50
    parts = [
        f'<text x="{x0}" y="{y0}" font-size="14" font-weight="600" fill="{theme["text"]}">'
        f"{escape(title)}</text>"
    ]
    top = y0 + 18
    group_h = len(series) * (BAR + GAP) - GAP
    height = len(categories) * (group_h + GROUP_GAP)
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        x = x0 + label_w + tick * plot_w
        parts.append(
            f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + height - GROUP_GAP}" '
            f'stroke="{theme["grid"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x}" y="{top + height + 2}" font-size="11" text-anchor="middle" '
            f'fill="{theme["secondary"]}">{tick:g}</text>'
        )
    for i, category in enumerate(categories):
        gy = top + i * (group_h + GROUP_GAP)
        parts.append(
            f'<text x="{x0 + label_w - 12}" y="{gy + group_h / 2 + 4}" font-size="13" '
            f'text-anchor="end" fill="{theme["text"]}">{escape(category)}</text>'
        )
        for j, (_, values) in enumerate(series):
            v = values[i]
            y = gy + j * (BAR + GAP)
            w = v * plot_w
            parts.append(bar(x0 + label_w, y, w, BAR, theme["series"][j]))
            parts.append(
                f'<text x="{x0 + label_w + w + 6}" y="{y + BAR / 2 + 4}" font-size="12" '
                f'font-weight="600" fill="{theme["text"]}">{fmt.format(v)}</text>'
            )
    return "\n".join(parts), height + 34


def chart(name, title, subtitle, panels, legend, theme_name, width=720):
    theme = THEMES[theme_name]
    body, y = [], 92
    columns = len(panels)
    col_w = width / columns if columns > 1 else width
    tallest = 0
    for k, (ptitle, categories, series) in enumerate(panels):
        svg, h = panel(24 + k * col_w, y, col_w - 24, ptitle, categories, series, theme)
        body.append(svg)
        tallest = max(tallest, h)
    height = y + tallest + 24
    keys, lx = [], 24
    for j, label in enumerate(legend):
        keys.append(
            f'<rect x="{lx}" y="58" width="12" height="12" rx="3" fill="{theme["series"][j]}"/>'
            f'<text x="{lx + 18}" y="68" font-size="12" fill="{theme["secondary"]}">'
            f"{escape(label)}</text>"
        )
        lx += 18 + 8 * len(label) + 28
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" font-family="{FONT}" role="img" aria-labelledby="t d">
<title id="t">{escape(title)}</title><desc id="d">{escape(subtitle)}</desc>
<rect width="{width}" height="{height}" rx="10" fill="{theme["surface"]}"/>
<text x="24" y="30" font-size="17" font-weight="700" fill="{theme["text"]}">{escape(title)}</text>
<text x="24" y="48" font-size="12" fill="{theme["secondary"]}">{escape(subtitle)}</text>
{"".join(keys)}
{chr(10).join(body)}
</svg>
"""
    (OUT / f"{name}-{theme_name}.svg").write_text(svg, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    adv = json.loads((ROOT / "benchmarks/advaita/results.json").read_text())
    history = json.loads((ROOT / "benchmarks/advaita/history.json").read_text())
    spelling = json.loads((ROOT / "benchmarks/advaita/spelling-results.json").read_text())
    chapter = json.loads((ROOT / "benchmarks/results.json").read_text())
    v01 = json.loads((ROOT / "benchmarks/results-baseline-v0.1.json").read_text())
    methods = [
        ("hybrid", "Hybrid (chat default)"),
        ("lexical", "Keyword (BM25)"),
        ("dense", "Semantic (BGE-small)"),
    ]
    names = [label for _, label in methods]
    s = adv["strategies"]
    for theme in THEMES:
        chart(
            "passage",
            "Advaita passage benchmark",
            f"{adv['questions']} questions with exact gold spans · chat's All texts scope · "
            "AI-drafted, unreviewed",
            [
                (
                    "Recall@10",
                    names,
                    [
                        ("Dev", [s[m]["dev"]["recall_at_10"] for m, _ in methods]),
                        ("Heldout", [s[m]["heldout"]["recall_at_10"] for m, _ in methods]),
                    ],
                ),
                (
                    "MRR@10",
                    names,
                    [
                        ("Dev", [s[m]["dev"]["mrr_at_10"] for m, _ in methods]),
                        ("Heldout", [s[m]["heldout"]["mrr_at_10"] for m, _ in methods]),
                    ],
                ),
            ],
            ["Dev (30)", "Heldout (20)"],
            theme,
            width=980,
        )
        runs = history["runs"]
        chart(
            "library-growth",
            "Hybrid Recall@10 as the library grew",
            "Same 50 questions; the opt-in Yoga Vāsiṣṭha crowds results unless excluded",
            [
                (
                    "Recall@10",
                    [f"{r['label']} ({r['passages']:,})" for r in runs],
                    [
                        ("Dev", [r["recall"]["dev"] for r in runs]),
                        ("Heldout", [r["recall"]["heldout"] for r in runs]),
                    ],
                )
            ],
            ["Dev (30)", "Heldout (20)"],
            theme,
            width=820,
        )
        c = chapter["strategies"]
        chart(
            "chapter",
            "Chapter benchmark (Vishnu Purana, edition-filtered)",
            "20 development-visible questions · v0.1 index (587 passages) vs today's full index",
            [
                (
                    "Recall@10",
                    names,
                    [
                        ("v0.1", [v01["strategies"][m]["recall_at_10"] for m, _ in methods]),
                        ("Today", [c[m]["recall_at_10"] for m, _ in methods]),
                    ],
                ),
                (
                    "MRR@10",
                    names,
                    [
                        ("v0.1", [v01["strategies"][m]["mrr_at_10"] for m, _ in methods]),
                        ("Today", [c[m]["mrr_at_10"] for m, _ in methods]),
                    ],
                ),
            ],
            ["v0.1 (Oct 14)", "Today"],
            theme,
            width=980,
        )
        on = spelling["strategies"]
        off = history["spelling"]["off"]
        chart(
            "spelling",
            "Spelling tolerance (diagnostic)",
            "4 questions in modern spellings of old SBE forms (Naciketas for Nakiketas) · MRR@10",
            [
                (
                    "MRR@10",
                    ["Keyword (BM25)", "Hybrid (chat default)"],
                    [
                        ("Off", [off["lexical"], off["hybrid"]]),
                        (
                            "On",
                            [on["lexical"]["all"]["mrr_at_10"], on["hybrid"]["all"]["mrr_at_10"]],
                        ),
                    ],
                )
            ],
            ["Spelling tolerance off", "On"],
            theme,
            width=720,
        )
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
