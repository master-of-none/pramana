"""Check relative links and #anchors in the repository's Markdown files (no network).

Run `uv run python scripts/check_links.py`; exits non-zero and lists broken links.
External http(s)/mailto links are not fetched.
"""

import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", r"\1", heading.strip().lower())
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text))


def anchors(path: Path) -> set[str]:
    found, counts, fenced = set(), {}, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and (m := re.match(r"#{1,6}\s+(.*)", line)):
            base = slug(m[1])
            n = counts.get(base, 0)
            found.add(base if n == 0 else f"{base}-{n}")
            counts[base] = n + 1
    return found


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    broken = []
    for name in files:
        path = ROOT / name
        text = re.sub(r"(?s)```.*?```", "", path.read_text(encoding="utf-8"))
        for m in LINK.finditer(text):
            target = m[1] or m[2]
            if re.match(r"[a-z]+:", target):
                continue
            file_part, _, anchor = target.partition("#")
            dest = (path.parent / file_part).resolve() if file_part else path
            if not dest.exists():
                broken.append(f"{name}: {target} (missing file)")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                broken.append(f"{name}: {target} (missing anchor)")
    print("\n".join(broken) or f"All links resolve in {len(files)} Markdown files.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
