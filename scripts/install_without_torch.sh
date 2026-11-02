#!/usr/bin/env bash
# Install Pramana without PyTorch and the CUDA libraries: about 200 MB instead of 5-6 GB.
# For a small server that only serves excerpts (`pramana serve --agent-only`) from a library
# and search index built elsewhere. It cannot build an index or run hybrid topic search;
# lexical topic search (`strategy=lexical`) and everything else works.
#
# Afterwards run the environment's own program, `.venv/bin/pramana`, or `uv run --no-sync`:
# a plain `uv run` would sync the environment and install the skipped packages again.
set -euo pipefail
cd "$(dirname "$0")/.."

names=$(sed -nE 's/^name = "((nvidia-[a-z0-9-]+)|triton|torch|sentence-transformers|transformers|scikit-learn|scipy)"$/\1/p' uv.lock)
skip=()
for name in $names; do
  skip+=(--no-install-package "$name")
done
echo "Skipping $(echo "$names" | wc -l) packages: $(echo $names)"
uv sync --locked "${skip[@]}"
echo "Done. Run: .venv/bin/pramana ...   (not plain 'uv run', which would reinstall them)"
