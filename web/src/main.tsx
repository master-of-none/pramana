import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  Copy,
  CornerDownLeft,
  Feather,
  Plus,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import "./style.css";

type Turn = {
  id: string;
  question: string;
  answer?: string;
  state: "complete" | "pending" | "error" | "cancelled";
  error?: string;
  stage?: Stage;
};
type Stage = "understanding" | "searching" | "composing";
const stageLabels: Record<Stage, string> = {
  understanding: "Following the thread of your question…",
  searching: "Searching the texts…",
  composing: "Composing an answer…",
};
type ChatResponse = {
  answer: string;
  status: "grounded" | "insufficient_evidence";
};
const STORAGE = "pramana.conversation.v1";
const suggestions = [
  {
    topic: "JÑĀNA & KARMA",
    question: "Why does Shankara say action alone cannot lead to liberation?",
  },
  {
    topic: "BRAHMAN AS BLISS",
    question: "What does the Ananda-valli teach about Brahman as bliss?",
  },
  {
    topic: "THE UNCHANGING SELF",
    question:
      "How does Shankara explain that the Self neither acts nor is acted upon?",
  },
  {
    topic: "ACTION WITHOUT ATTACHMENT",
    question: "How does Chinmayananda explain acting without attachment?",
  },
];

function restore(): Turn[] {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(STORAGE) || "[]");
    if (!Array.isArray(data)) return [];
    return data.slice(-60).flatMap((t) => {
      if (
        !t ||
        typeof t.id !== "string" ||
        typeof t.question !== "string" ||
        t.question.length > 2000
      )
        return [];
      if (
        t.state === "complete" &&
        typeof t.answer === "string" &&
        t.answer.length <= 6000
      )
        return [
          {
            id: t.id,
            question: t.question,
            answer: t.answer,
            state: "complete",
          } as Turn,
        ];
      return [
        {
          id: t.id,
          question: t.question,
          state: "cancelled",
          error: "This answer was interrupted. You can try again.",
        } as Turn,
      ];
    });
  } catch {
    return [];
  }
}

type GlossaryTerm = {
  term: string;
  devanagari: string;
  aliases: string[];
  meaning: string;
};
type Glossary = { pattern: RegExp; lookup: Map<string, GlossaryTerm> };
const fold = (text: string) =>
  text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();

function buildGlossary(terms: GlossaryTerm[]): Glossary | null {
  const lookup = new Map<string, GlossaryTerm>();
  for (const t of terms)
    for (const name of [t.term, ...t.aliases]) lookup.set(fold(name), t);
  if (!lookup.size) return null;
  const names = terms
    .flatMap((t) => [t.term, ...t.aliases])
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return {
    pattern: new RegExp(
      `(?<![\\p{L}\\p{M}])(${names.join("|")})(?![\\p{L}\\p{M}])`,
      "giu",
    ),
    lookup,
  };
}

// Marks the first mention of each concept; a general glossary, not a source.
function annotate(raw: string, glossary: Glossary | null, seen: Set<string>) {
  const text = raw.normalize("NFC");
  if (!glossary) return [text];
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(glossary.pattern)) {
    const entry = glossary.lookup.get(fold(match[0]));
    if (!entry || seen.has(entry.term)) continue;
    seen.add(entry.term);
    out.push(text.slice(last, match.index));
    out.push(
      <span className="term" key={`${entry.term}-${match.index}`}>
        <button type="button" className="term-word">
          {match[0]}
        </button>
        <span className="term-card" role="tooltip">
          <span className="term-name">
            {entry.term}
            {entry.devanagari && <span lang="sa"> · {entry.devanagari}</span>}
          </span>
          {entry.meaning}
        </span>
      </span>,
    );
    last = match.index! + match[0].length;
  }
  out.push(text.slice(last));
  return out;
}

