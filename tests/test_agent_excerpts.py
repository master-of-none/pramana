import json
from datetime import UTC, date, datetime, timedelta

import pytest

from pramana import Corpus
from pramana import agent_excerpts as ex
from pramana.errors import PramanaError
from pramana.models import Location

# Gītā-style: a range, a printed gap (4 is absent), a speaker label and a chapter footer,
# a page break inside a sentence, and a supplementary character (offsets are code points).
VERSES = (
    "FIRST CHAPTER.\n\n"
    "1. Tell me, O Sanjaya, what the people did when they assembled on the field, 𑀅 desirous "
    "to fight?\n\n\n\nSanjaya said:\n\n"
    "2-3. Seeing the host drawn up, the king approached his teacher and spoke these words of "
    "great concern.\n\n"
    "5. The seed of every action lies in the mind, so a steady mind\n\n\n\n"
    "brings a steady life to the man who keeps it.\n\n"
    "The end of chapter first."
)
# Richards-style: reference at the paragraph end; or alone on its own line after a verse.
TRAILING = (
    "Chapter 1 Self\n\nJanaka said: \n\n"
    "How is one to acquire knowledge? How is one to attain liberation? And how is \n"
    "one to reach dispassion? Tell me this, sir. 1.1 \n\n"
    "If you are seeking liberation, my son, avoid the objects of the senses like poison \n"
    "and cultivate tolerance, sincerity and truthfulness. \n\n1.2 \n\n"
    "Ashtavakra said: \n\n"
    "You are not the body, nor is the body yours; you are the witness, free and at peace. 1.3 "
)
PAREN = (
    "Hymn.\n\n"
    "I praise, with devotion, the all-pervading Lord who is the origin of the universe. (1)\n\n"
    "Him in whom this wheel of samsara revolves I praise, the destroyer of darkness. (2).\n\n"
    "The third verse is long enough to count, and runs on past a page break\n\n\n\n"
    "so that it ends well after the break. (3)"
)
PROSE = (
    "The Self is the witness of all that is seen, free from change and from every limit "
    "of the mind. Thus the wise say that the Self alone remains when the world has passed away. "
    "Mr. Johnston adds that this teaching is old, viz. older than the schools of the Vedanta. "
    "The student who has understood this lives without fear.\n\n"
    "THIS HEADING IS ALL CAPITALS AND IS NOT PROSE AT ALL\n\n"
    'He said "go forth and tell the others about what you have learned here today.'
)


def entries(**docs):
    """An allowlist for fixtures: name -> (kinds, extra keys)."""
    return ex.parse_sources(
        {
            "groups": [
                {
                    "name": "fixtures",
                    "rights": "Test rights.",
                    "attribution": "Test attribution.",
                    "documents": [
                        {"id": name, "kinds": kinds, **extra}
                        for name, (kinds, extra) in docs.items()
                    ],
                }
            ]
        }
    )


@pytest.fixture
def library(tmp_path, make_chapter):
    """A corpus with one document per printed form, and its allowlist."""

    def add(text, document_id, chapter="1", sections=None):
        c = make_chapter(text, book="1", chapter=chapter)
        c.document_id, c.document = document_id, document_id.title()
        c.location = Location(book="1", chapter=chapter, sections=sections or [f"Sec {chapter}"])
        return c

    chapters = [
        add(VERSES, "verses"),
        add(TRAILING, "trailing"),
        add(PAREN, "paren"),
        add(PROSE, "prose"),
        add(PROSE.replace("The Self", "A Self"), "other-prose"),
    ]
    path = tmp_path / "excerpts.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in chapters), encoding="utf-8")
    corpus = Corpus(tmp_path / "library")
    corpus.import_jsonl(path)
    allow = entries(
        verses=({"verse": "leading-number"}, {}),
        trailing=({"verse": "trailing-ref"}, {"reference": "label"}),
        paren=({"verse": "trailing-paren"}, {"reference": "label"}),
        prose=({"passage": "windows", "sentence": "windows"}, {}),
    )
    return corpus, allow, chapters


def test_leading_numbers_keep_ranges_and_gaps_and_drop_labels_and_footers():
    units = ex.units_leading(VERSES)
    assert [(u.label, u.gap_before) for u in units] == [("1", False), ("2–3", False), ("5", True)]
    first, last = (VERSES[u.start : u.end] for u in (units[0], units[2]))
    assert first.endswith("desirous to fight?")  # the "Sanjaya said:" label is not part of it
    assert last.endswith("man who keeps it.")  # nor is the chapter footer
    assert "\n\n\n\n" in last  # a page break inside a sentence stays: text is the exact slice
    assert VERSES[units[0].body_start :].startswith("Tell me")  # the printed number is not body


