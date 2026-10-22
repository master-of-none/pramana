import json

from pramana.discourse import annotate, segments

TEXT = (
    "The Lord teaches. Objection:— Action alone leads to liberation. "
    "Answer: No; knowledge alone removes ignorance. Exposition continues.\n"
    "(Question)— Why act at all? Reply. — To purify the mind. 𑀅 Ānanda."
)


def test_labelled_roles_cover_text_exactly():
    parts = segments(TEXT)
    assert "".join(p["text"] for p in parts) == TEXT
    assert [p["role"] for p in parts] == ["unmarked", "objection", "reply", "objection", "reply"]
    assert parts[1]["text"].startswith("Objection:— Action")


def test_unlabelled_prose_is_never_assigned_a_role():
    prose = "The question: what is the Self? An answer, the sages say, is near."
    assert segments(prose) == [{"role": "unmarked", "text": prose}]


def test_role_carries_in_and_reply_follows_truncated_objection():
    start = TEXT.index("Action alone")
    end = TEXT.index("Answer:")
    found = annotate(TEXT, start, end)
    assert found["segments"] == [{"role": "objection", "text": TEXT[start:end]}]
    assert found["following_reply"].startswith("Answer: No; knowledge alone")
    later = annotate(TEXT, TEXT.index("Exposition"), TEXT.index("(Question)"))
    assert later["segments"][0]["role"] == "reply" and "following_reply" not in later


def test_answerer_supplies_roles_to_model(tmp_path, make_chapter, embedder):
    from test_answering import Provider, grounded, run

    from pramana import Corpus, Retriever
    from pramana.answering import Answerer

    corpus = Corpus(tmp_path / "library")
    path = tmp_path / "commentary.jsonl"
    path.write_text(make_chapter(TEXT).model_dump_json(), encoding="utf-8")
    corpus.import_jsonl(path)
    corpus.index(embedder=embedder)
    provider = Provider([grounded("Knowledge, not action alone, removes ignorance.")])
    run(Answerer(Retriever(corpus, embedder=embedder), provider=provider), "Does action liberate?")
    item = json.loads(provider.calls[0][0][-1]["content"])["evidence"][0]
    assert "text" not in item
    assert "".join(p["text"] for p in item["segments"]) == TEXT
    assert "objection segment" in provider.calls[0][0][0]["content"]
