import os
from pathlib import Path

MODEL_ID = "BAAI/bge-small-en-v1.5"
# Fixed upstream revision, so a future Hub update cannot silently change an index.
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
QUERY_PROMPT = "Represent this sentence for searching relevant passages: "
CHUNK_CONFIG = {"version": 2, "target_tokens": 384, "max_tokens": 448, "overlap_tokens": 48}


def data_dir() -> Path:
    return Path(os.environ.get("PRAMANA_HOME", ".pramana")).resolve()
