import { useEffect, useState } from "react";

// Reading progress, per browser (AGENTS.md allows it in localStorage): where each work was
// last read and which of its parts were read to the end. Never sent anywhere.
export const PROGRESS = "pramana.reading.v1";
const DONE_AT = 0.9;

export type WorkProgress = {
  chapter: string; // the part last open
  fraction: number; // how far down that part, 0..1
  at: number; // when, ms since epoch
  done: string[]; // parts read to the end
};
export type Progress = Record<string, WorkProgress>;

// Works are told apart by edition as well as document.
export const workKey = (documentId: string, edition: string) => `${documentId}|${edition}`;

export function parseProgress(data: unknown): Progress {
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  const out: Progress = {};
  for (const [key, value] of Object.entries(data as Record<string, unknown>).slice(0, 500)) {
    const v = value as Partial<WorkProgress> | null;
    if (
      !v ||
      typeof v.chapter !== "string" ||
      typeof v.fraction !== "number" ||
      typeof v.at !== "number" ||
      !Array.isArray(v.done)
    )
      continue;
    out[key] = {
      chapter: v.chapter,
      fraction: Math.min(1, Math.max(0, v.fraction)),
      at: v.at,
      done: v.done.filter((d): d is string => typeof d === "string").slice(0, 5000),
    };
  }
  return out;
}

// Record a position; a part counts as read once its end has been reached.
export function record(
  progress: Progress,
  key: string,
  chapter: string,
  fraction: number,
  now: number,
): Progress {
  const before = progress[key];
  const done = new Set(before?.done ?? []);
  if (fraction >= DONE_AT) done.add(chapter);
  return { ...progress, [key]: { chapter, fraction, at: now, done: [...done] } };
}

// The most recently read work, if any.
export function latest(progress: Progress): [string, WorkProgress] | null {
  const entries = Object.entries(progress);
  if (!entries.length) return null;
  return entries.reduce((a, b) => (b[1].at > a[1].at ? b : a));
}

export function share(work: WorkProgress | undefined, chapterIds: string[]): number {
  if (!work || !chapterIds.length) return 0;
  const done = new Set(work.done);
  return chapterIds.filter((id) => done.has(id)).length / chapterIds.length;
}

function load(): Progress {
  try {
    return parseProgress(JSON.parse(localStorage.getItem(PROGRESS) || "{}"));
  } catch {
    return {};
  }
}

export function useProgress() {
  const [progress, setProgress] = useState<Progress>(load);
  useEffect(() => {
    const sync = (event: StorageEvent) => event.key === PROGRESS && setProgress(load());
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  function save(key: string, chapter: string, fraction: number) {
    setProgress((current) => {
      const next = record(current, key, chapter, fraction, Date.now());
      try {
        localStorage.setItem(PROGRESS, JSON.stringify(next));
      } catch {
        /* Progress simply isn't remembered. */
      }
      return next;
    });
  }
  return { progress, save };
}
