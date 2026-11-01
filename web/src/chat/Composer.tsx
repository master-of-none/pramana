import { useEffect, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { ArrowUp, CornerDownLeft, RotateCcw, Square } from "lucide-react";
import type { Depth, Mode, Scope } from "./useChatSession.ts";

export const SCOPES: Scope[] = [
  "all",
  "upanishads",
  "gita",
  "yoga-vasistha",
  "shankara",
  "ramanuja",
];
export const DEPTHS: [Depth, string][] = [
  ["brief", "Brief"],
  ["explain", "Explain"],
  ["deep", "In depth"],
];
const COMPARE = "How do Śaṅkara and Rāmānuja differ on ";
type ScopeInfo = { scope: Scope; label: string; documents: number };
type Provider = { name: string; model: string };

// Scopes with imported books, and which model writes answers. A failure is shown, not
// hidden, so the missing controls are explained.
export function useChatOptions() {
  const [available, setAvailable] = useState<ScopeInfo[]>([]);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setFailed(false);
    const json = (r: Response) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)));
    Promise.all([fetch("/api/scopes").then(json), fetch("/api/config").then(json)])
      .then(([scopes, config]) => {
        if (Array.isArray(scopes)) setAvailable(scopes);
        if (config?.provider) setProvider(config.provider);
      })
      .catch(() => setFailed(true));
  }, [attempt]);
  return { available, provider, failed, retry: () => setAttempt((n) => n + 1) };
}

export type Settings = {
  scope: Scope;
  setScope: (s: Scope) => void;
  depth: Depth;
  setDepth: (d: Depth) => void;
  mode: Mode;
  setMode: (m: Mode) => void;
  check: "on" | "off";
  setCheck: (c: "on" | "off") => void;
};

export function Composer({
  composer,
  message,
  setMessage,
  settings,
  options,
  pending,
  ready,
  hasConversation,
  hasFocus,
  onClearFocus,
  onSend,
  onStop,
  storageError,
  humanCheck,
  above,
  editing,
  onCancelEdit,
}: {
  composer: RefObject<HTMLTextAreaElement | null>;
  message: string;
  setMessage: (m: string) => void;
  settings: Settings;
  options: ReturnType<typeof useChatOptions>;
  pending: boolean;
  ready: boolean;
  hasConversation: boolean;
  hasFocus: boolean;
  onClearFocus: () => void;
  onSend: () => void;
  onStop: () => void;
  storageError: boolean;
  humanCheck: ReactNode;
  // Pinned just above the dock (Jump to latest), so the dock never covers it.
  above?: ReactNode;
  // Asking an earlier question again: it and every answer after it are replaced.
  editing: boolean;
  onCancelEdit: () => void;
}) {
  const { scope, setScope, depth, setDepth, mode, setMode, check, setCheck } = settings;
  const offered = options.available.filter((s) => SCOPES.includes(s.scope));
  const canCompare = ["shankara", "ramanuja"].every((k) =>
    offered.some((s) => s.scope === k),
  );
  useEffect(() => {
    const input = composer.current;
    if (input) {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    }
  }, [message]);
  const provider = options.provider;
  return (
    <div className="composer-dock">
      {above}
      <div className="chat-controls">
        {options.failed && (
          <p className="options-error" role="alert">
            Couldn’t load the answer options.{" "}
            <button type="button" onClick={options.retry}>
              <RotateCcw size={12} /> Retry
            </button>
          </p>
        )}
        {offered.length > 0 && (
          <div className="chip-row" role="radiogroup" aria-label="Ask within">
            {[{ scope: "all" as Scope, label: "All texts" }, ...offered].map((s) => (
              <button
                key={s.scope}
                type="button"
                role="radio"
                aria-checked={scope === s.scope}
                className="chip"
                onClick={() => setScope(s.scope)}
              >
                {s.label}
              </button>
            ))}
            {canCompare && (
              <button
                type="button"
                className="chip compare-chip"
                onClick={() => {
                  setScope("all");
                  setMessage(COMPARE);
                  composer.current?.focus();
                }}
              >
                Compare Śaṅkara &amp; Rāmānuja
              </button>
            )}
          </div>
        )}
        <div className="chip-row depth">
          <span role="radiogroup" aria-label="Answer length" className="chip-group">
            {DEPTHS.map(([d, label]) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={depth === d}
                className="chip"
                disabled={mode === "vichara"}
                title={mode === "vichara" ? "Vichāra sets its own length" : undefined}
                onClick={() => setDepth(d)}
              >
                {label}
              </button>
            ))}
          </span>
          <button
            type="button"
            className="chip"
            aria-pressed={mode === "vichara"}
            title="Vichāra: a short answer, then questions to reflect on from the same passages."
            onClick={() => setMode(mode === "vichara" ? "answer" : "vichara")}
          >
            Vichāra
          </button>
          <button
            type="button"
            className="chip"
            aria-pressed={check === "on"}
            title="A second pass removes sentences the passages do not support. Slower."
            onClick={() => setCheck(check === "on" ? "off" : "on")}
          >
            Check
          </button>
        </div>
      </div>
      {(mode === "vichara" || check === "on") && (
        <p className="mode-note">
          {mode === "vichara" &&
            "Vichāra: a short answer, then questions to reflect on from the same passages. "}
          {check === "on" &&
            "Check: a second pass removes sentences the passages do not support (slower), and Study shows which passage supports each sentence."}
        </p>
      )}
      {humanCheck}
      {editing && (
        <p className="focus-note" role="status">
          Editing an earlier question: its answer and the ones after it will be replaced.{" "}
          <button type="button" onClick={onCancelEdit}>
            Cancel
          </button>
        </p>
      )}
      {hasFocus && (
        <p className="focus-note" role="status">
          Asking about the passage you selected in Study.{" "}
          <button type="button" onClick={onClearFocus}>
            Ask without it
          </button>
        </p>
      )}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          onSend();
        }}
      >
        <label className="sr-only" htmlFor="message">
          Your question
        </label>
        <textarea
          ref={composer}
          id="message"
          placeholder={
            hasFocus
              ? "What would you like to understand about it?"
              : hasConversation
                ? "Keep the conversation going…"
                : "What would you like to understand?"
          }
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={1}
          maxLength={2000}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (!pending) onSend();
            }
          }}
        />
        {pending ? (
          <button
            type="button"
            className="send-button stop-button"
            onClick={onStop}
            aria-label="Stop answer"
          >
            <Square size={15} fill="currentColor" />
          </button>
        ) : (
          <button
            className="send-button"
            type="submit"
            disabled={!message.trim() || !ready}
            aria-label="Send message"
          >
            <ArrowUp size={19} />
          </button>
        )}
      </form>
      <div className="composer-caption">
        <span>
          {pending
            ? "Take a moment. Good questions are worth sitting with."
            : provider?.name === "openrouter"
              ? `Answers by ${provider.model} on OpenRouter's free plan: your question and public-domain passages are sent there; private books never are.`
              : "A conversation with the books in your local library."}
        </span>
        <span className="keyboard-hint">
          <CornerDownLeft size={11} /> to send <span>·</span> Shift + Enter for a new line
        </span>
      </div>
      {storageError && (
        <p className="storage-error" role="alert">
          Browser storage is unavailable. This conversation cannot survive a reload.
        </p>
      )}
    </div>
  );
}
