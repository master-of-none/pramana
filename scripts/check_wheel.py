"""Run with a wheel installed, from outside the checkout, without models or corpora."""

from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import pramana
from pramana.api import create_app


def main():
    installed = distribution("pramana-rag")
    assert installed.files and any(str(p).endswith("static/index.html") for p in installed.files)
    assert "/src/pramana/" not in str(Path(pramana.__file__).resolve())
    with TemporaryDirectory(prefix="pramana-wheel-test-") as directory:
        client = TestClient(create_app(Path(directory)))
        assert client.get("/api/status").json()["state"] == "empty"
        page = client.get("/")
        assert page.status_code == 200
        assert "A space for understanding" in page.text
        import re

        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
        assert assets
        for asset in assets:
            assert client.get(asset).status_code == 200
        # Self-hosted fonts and the installable-app manifest and icons ship in the wheel.
        assert any(str(p).endswith(".woff2") for p in installed.files)
        assert client.get("/manifest.webmanifest").json()["name"] == "Pramana"
        assert client.get("/icon.svg").status_code == 200
        assert client.get("/icons/icon-192.png").status_code == 200
        # The curated great sayings ship as package data (none found in an empty library).
        sayings = client.get("/api/sayings").json()
        assert len(sayings) == 4 and not any(s["found"] for s in sayings)
        assert client.post("/api/chat", json={"message": "What is knowledge?"}).status_code == 409
        assert client.post("/api/search", json={"query": "knowledge"}).status_code == 409
        assert client.get("/api/chapters/missing").status_code == 404
    print(
        "Installed wheel: API, chat setup errors, compiled homepage, assets, fonts and "
        "app manifest passed."
    )


if __name__ == "__main__":
    main()