def test_trailing_reference_alone_on_its_line_belongs_to_the_paragraph_before():
    units = ex.units_trailing_ref(TRAILING)
    assert [u.label for u in units] == ["1.1", "1.2", "1.3"]
    assert TRAILING[units[1].start : units[1].end].startswith("If you are seeking liberation")
    assert TRAILING[units[1].start : units[1].end].endswith("1.2")
    assert TRAILING[units[0].body_start : units[0].body_end].strip().endswith("Tell me this, sir.")
    assert TRAILING[units[0].start : units[0].end].endswith("sir. 1.1")  # no trailing space


def test_trailing_parenthesis_numbers_reach_back_over_a_page_break():
    units = ex.units_trailing_paren(PAREN)
    assert [u.label for u in units] == ["1", "2", "3"]
    third = PAREN[units[2].start : units[2].end]
    assert third.startswith("The third verse") and third.endswith("(3)")


def test_rejections_are_counted_not_served():
    marked = "1. A verse that carries a stray [paragraph continues] scan marker inside of it.\n\n"
    short = "2. Om.\n\n"
    open_ended = "3. A verse that stops with a semicolon and goes on in the next one;\n\n"
    text = marked + short + open_ended + "4. A verse that is whole and long enough to be served."
    reasons = [ex.verse_rejection(text, u) for u in ex.units_leading(text)]
    assert reasons == ["marker", "short", "no-terminal", None]


def test_sentence_rules():
    ok = "The Self is the witness of all that is seen, free from change and from every limit."
    assert ex.sentence_ok(ok)
    assert not ex.sentence_ok("Thus the wise say that the Self alone remains when all passes.")
    assert not ex.sentence_ok('He said "go forth and tell the others what you have learned.')
    assert not ex.sentence_ok("Too short to stand alone.")
    assert not ex.sentence_ok(ok * 5)
    assert not ex.sentence_ok("It is laid down elsewhere in the text (see Sutra III, 2, 4 above).")
    assert not ex.sentence_ok("the Self is the witness of all that is seen, free from change.")


def test_windows_split_around_abbreviations_and_skip_headings():
    found = ex.prose_units(PROSE, {"passage", "sentence"})
    texts = {kind: [PROSE[u.start : u.end] for k, u in found if k == kind] for kind in ex.KINDS}
    sentences = texts["sentence"]
    assert any(s.startswith("Mr. Johnston adds") and s.endswith("Vedanta.") for s in sentences)
    assert all(not s.startswith("Thus") and "ALL CAPITALS" not in s for s in sentences)
    assert all(not s.startswith("He said") for s in sentences)  # an unclosed quote
    for text in texts["passage"]:
        assert 150 <= len(text) <= 600 and text.endswith(".")
    spans = sorted((u.start, u.end) for k, u in found if k == "passage")
    assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:], strict=False))