function inline(
  text: string,
  glossary: Glossary | null = null,
  seen = new Set<string>(),
) {
  return text
    .split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g)
    .map((part, i) =>
      part.startsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : /^([*_]).+\1$/.test(part) ? (
        <em key={i}>{part.slice(1, -1)}</em>
      ) : (
        <span key={i}>{annotate(part, glossary, seen)}</span>
      ),
    );
}
function Answer({
  text,
  glossary,
}: {
  text: string;
  glossary: Glossary | null;
}) {
  const seen = new Set<string>();
  return (
    <div className="answer-prose">
      {text.split(/\n\s*\n/).map((block, i) => {
        const lines = block.split("\n");
        const heading = /^#{1,6}\s+(.+)$/.exec(block.trim());
        if (heading && lines.length === 1)
          return <h3 key={i}>{inline(heading[1], glossary, seen)}</h3>;
        const ordered = lines.every((line) => /^\s*\d+[.)]\s+/.test(line));
        if (ordered || lines.every((line) => /^\s*[-*•]\s+/.test(line))) {
          const List = ordered ? "ol" : "ul";
          return (
            <List key={i}>
              {lines.map((line, j) => (
                <li key={j}>
                  {inline(
                    line.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""),
                    glossary,
                    seen,
                  )}
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={i}>
            {inline(block.replace(/^#{1,6}\s+/gm, ""), glossary, seen)}
          </p>
        );
      })}
    </div>
  );
}

function App() {
  const [turns, setTurns] = useState<Turn[]>(restore);
  const [message, setMessage] = useState("");
  const [storageError, setStorageError] = useState(false);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  const [glossary, setGlossary] = useState<Glossary | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const controller = useRef<AbortController | null>(null);
  const requestNumber = useRef(0);
  const pending = turns.some((t) => t.state === "pending");
  const hasConversation = turns.length > 0;

  useEffect(() => {
    // Optional enhancement: answers render normally if the glossary is unavailable.
    fetch("/api/glossary")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => Array.isArray(data) && setGlossary(buildGlossary(data)))
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE, JSON.stringify(turns.slice(-60)));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [turns]);
  useEffect(() => {
    bottom.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "end",
    });
  }, [turns]);
  useEffect(() => {
    const input = composer.current;
    if (input) {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
    }
  }, [message]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        composer.current?.focus();
      }
      if (event.key === "Escape") controller.current?.abort();
    };
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("keydown", key);
      controller.current?.abort();
    };
  }, []);

  async function send(text: string, retryId?: string) {
    if (!text.trim() || controller.current) return;
    const previous = retryId
      ? turns.slice(
          0,
          turns.findIndex((t) => t.id === retryId),
        )
      : turns;
    const history = previous
      .filter((t) => t.state === "complete")
      .slice(-6)
      .flatMap((t) => [
        { role: "user", content: t.question },
        { role: "assistant", content: t.answer! },
      ]);
    const id = retryId || crypto.randomUUID();
    const abort = new AbortController();
    controller.current = abort;
    const number = ++requestNumber.current;
    setTurns([...previous, { id, question: text.trim(), state: "pending" }]);
    setMessage("");
    const update = (value: Partial<Turn>) => {
      if (requestNumber.current === number)
        setTurns((current) =>
          current.map((t) => (t.id === id ? { ...t, ...value } : t)),
        );
    };
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abort.signal,
        body: JSON.stringify({ message: text.trim(), history }),
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The question could not be processed. Try a shorter question.",
        );
      }
      let result: ChatResponse | undefined;
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        buffer += value ?? "";
        const lines = done ? [buffer] : buffer.split("\n");
        buffer = done ? "" : lines.pop()!;
        for (const line of lines.filter((l) => l.trim())) {
          const event = JSON.parse(line);
          if (event.type === "stage" && event.stage in stageLabels)
            update({ stage: event.stage });
          else if (event.type === "error")
            throw new Error(
              typeof event.detail === "string"
                ? event.detail
                : "The question could not be processed. Please retry.",
            );
          else if (event.type === "answer") result = event;
        }
        if (done) break;
      }
      if (
        !result ||
        typeof result.answer !== "string" ||
        !["grounded", "insufficient_evidence"].includes(result.status)
      )
        throw new Error("The answer was incomplete. Please retry.");
      update({
        state: "complete",
        answer: result.answer,
        error: undefined,
        stage: undefined,
      });
    } catch (error) {
      if (abort.signal.aborted)
        update({
          state: "cancelled",
          error: "Answer stopped. You can try again whenever you’re ready.",
        });
      else
        update({
          state: "error",
          error:
            error instanceof TypeError
              ? "Pramana is unreachable. Check that the local server is running, then retry."
              : (error as Error).message,
        });
    } finally {
      if (requestNumber.current === number) {
        controller.current = null;
        composer.current?.focus();
      }
    }
  }
  function newChat() {
    requestNumber.current++;
    controller.current?.abort();
    controller.current = null;
    setTurns([]);
    setMessage("");
    setCopyError("");
    try {
      sessionStorage.removeItem(STORAGE);
    } catch {
      /* The in-memory chat still resets. */
    }
    composer.current?.focus();
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void send(message);
  }
  async function copy(turn: Turn) {
    try {
      await navigator.clipboard.writeText(turn.answer!);
      setCopied(turn.id);
      setCopyError("");
    } catch {
      setCopyError("Copy is unavailable. Select the answer text to copy it.");
    }
  }

  return (
    <div className={`app ${hasConversation ? "in-conversation" : "welcome"}`}>
      <a className="skip-link" href="#message">
        Skip to message
      </a>
      <header className="topbar">
        <button
          className="brand"
          onClick={newChat}
          aria-label="Pramana, new chat"
        >
          <span className="brand-mark">प्र</span>
          <span className="brand-name">
            pramāṇa<span className="brand-sub">A SPACE FOR UNDERSTANDING</span>
          </span>
        </button>
        <div className="topbar-right">
          <span className="local-badge">
            <span /> On your device
          </span>
          <button className="new-chat" onClick={newChat}>
            <Plus size={16} />
            <span>New chat</span>
          </button>
        </div>
      </header>
      <main id="main">
        {!hasConversation ? (
          <section className="welcome-section" aria-label="Welcome">
            <div className="welcome-symbol">
              <BookOpen size={28} strokeWidth={1.25} />
              <span className="symbol-ray ray-one" />
              <span className="symbol-ray ray-two" />
              <span className="symbol-ray ray-three" />
            </div>
            <div className="eyebrow">
              <span /> THE READING ROOM
            </div>
            <h1>
              Old wisdom.
              <br />
              <em>New conversations.</em>
            </h1>
            <p className="welcome-copy">
              A little curiosity can open a whole world.
              <br />
              Ask a question. Follow an idea. Make room for understanding.
            </p>
            <div className="suggestions" aria-label="Suggested questions">
              {suggestions.map((s) => (
                <button key={s.topic} onClick={() => void send(s.question)}>
                  <span className="suggestion-topic">{s.topic}</span>
                  <span className="suggestion-question">{s.question}</span>
                  <ArrowRight size={17} />
                </button>
              ))}
            </div>
            <div className="welcome-footnote">
              <Feather size={15} />
              <span>Read slowly. Ask freely. Think deeply.</span>
            </div>
          </section>
        ) : (
          <section
            className="conversation"
            aria-label="Conversation"
            aria-busy={pending}
          >
            <div className="conversation-kicker">
              <span /> A THREAD OF INQUIRY
            </div>
            {turns.map((turn, index) => (
              <article
                className="turn"
                key={turn.id}
                aria-label={`Exchange ${index + 1}`}
              >
                <div className="user-turn">
                  <span className="turn-label">YOU</span>
                  <p>{turn.question}</p>
                </div>
                <div className="assistant-turn">
                  <div className="assistant-heading">
                    <span className="mini-mark">प्र</span>
                    <span>PRAMĀṆA</span>
                    <span className="answer-line" />
                  </div>
                  {turn.state === "complete" && (
                    <>
                      <Answer text={turn.answer!} glossary={glossary} />
                      <button
                        className="copy-answer"
                        onClick={() => void copy(turn)}
                        aria-label="Copy answer"
                      >
                        {copied === turn.id ? (
                          <Check size={14} />
                        ) : (
                          <Copy size={14} />
                        )}
                        {copied === turn.id ? "Copied" : "Copy answer"}
                      </button>
                    </>
                  )}
                  {turn.state === "pending" && (
                    <div className="thinking" role="status">
                      <span className="thinking-dots">
                        <i />
                        <i />
                        <i />
                      </span>
                      <span>
                        {turn.stage
                          ? stageLabels[turn.stage]
                          : "Reading and reflecting…"}
                      </span>
                    </div>
                  )}
                  {(turn.state === "error" || turn.state === "cancelled") && (
                    <div className={`turn-notice ${turn.state}`}>
                      <p role={turn.state === "error" ? "alert" : "status"}>
                        {turn.error}
                      </p>
                      {index === turns.length - 1 && !pending && (
                        <button
                          onClick={() => void send(turn.question, turn.id)}
                        >
                          <RotateCcw size={14} />
                          Try again
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </article>
            ))}
            {copyError && (
              <p className="small-notice" role="alert">
                {copyError}
                <button
                  aria-label="Dismiss copy error"
                  onClick={() => setCopyError("")}
                >
                  <X size={14} />
                </button>
              </p>
            )}
            <div ref={bottom} className="conversation-bottom" />
          </section>
        )}
      </main>
      <div className="composer-dock">
        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="message">
            Your question
          </label>
          <textarea
            ref={composer}
            id="message"
            placeholder={
              hasConversation
                ? "Keep the conversation going…"
                : "What would you like to understand?"
            }
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={1}
            maxLength={2000}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                if (!pending) void send(message);
              }
            }}
          />
          {pending ? (
            <button
              type="button"
              className="send-button stop-button"
              onClick={() => controller.current?.abort()}
              aria-label="Stop answer"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              className="send-button"
              type="submit"
              disabled={!message.trim()}
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
              : "A conversation with the books in your local library."}
          </span>
          <span className="keyboard-hint">
            <CornerDownLeft size={11} /> to send <span>·</span> Shift + Enter
            for a new line
          </span>
        </div>
        {storageError && (
          <p className="storage-error" role="alert">
            Browser storage is unavailable. This conversation cannot survive a
            reload.
          </p>
        )}
      </div>
      <footer className="page-footer">
        <span>
          प्रमाण <span className="footer-divider">/</span> a means of knowledge
        </span>
        <span>Stay curious.</span>
      </footer>
      {hasConversation && (
        <button
          className="jump-bottom"
          aria-label="Jump to latest message"
          onClick={() => bottom.current?.scrollIntoView({ behavior: "smooth" })}
        >
          <ArrowDown size={16} />
        </button>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
