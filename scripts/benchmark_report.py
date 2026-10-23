"""Write a self-contained HTML report from the v2 benchmark result files.

    uv run python scripts/benchmark_report.py [--output PATH]

Every number comes from `benchmarks/advaita/v2/` (results, models, answers when present)
and the dataset itself; charts are the SVGs from `scripts/plot_benchmarks.py`, embedded.
The default output is `.pramana/reports/benchmark.html`, outside version control.
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "benchmarks" / "advaita" / "v2"
CHARTS = ROOT / "docs" / "images" / "benchmarks"
METHODS = (("hybrid", "Hybrid"), ("lexical", "Keyword"), ("dense", "Semantic"))
METRICS = ("recall_at_10", "mrr_at_10")

CSS = """
:root { --bg:#fcfcfb; --fg:#0b0b0b; --muted:#52514e; --line:#e4e3df; --card:#f4f3ef;
  --bad:#b3261e; --good:#1b6e3a; color-scheme: light dark; }
@media (prefers-color-scheme: dark) { :root { --bg:#1a1a19; --fg:#f0efec; --muted:#c3c2b7;
  --line:#383835; --card:#232321; --bad:#f2938c; --good:#7fcf9a; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }
main { max-width:1040px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:26px; margin:0 0 4px; } h2 { font-size:19px; margin:36px 0 8px; }
p.lead, .muted { color:var(--muted); }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px;
  margin:18px 0; }
.tile { background:var(--card); border-radius:10px; padding:12px 14px; }
.tile b { display:block; font-size:24px; font-variant-numeric:tabular-nums; }
.tile span { color:var(--muted); font-size:13px; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; margin:8px 0 4px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { color:var(--muted); font-weight:600; }
td.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
picture img, .chart svg { width:100%; height:auto; }
details { margin:6px 0; } summary { cursor:pointer; color:var(--muted); }
code { font-size:13px; }
"""


def pct(v):
    return "–" if v is None else f"{v:.2f}"


def table(head, rows, numeric=()):
    out = ["<div class='scroll'><table><tr>"]
    out += [f"<th>{escape(h)}</th>" for h in head]
    out.append("</tr>")
    for row in rows:
        out.append("<tr>")
        for i, cell in enumerate(row):
            klass = " class='n'" if i in numeric else ""
            out.append(f"<td{klass}>{cell}</td>")
        out.append("</tr>")
    out.append("</table></div>")
    return "".join(out)


def chart(name):
    light, dark = CHARTS / f"{name}-light.svg", CHARTS / f"{name}-dark.svg"
    if not light.exists():
        return ""
    import base64

    def uri(path):
        return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()

    return (
        f"<picture><source media='(prefers-color-scheme: dark)' srcset='{uri(dark)}'>"
        f"<img alt='{escape(name)} chart' src='{uri(light)}'></picture>"
    )


def retrieval(res, questions):
    s = res["strategies"]
    out = ["<h2>Retrieval: overall</h2>", chart("v2-overview")]
    rows = []
    for key, label in METHODS:
        r = s[key]
        cells = [r[split][m] for split in ("dev", "heldout", "all") for m in METRICS]
        rows.append([label] + [pct(v) for v in cells])
    out.append(
        table(
            ["Method", "Dev R@10", "Dev MRR", "Heldout R@10", "Heldout MRR", "All R@10", "All MRR"],
            rows,
            numeric=range(1, 7),
        )
    )
    for title, key, name in (
        ("By question type", "by_type", "v2-by-type"),
        ("By text", "by_text", "v2-by-text"),
    ):
        out += [f"<h2>{title}</h2>", chart(name)]
        groups = sorted(s["hybrid"][key], key=lambda g: -s["hybrid"][key][g]["questions"])
        out.append(
            table(
                ["Group", "Questions"] + [f"{label} R@10" for _, label in METHODS] + ["Hybrid MRR"],
                [
                    [escape(g), s["hybrid"][key][g]["questions"]]
                    + [pct(s[m][key][g]["recall_at_10"]) for m, _ in METHODS]
                    + [pct(s["hybrid"][key][g]["mrr_at_10"])]
                    for g in groups
                ],
                numeric=range(1, 6),
            )
        )
    out.append("<h2>Failure analysis (hybrid)</h2>")
    h = s["hybrid"]
    depth = h["failure_depth"]
    out.append(
        f"<p>{len(h['failures'])} of {res['questions']} questions miss at least one gold span "
        f"in the top 10. {depth['found_at_11_to_50']} are found at ranks 11–50; "
        f"{depth['not_in_top_50']} are not in the top 50 at all.</p>"
    )
    out.append(
        table(
            ["Where the top hit landed", "Failures"],
            [[escape(k), v] for k, v in sorted(h["failure_kinds"].items(), key=lambda x: -x[1])],
            numeric=(1,),
        )
    )
    if "comparison_coverage" in h:
        c = h["comparison_coverage"]
        out.append(
            f"<p>Comparisons, both thinkers' spans in the top 10: {c['both']}; one: {c['one']}; "
            f"neither: {c['neither']}.</p>"
        )
    if "followup_raw" in h:
        out.append(
            f"<p>Follow-ups searched as asked: R@10 {pct(h['followup_raw']['recall_at_10'])}; with "
            f"the reference rewrite: {pct(h['followup_rewritten']['recall_at_10'])}. Chat "
            "rewrites follow-ups with the model before searching.</p>"
        )
    by_id = {q["id"]: q for q in questions}
    rows = []
    for r in sorted(h["failures"], key=lambda r: (r.get("text") or "", r["id"])):
        q = by_id[r["id"]]
        gold = "<br>".join(escape(g["quote"][:110]) for g in q["gold"][:2])
        rows.append(
            [
                f"<code>{r['id']}</code>",
                escape(q.get("type", "")),
                escape(q["query"]),
                gold,
                "–" if r["best_rank_at_50"] is None else r["best_rank_at_50"],
                escape(r["miss"]),
                "<br>".join(escape(t) for t in r["top"]),
            ]
        )
    out.append("<details><summary>Every hybrid failure</summary>")
    out.append(
        table(
            ["ID", "Type", "Question", "Gold span", "Best rank ≤50", "Top hit", "Top 3"],
            rows,
            numeric=(4,),
        )
    )
    out.append("</details>")
    out.append("<h2>Out-of-corpus probes</h2>")
    out.append(
        "<p class='muted'>Retrieval always returns something; these show what is nearest. "
        "Declining is measured in the answer evaluation.</p>"
    )
    out.append(
        table(
            ["ID", "Kind", "Question", "Nearest documents"],
            [
                [
                    f"<code>{o['id']}</code>",
                    escape(o.get("kind", "")),
                    escape(o["query"]),
                    escape(", ".join(dict.fromkeys(o["retrieved"]))),
                ]
                for o in res["out_of_corpus"]
            ],
        )
    )
    return out


def models(m):
    rows = []
    for r in m["models"].values():
        rows.append(
            [
                escape(r["model"]),
                f"{r['parameters'] / 1e6:.0f}M",
                r["dimensions"],
                pct(r["strategies"]["dense"]["dev"]["recall_at_10"]),
                pct(r["strategies"]["dense"]["heldout"]["recall_at_10"]),
                pct(r["strategies"]["hybrid"]["dev"]["recall_at_10"]),
                pct(r["strategies"]["hybrid"]["heldout"]["recall_at_10"]),
                pct(r["strategies"]["hybrid"]["all"]["mrr_at_10"]),
                f"{r['embedding_seconds']:.0f}s ({escape(r['device'])})",
            ]
        )
    return [
        "<h2>Embedding models</h2>",
        f"<p class='muted'>{escape(m['note'])}</p>",
        chart("models"),
        table(
            [
                "Model",
                "Params",
                "Dims",
                "Semantic dev R@10",
                "Semantic heldout R@10",
                "Hybrid dev R@10",
                "Hybrid heldout R@10",
                "Hybrid MRR",
                f"Embed {next(iter(m['models'].values()))['passages']:,} passages",
            ],
            rows,
            numeric=range(1, 9),
        ),
    ]


def answers(a):
    keys = (
        ("status_accuracy", "Expected status"),
        ("grounded_when_answerable", "Answered"),
        ("refused_when_out_of_corpus", "Declined OOC"),
        ("gold_cited", "Cited gold"),
        ("evidence_on_thinker", "On-thinker evidence"),
    )

    def rows(groups):
        return [
            [escape(g), v["questions"]]
            + [pct(v[k]) for k, _ in keys]
            + [f"{v['latency_seconds'].get('p50', 0):.0f}s", v["errors"]]
            for g, v in groups.items()
        ]

    head = ["Group", "Questions"] + [label for _, label in keys] + ["Median time", "Errors"]
    out = [
        "<h2>Answer quality</h2>",
        f"<p class='muted'>Model {escape(str(a['model']))}, claim check "
        f"{'on' if a['check'] else 'off'}. These are structural checks: whether the status "
        "matches, whether a cited passage contains a gold span, whether evidence comes from the "
        "named thinker. They do not establish that an answer is correct.</p>",
        chart("answers"),
        table(head, rows({"All": a["overall"], **a["by_split"]}), numeric=range(1, 9)),
        "<h3>By type</h3>",
        table(head, rows(a["by_type"]), numeric=range(1, 9)),
        "<h3>By text</h3>",
        table(head, rows(a["by_text"]), numeric=range(1, 9)),
    ]
    if a.get("comparisons_with_each_view") is not None:
        out.append(
            f"<p>Comparisons with a view for each expected thinker: "
            f"{pct(a['comparisons_with_each_view'])}.</p>"
        )
    misses = [d for d in a["details"] if not d["status_ok"] or d.get("gold_cited") == 0]
    out.append(f"<details><summary>{len(misses)} answers that missed</summary>")
    out.append(
        table(
            ["ID", "Type", "Expected", "Got", "Cited gold", "Answer (start)"],
            [
                [
                    f"<code>{d['id']}</code>",
                    escape(d["type"] or ""),
                    escape(d["expect"]),
                    escape(d["status"]),
                    pct(d["gold_cited"]),
                    escape((d["answer"] or "")[:220]),
                ]
                for d in misses
            ],
        )
    )
    out.append("</details>")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, default=ROOT / ".pramana/reports/benchmark.html")
    args = parser.parse_args()
    dataset = json.loads((V2 / "questions.json").read_text(encoding="utf-8"))
    res = json.loads((V2 / "results.json").read_text(encoding="utf-8"))
    questions = dataset["questions"]
    answerable = [q for q in questions if q["type"] != "out_of_corpus"]
    h = res["strategies"]["hybrid"]
    tiles = [
        (len(questions), "questions"),
        (len({q["text"] for q in answerable}), "text groups"),
        (len({q["type"] for q in questions}), "question types"),
        (f"{h['heldout']['recall_at_10']:.2f}", "hybrid heldout R@10"),
        (f"{h['heldout']['mrr_at_10']:.2f}", "hybrid heldout MRR"),
        (res["review"].get("reviewed", 0), "human-reviewed"),
    ]
    body = [
        "<h1>Pramana benchmark report</h1>",
        f"<p class='lead'>{escape(dataset['label'])}. Dataset "
        f"<code>{res['dataset_sha256'][:12]}</code>; index "
        f"{escape(res['index']['embedding']['model'])}; scope: {escape(res['scope'])}.</p>",
        "<div class='tiles'>"
        + "".join(f"<div class='tile'><b>{v}</b><span>{escape(k)}</span></div>" for v, k in tiles)
        + "</div>",
        f"<p class='muted'>{escape(dataset['split_policy'])}</p>",
    ]
    body += retrieval(res, questions)
    if (V2 / "models.json").exists():
        body += models(json.loads((V2 / "models.json").read_text(encoding="utf-8")))
    if (V2 / "answers.json").exists():
        body += answers(json.loads((V2 / "answers.json").read_text(encoding="utf-8")))
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Pramana benchmarks</title><style>{CSS}</style></head><body><main>"
        + "\n".join(body)
        + "</main></body></html>\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
