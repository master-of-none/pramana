import { useEffect, useState } from "react";

// Per-browser display preferences; conversations never go to localStorage.
export type Theme = "system" | "light" | "dark";

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

// Reading typography: applied as attributes on <html>, read by styles/tokens.css.
export const SIZES = ["small", "regular", "large", "xlarge"] as const;
export const LEADINGS = ["compact", "normal", "airy"] as const;
export const MEASURES = ["narrow", "normal", "wide"] as const;
export const FACES = ["serif", "sans"] as const;
export type Size = (typeof SIZES)[number];

const attribute = (name: string) => (value: string) => {
  document.documentElement.dataset[name] = value;
};

export function useTypography() {
  const [size, setSize] = usePreference<Size>("pramana.text-size", [...SIZES], "regular", attribute("size"));
  const [leading, setLeading] = usePreference<(typeof LEADINGS)[number]>(
    "pramana.leading",
    [...LEADINGS],
    "normal",
    attribute("leading"),
  );
  const [measure, setMeasure] = usePreference<(typeof MEASURES)[number]>(
    "pramana.measure",
    [...MEASURES],
    "normal",
    attribute("measure"),
  );
  const [face, setFace] = usePreference<(typeof FACES)[number]>(
    "pramana.face",
    [...FACES],
    "serif",
    attribute("face"),
  );
  return { size, setSize, leading, setLeading, measure, setMeasure, face, setFace };
}
