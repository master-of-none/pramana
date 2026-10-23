"""Compare pinned embedding models on a passage benchmark, each in an isolated library copy.

    uv run python scripts/compare_embeddings.py --download     # fetch candidates once
    HF_HUB_OFFLINE=1 uv run python scripts/compare_embeddings.py

The product keeps its pinned BGE-small; nothing here changes the library or its index.
For each model the script copies `pramana.sqlite3` to
`PRAMANA_HOME/benchmarks/embeddings/<name>/`, re-embeds the stored passages there and runs
`evaluate_passages` on the copy. Passages are reused unchanged, so keyword search and
chunk boundaries are identical and only the embedding model differs; a model whose
tokenizer vocabulary differs from the production one is refused, because the stored
chunks were sized with that tokenizer. Candidates are downloaded only with `--download`
(BGE-base 438 MB, BGE-large 1.34 GB), into `PRAMANA_HOME/benchmark-models/`.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from pramana import Corpus, Retriever
from pramana.config import MODEL_ID, MODEL_REVISION, QUERY_PROMPT, data_dir
from pramana.evaluation import evaluate_passages

# Pinned revisions (Hugging Face commits, checked 23 October 2026); all MIT-licensed.
MODELS = {
    "bge-small": ("BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"),
    "bge-base": ("BAAI/bge-base-en-v1.5", "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"),
    "bge-large": ("BAAI/bge-large-en-v1.5", "d4aa6901d3a41ba39fb536a557fa166f842b0e09"),
}
PATTERNS = ["*.json", "*.txt", "model.safetensors", "1_Pooling/*"]


class Candidate:
    def __init__(self, path: Path, model: str, revision: str, device: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(str(path), local_files_only=True, device=device)
        self.tokenizer = self.model.tokenizer
        self.identity = {"model": model, "revision": revision, "query_prompt": QUERY_PROMPT}

    def documents(self, texts):
        return self.model.encode(
            texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True
        ).astype(np.float32)

    def query(self, text):
        return self.documents([QUERY_PROMPT + text])[0]


def model_dir(home: Path, name: str, download: bool) -> Path:
    model, revision = MODELS[name]
    if (model, revision) == (MODEL_ID, MODEL_REVISION):
        return home / "models" / MODEL_REVISION  # the product's own copy
    target = home / "benchmark-models" / revision
    if not (target / "model.safetensors").exists():
        if not download:
            sys.exit(f"{model} is not downloaded. Run this script once with --download.")
        from huggingface_hub import snapshot_download

        snapshot_download(model, revision=revision, local_dir=target, allow_patterns=PATTERNS)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    v2 = Path("benchmarks/advaita/v2")
    parser.add_argument("--dataset", type=Path, default=v2 / "questions.json")
    parser.add_argument("--output", type=Path, default=v2 / "models.json")
    parser.add_argument("--download", action="store_true", help="fetch missing candidates")
    parser.add_argument("--device", default=None, help="cpu or cuda (default: cuda if present)")
    args = parser.parse_args()
    import torch

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    home = data_dir()
    production = Candidate(home / "models" / MODEL_REVISION, MODEL_ID, MODEL_REVISION, "cpu")
    results = {}
    for name in args.models:
        model, revision = MODELS[name]
        embedder = Candidate(model_dir(home, name, args.download), model, revision, device)
        if embedder.tokenizer.get_vocab() != production.tokenizer.get_vocab():
            sys.exit(f"{model} uses a different tokenizer; stored chunks would not fit it.")
        work = home / "benchmarks" / "embeddings" / name
        work.mkdir(parents=True, exist_ok=True)
        target = work / "pramana.sqlite3"
        target.unlink(missing_ok=True)
        with sqlite3.connect(home / "pramana.sqlite3") as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        with sqlite3.connect(target) as db:
            rows = db.execute("SELECT id, json_extract(data, '$.text') FROM passages").fetchall()
            started = time.perf_counter()
            vectors = embedder.documents([text for _, text in rows])
            seconds = time.perf_counter() - started
            db.executemany(
                "UPDATE passages SET vector=? WHERE id=?",
                [(v.tobytes(), pid) for (pid, _), v in zip(rows, vectors, strict=True)],
            )
            config = json.loads(
                db.execute("SELECT value FROM meta WHERE key='index_config'").fetchone()[0]
            )
            config["embedding"] = embedder.identity
            config = json.dumps(config, sort_keys=True)
            db.execute("UPDATE meta SET value=? WHERE key='index_config'", (config,))
        retriever = Retriever(Corpus(work), embedder=embedder)
        started = time.perf_counter()
        report = evaluate_passages(retriever, args.dataset)
        results[name] = {
            "model": model,
            "revision": revision,
            "dimensions": int(vectors.shape[1]),
            "parameters": sum(p.numel() for p in embedder.model.parameters()),
            "device": device,
            "passages": len(rows),
            "embedding_seconds": round(seconds, 1),
            "benchmark_seconds": round(time.perf_counter() - started, 1),
            "strategies": {
                s: {k: v for k, v in r.items() if k not in ("details", "failures")}
                for s, r in report["strategies"].items()
            },
        }
        print(name, json.dumps({s: r["all"] for s, r in results[name]["strategies"].items()}))
    summary = {
        "label": "Embedding model comparison on the v2 passage benchmark (unreviewed dataset)",
        "dataset_sha256": report["dataset_sha256"],
        "note": "Passages, chunking and keyword search identical across models; only the "
        "embedding model differs. Vectors computed on the stated device.",
        "models": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
