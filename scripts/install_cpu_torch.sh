#!/usr/bin/env bash
# Install Pramana with a CPU-only PyTorch: about 1.1 GB instead of 5-6 GB, and no CUDA.
# For a server without a GPU that should run hybrid (meaning-based) search. It installs
# everything in uv.lock except the NVIDIA libraries, triton and the CUDA torch wheel, then
# adds the CPU build of the SAME torch version from PyTorch's own CPU index (explicit network
# use). The standard wheel cannot even be imported without the NVIDIA libraries.
#
# Afterwards run the environment's own program, `.venv/bin/pramana`: a plain `uv run` or
# `uv sync` would install the CUDA wheels again. For a server that never needs hybrid search,
# scripts/install_without_torch.sh is smaller still (about 200 MB).
set -euo pipefail
cd "$(dirname "$0")/.."

env_dir="${UV_PROJECT_ENVIRONMENT:-.venv}"
version=$(awk '/^name = "torch"$/ {getline; print; exit}' uv.lock | sed -E 's/version = "(.*)"/\1/')
[ -n "$version" ] || { echo "Could not read the torch version from uv.lock" >&2; exit 1; }

names=$(sed -nE 's/^name = "((nvidia-[a-z0-9-]+)|triton|torch)"$/\1/p' uv.lock)
skip=()
for name in $names; do
  skip+=(--no-install-package "$name")
done
echo "Skipping $(echo "$names" | wc -l) packages: $(echo $names)"
uv sync --locked "${skip[@]}"
echo "Adding torch==$version (CPU build) from https://download.pytorch.org/whl/cpu"
uv pip install --python "$env_dir/bin/python" "torch==$version" \
  --index-url https://download.pytorch.org/whl/cpu
"$env_dir/bin/python" -c "import torch; print('torch', torch.__version__, '| cuda:', torch.cuda.is_available())"
echo "Done. Run: $env_dir/bin/pramana ...   (not plain 'uv run')"
