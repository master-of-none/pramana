import json
from pathlib import Path

import numpy as np
from huggingface_hub import snapshot_download

from pramana.config import MODEL_ID, MODEL_REVISION, QUERY_PROMPT
from pramana.errors import PramanaError


def setup_model(home: Path) -> Path:
    """The only model operation permitted to access the network."""
    target = home / "models" / MODEL_REVISION
    snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=target,
        allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*"],
    )
    (target / "pramana-model.json").write_text(
        json.dumps({"model": MODEL_ID, "revision": MODEL_REVISION}), encoding="utf-8"
    )
    return target


class LocalEmbedder:
    def __init__(self, home: Path):
        target = home / "models" / MODEL_REVISION
        marker = target / "pramana-model.json"
        if not marker.exists():
            raise PramanaError("Local model is missing. Run: pramana model setup")
        if json.loads(marker.read_text()) != {"model": MODEL_ID, "revision": MODEL_REVISION}:
            raise PramanaError("Model metadata is incompatible. Run: pramana model setup")
        from sentence_transformers import SentenceTransformer

        try:
            self.model = SentenceTransformer(str(target), local_files_only=True, device="cpu")
        except (OSError, ValueError) as exc:
            raise PramanaError("Model cache is incomplete. Run: pramana model setup") from exc
        self.tokenizer = self.model.tokenizer

    @property
    def identity(self) -> dict:
        return {"model": MODEL_ID, "revision": MODEL_REVISION, "query_prompt": QUERY_PROMPT}

    def documents(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype(np.float32)

    def query(self, text: str) -> np.ndarray:
        if (
            len(self.tokenizer.encode(QUERY_PROMPT + text, verbose=False))
            > self.model.max_seq_length
        ):
            raise PramanaError("Query exceeds the model's token limit. Shorten the search terms.")
        return self.documents([QUERY_PROMPT + text])[0]
