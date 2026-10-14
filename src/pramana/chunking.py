import re
from bisect import bisect_left

from pramana.config import CHUNK_CONFIG
from pramana.models import Chapter, Citation, Passage, digest


def chunk_chapter(chapter: Chapter, tokenizer, config: dict | None = None) -> list[Passage]:
    """Slice immutable chapter text, using original character offsets throughout."""
    config = config or CHUNK_CONFIG
    target, maximum, overlap = (
        config[k] for k in ("target_tokens", "max_tokens", "overlap_tokens")
    )
    if not 0 <= overlap < target <= maximum:
        raise ValueError("Expected overlap < target <= max_tokens")
    encoded = tokenizer(
        chapter.text, add_special_tokens=False, return_offsets_mapping=True, verbose=False
    )
    offsets = [(a, b) for a, b in encoded["offset_mapping"] if b > a]
    if not offsets:
        return []
    # Sentence/paragraph endings are candidates, never transformations of source text.
    boundaries = sorted(m.end() for m in re.finditer(r"[.!?][\"'’”]?\s+|\n\n", chapter.text))
    chunks, cursor = [], 0
    while cursor < len(offsets):
        stop = min(cursor + maximum, len(offsets))
        preferred = []
        for i in range(cursor + min(target, stop - cursor), stop):
            boundary_index = bisect_left(boundaries, offsets[i - 1][1])
            if boundary_index < len(boundaries) and boundaries[boundary_index] <= offsets[i][0]:
                preferred.append(i)
        if preferred:
            stop = preferred[0]
        start_char = 0 if cursor == 0 else offsets[cursor][0]
        end_char = len(chapter.text) if stop == len(offsets) else offsets[stop][0]
        # Retokenizing a substring can differ at boundaries; enforce the hard limit.
        while (
            len(tokenizer.encode(chapter.text[start_char:end_char], add_special_tokens=False))
            > maximum
        ):
            stop -= 1
            end_char = offsets[stop][0]
        text = chapter.text[start_char:end_char]
        pid = "p_" + digest(f"{chapter.id}:{digest(chapter.text)}:{start_char}:{end_char}")[:28]
        pages = []
        preceding = [p.label for p in chapter.pages if p.offset <= start_char]
        if preceding:
            pages.append(preceding[-1])
        pages.extend(p.label for p in chapter.pages if start_char < p.offset < end_char)
        pages = list(dict.fromkeys(pages))
        loc = chapter.location
        if chapter.source.local_path:
            label = f"{chapter.document}, physical PDF page " + ", ".join(pages)
        else:
            label = f"{chapter.document}, Book {loc.book}, Chapter {loc.chapter}"
            if pages:
                label += ", pp. " + ", ".join(pages)
        label += f"; {chapter.translator}, {chapter.edition}; {pid}"
        chunks.append(
            Passage(
                id=pid,
                chapter_id=chapter.id,
                corpus_id=chapter.corpus_id,
                text=text,
                start=start_char,
                end=end_char,
                token_count=len(tokenizer.encode(text, add_special_tokens=False)),
                citation=Citation(
                    document=chapter.document,
                    edition=chapter.edition,
                    translator=chapter.translator,
                    language=chapter.language,
                    location=loc,
                    pages=pages,
                    source_url=str(chapter.source.url) if chapter.source.url else None,
                    source_local_path=chapter.source.local_path,
                    author=chapter.author,
                    content_type=chapter.content_type,
                    passage_id=pid,
                    label=label,
                ),
            )
        )
        if stop == len(offsets):
            break
        # Keep overlap within 48 tokens and begin at a sentence boundary if possible.
        next_cursor = stop
        for i in range(max(cursor + 1, stop - overlap), stop):
            boundary_index = bisect_left(boundaries, offsets[i - 1][1])
            if boundary_index < len(boundaries) and boundaries[boundary_index] <= offsets[i][0]:
                next_cursor = i
                break
        cursor = next_cursor
    return chunks
