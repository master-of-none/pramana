import { useEffect, useState } from "react";

// Per-browser display preferences; conversations never go to localStorage.
export type Theme = "system" | "light" | "dark";
export type Size = "regular" | "large";

function read<T extends string>(key: string, allowed: T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key) as T | null;
    return value && allowed.includes(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function usePreference<T extends string>(
  key: string,
  allowed: T[],
  fallback: T,
  apply: (v: T) => void,
) {
  const [value, setValue] = useState<T>(() => read(key, allowed, fallback));
  useEffect(() => {
    apply(value);
    try {
      localStorage.setItem(key, value);
    } catch {
      /* Preferences simply reset next visit. */
    }
  }, [value]);
  return [value, setValue] as const;
}

export function useTheme() {
  return usePreference<Theme>(
    "pramana.theme",
    ["system", "light", "dark"],
    "system",
    (t) => {
      if (t === "system") delete document.documentElement.dataset.theme;
      else document.documentElement.dataset.theme = t;
    },
  );
}

export function useTextSize() {
  return usePreference<Size>(
    "pramana.text-size",
    ["regular", "large"],
    "regular",
    (s) => {
      document.documentElement.dataset.size = s;
    },
  );
}
