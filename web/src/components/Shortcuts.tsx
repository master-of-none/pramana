import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { SHORTCUTS, isShortcut } from "../lib/keys.ts";

const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const MOD = mac ? "⌘" : "Ctrl";

const GROUPS: [string, [string, string[]][]][] = [
  [
    "Everywhere",
    [
      ["Open the command palette", [MOD + " + K"]],
      ["Show these shortcuts", ["?"]],
    ],
  ],
  [
    "Ask",
    [
      ["Type a question", ["/"]],
      ["Send · new line", ["Enter", "Shift + Enter"]],
      ["Stop an answer, or close a popover", ["Esc"]],
    ],
  ],
  [
    "Study",
    [
      ["Search the library", ["/"]],
      ["Previous · next part", ["←", "→"]],
      ["Contents of the work", ["T"]],
    ],
  ],
];

// "?" opens a sheet of keyboard shortcuts (also from the command palette).
export function Shortcuts() {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "?" && isShortcut(event)) {
        event.preventDefault();
        setOpen(true);
      }
    };
    const show = () => setOpen(true);
    window.addEventListener("keydown", key);
    window.addEventListener(SHORTCUTS, show);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener(SHORTCUTS, show);
    };
  }, []);
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={dialog}
      className="shortcuts sheet"
      aria-labelledby="shortcuts-title"
      onClose={() => setOpen(false)}
      onClick={(event) => event.target === dialog.current && dialog.current.close()}
    >
      <header>
        <h2 id="shortcuts-title">Keyboard shortcuts</h2>
        <button
          type="button"
          className="icon-button"
          onClick={() => dialog.current?.close()}
          aria-label="Close shortcuts"
        >
          <X size={16} />
        </button>
      </header>
      {GROUPS.map(([group, rows]) => (
        <section key={group}>
          <h3>{group}</h3>
          <dl>
            {rows.map(([label, keys]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  {keys.map((k, i) => (
                    <span key={k}>
                      {i > 0 && <span className="sep"> · </span>}
                      {k.split(" + ").map((part, j) => (
                        <span key={part}>
                          {j > 0 && " + "}
                          <kbd>{part}</kbd>
                        </span>
                      ))}
                    </span>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </dialog>
  );
}
