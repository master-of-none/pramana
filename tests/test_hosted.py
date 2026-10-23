import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.answering import Answerer
from pramana.api import create_app
from pramana.hosted import Admission, HostedGuard, Limits, Refused, TurnstileVerifier


class Verifier:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, 0

    async def verify(self, token, ip):
        self.calls += 1
        return self.ok and token == "good"


class CountingProvider:
    model = "fixture"

    def __init__(self):
        self.calls = 0

    async def chat(self, messages, schema):
        self.calls += 1
        return {
            "answer": "Vishnu preserves the universe.",
            "status": "grounded",
            "evidence_ids": ["E1"],
        }


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.now


def admission(tmp_path, clock=None, **limits):
    return Admission(tmp_path / "quota.sqlite3", "secret", Limits(**limits), clock or Clock())


def test_limits_duplicates_rollover_and_pause(tmp_path):
    clock = Clock()
    a = admission(tmp_path, clock, global_per_day=3, visitor_per_day=2, visitor_per_minute=5)
    a.admit("1.1.1.1", "request-0001", {"m": "a"})
    with pytest.raises(Refused) as same:
        a.admit("1.1.1.1", "request-0001", {"m": "a"})
    with pytest.raises(Refused) as other:
        a.admit("1.1.1.1", "request-0001", {"m": "b"})
    assert same.value.status_code == other.value.status_code == 409
    a.admit("1.1.1.1", "request-0002", {"m": "c"})
    with pytest.raises(Refused, match="You have used") as mine:
        a.admit("1.1.1.1", "request-0003", {"m": "d"})
    assert mine.value.status_code == 429 and mine.value.retry_after == 12 * 3600
    a.admit("2.2.2.2", "request-0004", {"m": "e"})
    with pytest.raises(Refused, match="Today's questions"):
        a.admit("3.3.3.3", "request-0005", {"m": "f"})
    clock.now += timedelta(days=1)  # Midnight UTC resets both caps.
    a.admit("1.1.1.1", "request-0006", {"m": "g"})
    a.set_paused(True)
    with pytest.raises(Refused, match="paused"):
        a.admit("4.4.4.4", "request-0007", {"m": "h"})
    assert "1.1.1.1" not in (tmp_path / "quota.sqlite3").read_bytes().decode("latin-1")


def test_burst_limit_and_daily_visitor_key_rotation(tmp_path):
    clock = Clock()
    a = admission(tmp_path, clock, visitor_per_minute=2)
    a.admit("9.9.9.9", "burst-00001", {"m": 1})
    a.admit("9.9.9.9", "burst-00002", {"m": 2})
    with pytest.raises(Refused, match="wait a minute"):
        a.admit("9.9.9.9", "burst-00003", {"m": 3})
    clock.now += timedelta(seconds=61)
    a.admit("9.9.9.9", "burst-00004", {"m": 4})
    today = a.visitor("9.9.9.9")
    clock.now += timedelta(days=1)
    assert a.visitor("9.9.9.9") != today


def test_concurrent_requests_never_exceed_the_global_cap(tmp_path):
    a = admission(tmp_path, global_per_day=50, visitor_per_day=1000, visitor_per_minute=1000)
    for i in range(49):
        a.admit(f"10.0.0.{i}", f"seed-{i:06d}", {"i": i})
    admitted, refused = [], []
    barrier = threading.Barrier(16)

    def race(n):
        barrier.wait()
        try:
            a.admit(f"10.1.0.{n}", f"race-{n:06d}", {"n": n})
            admitted.append(n)
        except Refused:
            refused.append(n)

    threads = [threading.Thread(target=race, args=(n,)) for n in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(admitted) == 1 and len(refused) == 15


def test_hosted_app_refuses_before_any_model_call(indexed, embedder, tmp_path):
    retriever = Retriever(indexed, embedder=embedder)
    provider = CountingProvider()
    verifier = Verifier()
    guard = HostedGuard(verifier, admission(tmp_path, visitor_per_day=1), site_key="site-key")
    client = TestClient(
        create_app(
            retriever=retriever, answerer=Answerer(retriever, provider=provider), hosted=guard
        )
    )
    body = {"message": "Who preserves the universe?"}
    assert client.get("/api/config").json() == {"hosted": True, "turnstile_site_key": "site-key"}
    assert client.post("/api/chat", json=body).status_code == 403  # no human check
    bad = client.post("/api/chat/stream", json=body, headers={"x-turnstile-token": "bad"})
    assert bad.status_code == 403
    no_id = client.post("/api/chat", json=body, headers={"x-turnstile-token": "good"})
    assert no_id.status_code == 400
    assert provider.calls == 0
    ok = {"x-turnstile-token": "good", "x-request-id": "first-question"}
    assert client.post("/api/chat", json=body, headers=ok).status_code == 200
    assert provider.calls == 1
    again = {"x-turnstile-token": "good", "x-request-id": "second-question"}
    limited = client.post("/api/chat/stream", json=body, headers=again)
    assert limited.status_code == 429 and "Retry-After" in limited.headers
    assert provider.calls == 1
    # Reading and search need no admission.
    assert (
        client.post("/api/search", json={"query": "Vishnu", "strategy": "lexical"}).status_code
        == 200
    )
    # Local mode is unaffected.
    local = TestClient(
        create_app(retriever=retriever, answerer=Answerer(retriever, provider=provider))
    )
    assert local.get("/api/config").json()["hosted"] is False
    assert local.post("/api/chat", json=body).status_code == 200


def test_turnstile_verifier_fails_closed():
    import httpx

    def handler(request):
        if b"response=down" in request.content:
            raise httpx.ConnectError("unreachable")
        return httpx.Response(200, json={"success": b"response=good" in request.content})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = TurnstileVerifier("secret", client)
    assert asyncio.run(verifier.verify("good", "1.1.1.1"))
    assert not asyncio.run(verifier.verify("other", "1.1.1.1"))
    assert not asyncio.run(verifier.verify("down", "1.1.1.1"))
    assert not asyncio.run(verifier.verify("", "1.1.1.1"))
