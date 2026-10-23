import { useEffect, useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import { getJSON, placeLabel } from "../lib/api.ts";
import type { Location } from "../lib/api.ts";
import { href } from "../lib/router.ts";

type Step =
  | {
      kind: "sutra";
      sutra: [string, string, string];
      note: string;
      available: boolean;
    }
  | {
      kind: "chapter";
      document: string;
      category: string;
      location: Location | null;
      chapter_id: string | null;
      note: string;
      available: boolean;
    };
type ReadingPath = {
  slug: string;
  title: string;
  description: string;
  steps: Step[];
};

const KEY = "pramana.paths.read";
const stepKey = (path: string, i: number) => `${path}/${i}`;

// Reading progress is a per-browser convenience, never conversation data.
function useProgress() {
  const [read, setRead] = useState<Set<string>>(() => {
    try {
      const value: unknown = JSON.parse(localStorage.getItem(KEY) || "[]");
      return new Set(
        Array.isArray(value) ? value.filter((v) => typeof v === "string") : [],
      );
    } catch {
      return new Set();
    }
  });
  function toggle(key: string) {
    const next = new Set(read);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setRead(next);
    try {
      localStorage.setItem(KEY, JSON.stringify([...next]));
    } catch {
      /* Progress is kept for this visit only. */
    }
  }
  return { read, toggle };
}

export function Paths() {
  const [paths, setPaths] = useState<ReadingPath[] | null>(null);
  const [error, setError] = useState("");
  const { read, toggle } = useProgress();
  useEffect(() => {
    getJSON<ReadingPath[]>("/api/paths")
      .then(setPaths)
      .catch((e: Error) => setError(e.message));
  }, []);
  if (!paths)
    return (
      <p className="study-status" role={error ? "alert" : "status"}>
        {error || "Opening the reading paths…"}
      </p>
    );
  return (
    <div className="paths">
      <header className="study-intro">
        <a href={href("study")} className="back-link">
          <ArrowLeft size={14} /> Library
        </a>
        <h1>Reading paths</h1>
        <p>
          Curated sequences through the library. Mark a step read to keep your
          place in this browser. Steps for books you have not imported are shown
          but cannot be opened.
        </p>
      </header>
      {paths.map((path) => {
        const done = path.steps.filter((_, i) =>
          read.has(stepKey(path.slug, i)),
        ).length;
        return (
          <section key={path.slug} className="reading-path">
            <h2>{path.title}</h2>
            <p className="doc-meta">
              {path.description} · {done} of {path.steps.length} read
            </p>
            <ol>
              {path.steps.map((step, i) => {
                const key = stepKey(path.slug, i);
                const title =
                  step.kind === "sutra"
                    ? `Brahma Sūtra ${step.sutra.join(".")} · Śaṅkara and Rāmānuja`
                    : `${step.document}${step.location ? ` · ${placeLabel(step.category, step.location)}` : ""}`;
                const link =
                  step.kind === "sutra"
                    ? href("study", "sutra", ...step.sutra)
                    : step.chapter_id && href("study", "read", step.chapter_id);
                return (
                  <li key={key} className={read.has(key) ? "read" : undefined}>
                    <button
                      type="button"
                      className="step-check"
                      aria-pressed={read.has(key)}
                      aria-label={`Mark ${title} as read`}
                      onClick={() => toggle(key)}
                    >
                      <Check size={13} />
                    </button>
                    <div>
                      {step.available && link ? (
                        <a href={link}>{title}</a>
                      ) : (
                        <span className="step-missing">
                          {title} (not imported)
                        </span>
                      )}
                      <p>{step.note}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
