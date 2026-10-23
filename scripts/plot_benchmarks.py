"""Render the README benchmark charts as static SVG (light and dark) from result files.

Run `uv run python scripts/plot_benchmarks.py` after re-running the benchmarks; every
number comes from `benchmarks/`, never typed into the chart. No plotting dependency:
plain SVG, grouped horizontal bars, values at the bar tips, one legend per chart.
Palette: validated categorical slots 1-3 (blue, orange, aqua) in both modes; light aqua is
below 3:1 on the surface, so every bar carries its value label.
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
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
    },
    "dark": {
        "surface": "#1a1a19",
        "text": "#f0efec",
        "secondary": "#c3c2b7",
        "grid": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70"],
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
    v2 = ROOT / "benchmarks/advaita/v2"
    if (v2 / "results.json").exists():
        plot_v2(json.loads((v2 / "results.json").read_text()), methods)
    if (v2 / "models.json").exists():
        plot_models(json.loads((v2 / "models.json").read_text()))
    if (v2 / "answers.json").exists():
        plot_answers(json.loads((v2 / "answers.json").read_text()))
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


TYPES = {
    "fact": "Fact",
    "concept": "Concept",
    "comparison": "Comparison",
    "objection": "Objection or reply",
    "followup": "Follow-up (rewritten)",
}


def plot_v2(v2, methods):
    s = v2["strategies"]
    names = [label for _, label in methods]
    n = v2["splits"]
    types = [t for t in TYPES if t in s["hybrid"]["by_type"]]
    texts = sorted(s["hybrid"]["by_text"], key=lambda t: -s["hybrid"]["by_text"][t]["questions"])
    for theme in THEMES:
        chart(
            "v2-overview",
            "Advaita benchmark v2: retrieval",
            f"{v2['questions']} answerable questions with exact gold spans · chat's scopes · "
            "AI-drafted, unreviewed",
            [
                (
                    metric,
                    names,
                    [
                        (split, [s[m][split.lower()][key] for m, _ in methods])
                        for split in ("Dev", "Heldout")
                    ],
                )
                for metric, key in (("Recall@10", "recall_at_10"), ("MRR@10", "mrr_at_10"))
            ],
            [f"Dev ({n['dev']})", f"Heldout ({n['heldout']})"],
            theme,
            width=980,
        )
        chart(
            "v2-by-type",
            "Recall@10 by question type",
            "All splits · counts in labels · follow-ups searched with their reference rewrite",
            [
                (
                    "Recall@10",
                    [f"{TYPES[t]} ({s['hybrid']['by_type'][t]['questions']})" for t in types],
                    [
                        (label, [s[m]["by_type"][t]["recall_at_10"] for t in types])
                        for m, label in methods
                    ],
                )
            ],
            names,
            theme,
            width=820,
        )
        chart(
            "v2-by-text",
            "Recall@10 by text",
            "All splits · the text holding the gold span (comparisons need both thinkers)",
            [
                (
                    "Recall@10",
                    [f"{t} ({s['hybrid']['by_text'][t]['questions']})" for t in texts],
                    [
                        (label, [s[m]["by_text"][t]["recall_at_10"] for t in texts])
                        for m, label in methods
                    ],
                )
            ],
            names,
            theme,
            width=860,
        )


def plot_models(models):
    rows = models["models"]
    names = list(rows)
    labels = [
        f"{n.replace('bge-', 'BGE-')} ({r['parameters'] / 1e6:.0f}M, {r['dimensions']}d)"
        for n, r in rows.items()
    ]
    for theme in THEMES:
        chart(
            "models",
            "Embedding models on the v2 benchmark",
            "Same passages, chunks and keyword index; only the embedding model differs",
            [
                (
                    metric,
                    ["Semantic only", "Hybrid (chat default)"],
                    [
                        (label, [rows[n]["strategies"][s]["all"][key] for s in ("dense", "hybrid")])
                        for n, label in zip(names, labels, strict=True)
                    ],
                )
                for metric, key in (("Recall@10", "recall_at_10"), ("MRR@10", "mrr_at_10"))
            ],
            labels,
            theme,
            width=980,
        )


def plot_answers(answers):
    o, splits = answers["overall"], answers["by_split"]
    metrics = [
        ("status_accuracy", "Expected status"),
        ("grounded_when_answerable", "Answered when answerable"),
        ("refused_when_out_of_corpus", "Declined when out of corpus"),
        ("gold_cited", "Cited the gold passage"),
        ("evidence_on_thinker", "Evidence from the named thinker"),
    ]
    metrics = [(k, label) for k, label in metrics if o.get(k) is not None]
    for theme in THEMES:
        chart(
            "answers",
            f"Answer quality with {answers['model']}",
            f"{o['questions']} questions · local Ollama · structural checks, not correctness",
            [
                (
                    "Share of questions",
                    [label for _, label in metrics],
                    [
                        (split, [splits[split.lower()][k] or 0 for k, _ in metrics])
                        for split in ("Dev", "Heldout")
                    ],
                )
            ],
            [
                f"Dev ({splits['dev']['questions']})",
                f"Heldout ({splits['heldout']['questions']})",
            ],
            theme,
            width=820,
        )


if __name__ == "__main__":
    main()
