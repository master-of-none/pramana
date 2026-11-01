import { useEffect, useState } from "react";
import { getJSON } from "../lib/api.ts";
import type {
  ChapterCitations,
  ChapterContext,
  Divergence,
  LibraryDocument,
} from "../lib/api.ts";

// Shared per page load; the catalogue changes only when the library is re-imported.
let catalogue: Promise<LibraryDocument[]> | null = null;
export function useLibrary() {
  const [docs, setDocs] = useState<LibraryDocument[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    catalogue ??= getJSON<LibraryDocument[]>("/api/library");
    catalogue.then(setDocs).catch((e: Error) => {
      catalogue = null;
      setError(e.message);
    });
  }, []);
  return { docs, error };
}

export function useChapter(id: string | undefined) {
  const [context, setContext] = useState<ChapterContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!id) return;
    setContext(null);
    setError("");
    getJSON<ChapterContext>(`/api/chapters/${encodeURIComponent(id)}`)
      .then(setContext)
      .catch((e: Error) => setError(e.message));
  }, [id]);
  return { context, error };
}

export function useCitations(id: string | undefined) {
  const [citations, setCitations] = useState<ChapterCitations | null>(null);
  useEffect(() => {
    setCitations(null);
    if (!id) return;
    // Links are an addition to the text: a failure leaves the reader unchanged.
    getJSON<ChapterCitations>(`/api/citations/${encodeURIComponent(id)}`)
      .then(setCitations)
      .catch(() => setCitations(null));
  }, [id]);
  return citations;
}

// Each chapter loads on its own: one failure is shown in its place, not for the page.
export async function loadChapters(ids: string[]) {
  const unique = [...new Set(ids)];
  const loaded = await Promise.allSettled(
    unique.map((id) => getJSON<ChapterContext>(`/api/chapters/${encodeURIComponent(id)}`)),
  );
  return Object.fromEntries(
    loaded.map((r, i) => [
      unique[i],
      r.status === "fulfilled" ? r.value : (r.reason as Error),
    ]),
  ) as Record<string, ChapterContext | Error>;
}

// The divergence map, once per page load (rebuilt server-side when the library changes).
let divergenceMap: Promise<Divergence> | null = null;
export function useDivergence() {
  const [data, setData] = useState<Divergence | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    divergenceMap ??= getJSON<Divergence>("/api/divergence");
    divergenceMap.then(setData).catch((e: Error) => {
      divergenceMap = null;
      setError(e.message);
    });
  }, []);
  return { data, error };
}

// The unit of the map that covers a sūtra, if any.
export function unitFor(data: Divergence | null, book: string, pada: string, sutra: number) {
  return data?.units.find(
    (u) =>
      u.book === book &&
      u.pada === pada &&
      u.first <= sutra &&
      (u.last === null || sutra <= u.last),
  );
}