def test_every_excerpt_is_the_exact_slice_in_code_points(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    assert {i.kind for i in pool.items} == set(ex.KINDS)
    for item in pool.items:
        data, body = ex.render(corpus.store, pool, item)
        chapter = corpus.store.chapter(item.chapter_id)
        assert data["text"] == chapter.text[item.start : item.end]
        assert item.id == f"{item.chapter_id}:{item.start}-{item.end}"
        assert body and "\n" not in body
    first = next(i for i in pool.items if i.label == "1" and i.document_id == "verses")
    data, _ = ex.render(corpus.store, pool, first)
    assert "𑀅" in data["text"] and data["boundary"] == "printed"
    assert data["rights"] == "Test rights." and data["notes"] == []


def test_references_come_only_from_printed_labels(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    refs = {}
    for item in pool.items:
        data, _ = ex.render(corpus.store, pool, item)
        refs[(item.document_id, item.kind, item.label)] = data["reference"]
    assert refs[("verses", "verse", "2–3")] == "Verses, Sec 1, 2–3"
    assert refs[("trailing", "verse", "1.2")] == "Trailing 1.2"
    assert refs[("paren", "verse", "1")] == "Paren 1"
    prose = {r for (doc, kind, _), r in refs.items() if doc == "prose"}
    assert prose == {"Prose, Sec 1"}  # a passage or sentence never gets a number


def test_the_pool_serves_only_listed_documents_and_refuses_private_ones(library, make_chapter):
    corpus, allow, chapters = library
    pool = ex.build_pool(corpus.store, allow)
    assert "other-prose" not in {i.document_id for i in pool.items}
    private = chapters[0].model_copy(deep=True)
    private.source.url, private.source.local_path = None, "sources/private.pdf"
    private.document_id = "private"
    path = corpus.home / "private.jsonl"
    path.write_text(private.model_dump_json(), encoding="utf-8")
    corpus.import_jsonl(path)
    assert "private" not in {i.document_id for i in ex.build_pool(corpus.store, allow).items}
    listed = {
        **allow,
        "private": ex.Entry("private", "", "r", "a", {"verse": "leading-number"}, "section", 9),
    }
    with pytest.raises(PramanaError, match="private local origin"):
        ex.build_pool(corpus.store, listed)


def test_an_identical_text_is_served_once(tmp_path, make_chapter):
    twice = "1. The same words are said here, and they are whole enough to serve.\n\n"
    chapters = []
    for n in ("1", "2"):
        c = make_chapter(
            twice + "2. A second and different verse, whole enough to serve too.", chapter=n
        )
        c.document_id, c.location = "refrain", Location(book="1", chapter=n, sections=[n])
        chapters.append(c)
    path = tmp_path / "r.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in chapters), encoding="utf-8")
    corpus = Corpus(tmp_path / "library")
    corpus.import_jsonl(path)
    pool = ex.build_pool(corpus.store, entries(refrain=({"verse": "leading-number"}, {})))
    assert len(pool.items) == 2


def test_the_pool_is_rebuilt_when_the_corpus_changes(library, make_chapter):
    corpus, allow, _ = library
    first = ex.pool_for(corpus.store, allow)
    assert ex.pool_for(corpus.store, allow) is first
    extra = make_chapter(
        "1. A brand new verse that was imported later, whole and plain.", chapter="9"
    )
    extra.document_id, extra.location = "verses", Location(book="1", chapter="9", sections=["9"])
    path = corpus.home / "more.jsonl"
    path.write_text(extra.model_dump_json(), encoding="utf-8")
    corpus.import_jsonl(path)
    assert len(ex.pool_for(corpus.store, allow).items) == len(first.items) + 1


def test_today_is_the_same_for_everyone_and_follows_date_seed_and_timezone(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    items = ex.candidates(pool)
    day = date(2026, 11, 2)
    assert ex.today(pool, items, day=day) == ex.today(pool, items, day=day)
    picks = {ex.today(pool, items, day=day + timedelta(days=n))[0].id for n in range(3)}
    assert len(picks) == 3
    assert (
        ex.today(pool, items, day=day, seed="a")[0] != ex.today(pool, items, day=day, seed="b")[0]
    )
    late = datetime(2026, 11, 1, 20, 0, tzinfo=UTC)  # 01:30 the next day in Kolkata
    assert ex.day_in("UTC", now=late) == date(2026, 11, 1)
    assert ex.day_in("Asia/Kolkata", now=late) == date(2026, 11, 2)
    assert ex.day_in("UTC", on=date(2030, 1, 1)) == date(2030, 1, 1)
    with pytest.raises(ValueError, match="Unknown timezone"):
        ex.day_in("Mars/Olympus")


def test_nothing_repeats_until_the_whole_pool_has_run(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    items = ex.candidates(pool)
    seen = [
        ex.today(pool, items, day=date(2026, 1, 1) + timedelta(days=n))[0].id
        for n in range(len(items))
    ]
    assert sorted(seen) == sorted(i.id for i in items)


def test_a_cap_limits_how_much_one_document_contributes(library):
    corpus, allow, _ = library
    capped = {
        **allow,
        "verses": ex.Entry("verses", "", "r", "a", {"verse": "leading-number"}, "section", 1),
    }
    pool = ex.build_pool(corpus.store, capped)
    items = ex.candidates(pool)
    seen = {
        ex.today(pool, items, day=date(2026, 1, 1) + timedelta(days=n))[0]
        for n in range(len(items))
    }
    assert sum(i.document_id == "verses" for i in seen) == 1
    assert sum(i.document_id == "verses" for i in items) == 3  # random still reaches all of them


def test_filters_and_random_exclusion(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    assert {i.kind for i in ex.candidates(pool, ["sentence"])} == {"sentence"}
    assert {i.document_id for i in ex.candidates(pool, documents=["paren"])} == {"paren"}
    assert all(100 <= i.length <= 120 for i in ex.candidates(pool, min_chars=100, max_chars=120))
    with pytest.raises(ValueError, match="not in the excerpt pool"):
        ex.candidates(pool, documents=["other-prose"])
    items = ex.candidates(pool, documents=["paren"])
    skip = {i.id for i in items[:-1]}
    assert ex.pick_random(pool, items, skip)[0] == items[-1]
    with pytest.raises(PramanaError):
        ex.pick_random(pool, items, {i.id for i in items})


def test_messages_leave_the_printed_number_to_the_reference(library):
    corpus, allow, _ = library
    pool = ex.build_pool(corpus.store, allow)
    item = next(i for i in pool.items if i.document_id == "verses" and i.label == "5")
    data, body = ex.render(corpus.store, pool, item)
    assert body.startswith("The seed of every action") and "\n" not in body
    text = ex.message(data, body, "text")
    assert text.startswith("“The seed") and "— Verses, Sec 1, 5 · Test attribution." in text
    assert ex.message(data, body, "markdown").startswith("> The seed")


def test_the_committed_allowlist_is_well_formed_and_leaves_commentaries_out():
    entries_ = ex.load_sources()
    assert len(entries_) > 50
    for entry in entries_.values():
        assert entry.rights and entry.attribution and entry.kinds
        assert "Next:" not in entry.rights + entry.attribution  # no scraped page text
        assert "function(" not in entry.rights + entry.attribution
    assert not [d for d in entries_ if "brahma-sutra" in d or d.startswith("vivekachudamani-mad")]
    raw = json.loads(ex.SOURCES_FILE.read_text(encoding="utf-8"))
    assert len(
        {d if isinstance(d, str) else d["id"] for g in raw["groups"] for d in g["documents"]}
    ) == len(entries_)


@pytest.mark.parametrize(
    "bad",
    [
        {
            "groups": [
                {
                    "rights": "",
                    "attribution": "a",
                    "documents": ["d"],
                    "kinds": {"verse": "leading-number"},
                }
            ]
        },
        {
            "groups": [
                {
                    "rights": "r",
                    "attribution": "a",
                    "documents": ["d"],
                    "kinds": {"poem": "windows"},
                }
            ]
        },
        {
            "groups": [
                {
                    "rights": "r",
                    "attribution": "a",
                    "documents": ["d"],
                    "kinds": {"verse": "windows"},
                }
            ]
        },
        {
            "groups": [
                {
                    "rights": "r",
                    "attribution": "a",
                    "documents": ["d", "d"],
                    "kinds": {"sentence": "windows"},
                }
            ]
        },
        {
            "groups": [
                {
                    "rights": "r Next: x",
                    "attribution": "a",
                    "documents": ["d"],
                    "kinds": {"sentence": "windows"},
                }
            ]
        },
    ],
)
def test_a_bad_allowlist_fails_loudly(bad):
    with pytest.raises(PramanaError):
        ex.parse_sources(bad)


@pytest.fixture
def searchable(library, embedder):
    from pramana import Retriever

    corpus, allow, _ = library
    corpus.index(embedder=embedder)
    return corpus, allow, Retriever(corpus, embedder=embedder)


def about(searchable, topic, *, exclude=None, strategy="hybrid", documents=None):
    corpus, allow, retriever = searchable
    pool = ex.build_pool(corpus.store, allow)
    items = ex.candidates(pool, documents=documents)
    return ex.about(
        pool, corpus.store, retriever, topic, items, exclude, strategy=strategy, best=1
    ), pool


def test_a_topic_finds_the_excerpt_nearest_to_it(searchable):
    (item, meta), pool = about(searchable, "a steady mind and a steady life")
    assert item.document_id == "verses" and item.label == "5" and meta["size"] >= 3
    (item, _), _ = about(searchable, "the wheel of samsara", strategy="lexical")
    assert item.document_id == "paren" and item.label == "2"


def test_a_topic_only_searches_the_pool_and_honours_exclusions(searchable, make_chapter):
    corpus, allow, retriever = searchable
    secret = make_chapter("1. Zanzibar zanzibar zanzibar spices fill the market, whole and plain.")
    secret.document_id, secret.location = (
        "unlisted",
        Location(book="1", chapter="1", sections=["Z"]),
    )
    path = corpus.home / "secret.jsonl"
    path.write_text(secret.model_dump_json(), encoding="utf-8")
    corpus.import_jsonl(path)
    corpus.index(embedder=retriever.embedder)
    # Searched before ranking: an unlisted text that matches best must not use up the hits.
    pool = ex.build_pool(corpus.store, allow)
    item, _ = ex.about(
        pool, corpus.store, retriever, "zanzibar spices market", ex.candidates(pool), hits=1
    )
    assert item.document_id != "unlisted"
    with pytest.raises(ex.NoMatch):  # the one passage that has the word is not in the pool
        about(searchable, "zanzibar", strategy="lexical")
    (item, _), _ = about(searchable, "zanzibar spices market")
    assert item.document_id != "unlisted"
    (item, _), pool = about(searchable, "a steady mind")
    with pytest.raises(ex.NoMatch, match="excluded"):
        about(searchable, "a steady mind", exclude={i.id for i in pool.items})
    (other, _), _ = about(searchable, "a steady mind", exclude={item.id})
    assert other != item
