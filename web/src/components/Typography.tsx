import { useEffect, useRef, useState } from "react";
import { Type } from "lucide-react";
import { FACES, LEADINGS, MEASURES, SIZES, useTypography } from "../lib/theme.ts";

const LABELS: Record<string, string> = {
  small: "Small",
  regular: "Regular",
  large: "Large",
  xlarge: "Larger",
  compact: "Compact",
  normal: "Normal",
  airy: "Airy",
  narrow: "Narrow",
  wide: "Wide",
  serif: "Serif",
  sans: "Sans",
};

function Choice<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="type-choice">
      <legend>{label}</legend>
      <div role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={value === o}
            onClick={() => onChange(o)}
          >
            {LABELS[o]}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

// Reading settings for answers and the reader, kept in this browser.
export function TypographyButton({ open: initiallyOpen = false }: { open?: boolean }) {
  const t = useTypography();
  const [open, setOpen] = useState(initiallyOpen);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", outside);
    return () => window.removeEventListener("pointerdown", outside);
  }, [open]);
  useEffect(() => {
    // The command palette can open this panel.
    const show = () => setOpen(true);
    window.addEventListener("pramana:typography", show);
    return () => window.removeEventListener("pramana:typography", show);
  }, []);
  return (
    <div
      className="type-menu"
      ref={box}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <button
        className="icon-button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="type-panel"
        aria-label="Reading settings"
        title="Reading settings"
      >
        <Type size={16} />
      </button>
      {open && (
        <div id="type-panel" className="type-panel" role="group" aria-label="Reading settings">
          <Choice label="Text size" options={SIZES} value={t.size} onChange={t.setSize} />
          <Choice label="Line spacing" options={LEADINGS} value={t.leading} onChange={t.setLeading} />
          <Choice label="Column" options={MEASURES} value={t.measure} onChange={t.setMeasure} />
          <Choice label="Typeface" options={FACES} value={t.face} onChange={t.setFace} />
        </div>
      )}
    </div>
  );
}
