import { useEffect, useState } from "react";

// Hash routes keep the static build servable from FastAPI's single index.html.
export type Route = { path: string[]; query: URLSearchParams };

function parse(): Route {
  const [path, query = ""] = window.location.hash
    .replace(/^#\/?/, "")
    .split("?");
  return {
    path: path.split("/").filter(Boolean).map(decodeURIComponent),
    query: new URLSearchParams(query),
  };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const change = () => setRoute(parse());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return route;
}

export function href(...parts: (string | number)[]): string {
  return "#/" + parts.map((p) => encodeURIComponent(String(p))).join("/");
}

// The reader at a chapter, optionally highlighting a code-point span.
export function readAt(chapterId: string, start?: number, end?: number): string {
  const base = href("study", "read", chapterId);
  return start === undefined || end === undefined ? base : `${base}?s=${start}&e=${end}`;
}
