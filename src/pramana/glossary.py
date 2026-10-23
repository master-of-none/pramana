"""Curated general Advaita glossary: hover definitions and lexical query expansion.

Definitions are short editorial explanations, not quotations or evidence from the library.
"""

import json
import re
import unicodedata
from functools import cache
from pathlib import Path

from pydantic import Field

from pramana.models import NonEmpty, Record


class Term(Record):
    term: NonEmpty
    devanagari: str = ""
    aliases: list[str] = Field(default_factory=list)
    english: list[str] = Field(default_factory=list)
    meaning: NonEmpty
    # Whether lexical search expands this concept's names. Entries added after the
    # benchmarks were frozen are display-only: enabling them lowered dev MRR.
    expand: bool = True


def fold(text: str) -> str:
    """Casefold and drop diacritics so IAST, ASCII and English spellings compare equal."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@cache
def terms() -> tuple[Term, ...]:
    data = json.loads((Path(__file__).with_name("glossary.json")).read_text("utf-8"))
    return tuple(Term.model_validate(item) for item in data)


def expansions(query: str) -> list[str]:
    """Sanskrit and English names for every glossary concept the query mentions."""
    folded = fold(query)
    found = []
    for item in terms():
        if not item.expand:
            continue
        # The indexed books are English/IAST; Devanagari only triggers, never expands.
        names = [item.term, *item.aliases, *item.english]
        if any(
            re.search(r"(?<!\w)" + re.escape(fold(name)) + r"(?!\w)", folded) for name in names
        ) or (item.devanagari and item.devanagari in query):
            found.extend(name for name in names if fold(name) not in folded)
    return found
