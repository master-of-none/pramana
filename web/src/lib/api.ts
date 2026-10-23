export type Location = { book: string; chapter: string; sections: string[] };
export type Note = { id: string; text: string; anchor_offset: number | null };
export type Chapter = {
  document_id: string;
  document: string;
  edition: string;
  translator: string;
  author: string;
  content_type: string;
  location: Location;
  text: string;
  pages: { offset: number; label: string }[];
  notes: Note[];
  source: {
    url: string | null;
    local_path: string | null;
    rights: string;
    attribution: string;
  };
};
export type RoleSpan = {
  role: "objection" | "reply";
  start: number;
  end: number;
};
export type ChapterContext = {
  id: string;
  chapter: Chapter;
  roles: RoleSpan[];
  previous: string | null;
  next: string | null;
};
export type LibraryDocument = {
  document_id: string;
  document: string;
  category: string;
  author: string;
  translator: string;
  edition: string;
  rights: string;
  attribution: string;
  local: boolean;
  content_types: string[];
  chapters: { id: string; location: Location }[];
};
export type ParallelEntry = {
  document_id: string;
  document: string;
  author: string;
  edition: string;
  exact: boolean;
  chapters: string[];
};
export type SearchHit = {
  passage: {
    id: string;
    chapter_id: string;
    text: string;
    start: number;
    end: number;
    citation: {
      document: string;
      edition: string;
      author: string;
      location: Location;
    };
  };
  snippet: string;
};

export async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}).`,
    );
  return data as T;
}

// Printed divisions, worded for the kind of text.
export function placeLabel(category: string, location: Location): string {
  const [first, ...rest] = location.sections;
  if (category === "Brahma Sūtra")
    return first && /^\d+$/.test(first)
      ? `${location.book}.${location.chapter}.${first}${rest.length ? ` · ${rest.join(" · ")}` : ""}`
      : `${location.book}.${location.chapter} · ${location.sections.join(" · ") || "Pāda"}`;
  if (location.sections.length) return location.sections.join(" · ");
  return `Book ${location.book}, chapter ${location.chapter}`;
}

// Printed scripture references, resolved in the Study view only (code-point offsets).
export type CitationStatus = "verified" | "numbered" | "chapter";
export type Citation = {
  start: number;
  end: number;
  label: string;
  status: CitationStatus;
  quote: string | null;
  target: {
    chapter_id: string;
    document: string;
    place: string;
    start: number;
    end: number;
  };
};
export type CitedBy = {
  chapter_id: string;
  document: string;
  author: string;
  place: string;
  start: number;
  end: number;
  label: string;
  status: CitationStatus;
  quote: string | null;
  target_start: number;
  target_end: number;
};
export type ChapterCitations = { outgoing: Citation[]; incoming: CitedBy[] };
export type CitedPassage = {
  chapter_id: string;
  document: string;
  place: string;
  start: number;
  end: number;
  opening: string;
  verse: number | null;
  by: Record<string, number>;
  total: number;
};
export type CitationSummary = {
  references: number;
  status: Partial<Record<CitationStatus, number>>;
  passages: CitedPassage[];
};

export const CITATION_STATUS: Record<CitationStatus, string> = {
  verified: "The quoted words were found in this passage",
  numbered: "Linked by verse number; there was no quotation to check",
  chapter: "The cited chapter; the verse could not be matched",
};

// Common names for the edition authors, for labels only.
export function thinkerName(author: string): string {
  if (/sankara/i.test(author)) return "Śaṅkara";
  if (/ramanuja/i.test(author)) return "Rāmānuja";
  return author || "Translator's note";
}
