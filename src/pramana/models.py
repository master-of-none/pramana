import hashlib
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]+$", min_length=1)]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Record):
    url: HttpUrl
    retrieved_at: datetime
    checksum: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    rights: NonEmpty
    attribution: NonEmpty


class Location(Record):
    book: NonEmpty
    chapter: NonEmpty
    sections: list[str] = Field(default_factory=list)


class PageMark(Record):
    offset: int = Field(ge=0)
    label: NonEmpty


class Note(Record):
    id: NonEmpty
    text: NonEmpty
    anchor_offset: int | None = Field(default=None, ge=0)


class Chapter(Record):
    corpus_id: Identifier
    document_id: Identifier
    document: NonEmpty
    edition: NonEmpty
    translator: NonEmpty
    language: NonEmpty
    location: Location
    source: Source
    text: str = Field(min_length=1)
    summary: str = ""
    pages: list[PageMark] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_offsets(self):
        if not self.text.strip():
            raise ValueError("text must contain a non-whitespace translation body")
        if any(p.offset > len(self.text) for p in self.pages):
            raise ValueError("page offset exceeds chapter text length")
        if self.pages != sorted(self.pages, key=lambda p: p.offset):
            raise ValueError("pages must be ordered by offset")
        if any(
            n.anchor_offset is not None and n.anchor_offset > len(self.text) for n in self.notes
        ):
            raise ValueError("note anchor_offset exceeds chapter text length")
        if len({n.id for n in self.notes}) != len(self.notes):
            raise ValueError("note IDs must be unique within a chapter")
        return self

    @property
    def id(self) -> str:
        key = [
            self.corpus_id,
            self.document_id,
            self.edition,
            self.language,
            self.location.model_dump(),
        ]
        import json

        return "ch_" + digest(json.dumps(key, sort_keys=True, ensure_ascii=False))[:24]


class Citation(Record):
    document: str
    edition: str
    translator: str
    language: str
    location: Location
    pages: list[str]
    source_url: str
    passage_id: str
    label: str


class Passage(Record):
    id: str
    chapter_id: str
    corpus_id: str
    text: str
    start: int
    end: int
    token_count: int
    citation: Citation


class SearchHit(Record):
    passage: Passage
    snippet: str
    score: float
    score_kind: Literal["bm25", "cosine", "rrf"]


class SearchFilters(Record):
    corpus_id: str | None = None
    book: str | None = None
    chapter: str | None = None
    edition: str | None = None
    language: str | None = None
    translator: str | None = None


Strategy = Literal["lexical", "dense", "hybrid"]


class SearchRequest(Record):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    strategy: Strategy = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)
