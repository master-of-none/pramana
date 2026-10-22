import pytest

from pramana.errors import PramanaError
from pramana.ingestion import brahmasutra
from pramana.ingestion.brahmasutra import manifest, parse_page

PAGE = """<HTML><BODY><CENTER><A HREF="index.htm">Index</A></CENTER><HR>
<P ALIGN="CENTER"><FONT><I>The Vedanta Sutras (SBE38)</I>, tr. by George Thibaut [1896]
at sacred-texts.com</FONT></P><HR></p>
<p>7. But wherever there are effects, there is division; as in ordinary life.</p>
<p>The p&ucirc;rvapakshin maintains that ether is eternal&nbsp;<A NAME="fr_5"></A>
<A HREF="#fn_5"><FONT SIZE="1">1</FONT></A>.
<p><A NAME="page_14"><FONT SIZE=1 COLOR=GREEN>p. 14</FONT></A></p>
<p>To this we make the following reply. Vai<I>s</I>v&acirc;nara 𑀅 shows ether is an effect.
<p>
</p>
<HR><H3 ALIGN="CENTER">Footnotes</H3>
<P><A NAME="fn_4"></A><A HREF="prev.htm#fr_4">13:1</A> Belongs to the previous page.</P>
<P><A NAME="fn_5"></A><A HREF="sbe38008.htm#fr_5">13:2</A> A note on ether.</P>
<p><HR><CENTER><A HREF="next.htm">Next: II, 3, 8</A></CENTER>
<nav><p>Sacred Texts | Hinduism</p></nav></BODY></HTML>"""


def entry(**extra):
    return next(e for e in manifest() if e["file"] == "sbe38008.htm") | extra


def source():
    from datetime import UTC, datetime

    from pramana.models import Source

    return Source(
        url=entry()["url"],
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        checksum="0" * 64,
        rights="Test",
        attribution="Test",
    )


def test_manifest_identities_are_unique_and_corrected():
    entries = manifest()
    keys = {(e["adhyaya"], e["pada"], e["sutra"]) for e in entries}
    assert len(keys) == len(entries) == 552
    assert entry()["sutra"] == "7" and entry()["index_label"] == "II, 3, 6"


def test_parse_page_keeps_text_pages_and_own_notes():
    chapter = parse_page(PAGE, entry(), source())
    text = chapter.text
    assert text.startswith("7. But wherever")
    assert "Vaisvânara 𑀅 shows ether is an effect." in text
    assert "Next:" not in text and "Sacred Texts" not in text and "Belongs" not in text
    assert text.count("To this we make") == 1  # nested unclosed <p> is not duplicated
    assert [p.label for p in chapter.pages] == ["14"]
    assert text[chapter.pages[0].offset :].startswith("To this we")
    (note,) = chapter.notes
    assert note.id == "13:2" and note.text == "A note on ether."
    assert text[: note.anchor_offset].endswith("ether is eternal")
    assert chapter.location.sections == ["7"] and chapter.content_type == "mixed"


def test_parse_page_rejects_changed_structure():
    with pytest.raises(PramanaError, match="sutra 6"):
        parse_page(PAGE, entry(sutra="6"), source())
    with pytest.raises(PramanaError, match="not a Thibaut"):
        parse_page("<html><p>Just a moment...</p></html>", entry(), source())


def test_offline_acquire_requires_cache(tmp_path):
    with pytest.raises(PramanaError, match="cached pages missing"):
        brahmasutra.acquire(tmp_path, offline=True)
    assert not (tmp_path / "corpora" / "brahma-sutra-thibaut" / "chapters.jsonl").exists()
