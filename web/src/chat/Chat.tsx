import { useEffect, useRef, useState } from "react";
import { ArrowDown, Download, X } from "lucide-react";
import { useGlossary } from "../lib/glossary.tsx";
import { useHumanCheck } from "../lib/hosted.ts";
import { isShortcut } from "../lib/keys.ts";
import { ASK, EXPORT } from "../components/Palette.tsx";
import { useNotes } from "../lib/notes.ts";
import { conversationMarkdown, takePendingFocus } from "../lib/storage.ts";
import { download } from "../lib/notes.ts";
import type { FocusRef, Turn } from "../lib/storage.ts";
import { usePreference } from "../lib/theme.ts";
import { Composer, DEPTHS, SCOPES, useChatOptions } from "./Composer.tsx";
import { NoteEditor, SelectionTools, quoteFromSelection } from "./SelectionPopover.tsx";
import type { Noting, Quote } from "./SelectionPopover.tsx";
import { TurnView } from "./Turn.tsx";
import { Welcome } from "./Welcome.tsx";
import { useAnswerHighlights } from "./useAnswerHighlights.ts";
import { useChatSession } from "./useChatSession.ts";
import type { Depth, Mode, Scope } from "./useChatSession.ts";

export function Chat({
  active,
  registerNewChat,
}: {
  active: boolean;
  registerNewChat: (reset: () => void) => void;
}) {
  const composer = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const session = useChatSession(() => composer.current?.focus());
  const { turns, pending } = session;
  const [message, setMessage] = useState("");
  // "Ask about this passage" from Study: a pointer sent with the next question only.
  const [focus, setFocus] = useState<FocusRef | null>(null);
  // Words selected in an answer, and a note being written on them.
  const [quote, setQuote] = useState<Quote | null>(null);
  const [noting, setNoting] = useState<Noting | null>(null);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  const [atBottom, setAtBottom] = useState(true);
  // An earlier question being asked again (its turn id).
  const [editing, setEditing] = useState<string | null>(null);
  const study = useNotes();
  const glossary = useGlossary();
  const human = useHumanCheck();
  const options = useChatOptions();
  const none = () => {};
  const [scope, setScope] = usePreference<Scope>("pramana.scope", SCOPES, "all", none);
  const [depth, setDepth] = usePreference<Depth>(
    "pramana.depth",
    DEPTHS.map(([d]) => d),
    "explain",
    none,
  );
  const [mode, setMode] = usePreference<Mode>("pramana.mode", ["answer", "vichara"], "answer", none);
  const [check, setCheck] = usePreference<"on" | "off">("pramana.check", ["on", "off"], "off", none);
  const activeScope =
    scope === "all" || options.available.some((s) => s.scope === scope) ? scope : "all";
  const hasConversation = turns.length > 0;
  const last = turns.at(-1);

  useAnswerHighlights(study.notes, [turns, glossary]);
  useEffect(() => {
    if (!active) return;
    const pendingFocus = takePendingFocus();
    if (pendingFocus) {
      setFocus(pendingFocus);
      composer.current?.focus();
    }
  }, [active]);
  // Follow the conversation when a question is asked or answered, not on every stage.
  useEffect(() => {
    bottom.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "end",
    });
  }, [turns.length, last?.state]);
  // "Jump to latest" only while the end of the thread is out of view.
  useEffect(() => {
    const end = bottom.current;
    if (!end) return;
    const observer = new IntersectionObserver(([entry]) => setAtBottom(entry.isIntersecting), {
      rootMargin: "0px 0px 160px 0px",
    });
    observer.observe(end);
    return () => observer.disconnect();
  }, [hasConversation]);
  useEffect(() => {
    if (!quote) return;
    // The tools are fixed to the viewport: follow the selection when the page moves.
    let frame = 0;
    const follow = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setQuote(quoteFromSelection()));
    };
    window.addEventListener("scroll", follow, { capture: true, passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", follow, { capture: true });
    };
  }, [!!quote]);
  const state = useRef({ active, quote, noting });
  state.current = { active, quote, noting };
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (!state.current.active || event.defaultPrevented) return;
      if (event.key === "/" && isShortcut(event)) {
        event.preventDefault();
        composer.current?.focus();
      }
      if (event.key !== "Escape") return;
      // An open popover closes first; only then does Escape stop the answer.
      if (state.current.noting) setNoting(null);
      else if (state.current.quote) setQuote(null);
      else session.stop();
    };
    window.addEventListener("keydown", key);
    // "Ask" from the command palette: the words go into the box, not straight out.
    const fill = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (text) setMessage(text);
      requestAnimationFrame(() => composer.current?.focus());
    };
    window.addEventListener(ASK, fill);
    window.addEventListener(EXPORT, exportChat.current);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener(ASK, fill);
      window.removeEventListener(EXPORT, exportChat.current);
    };
  }, []);

  async function send(text: string, from?: string) {
    const asked = from ? turns.find((t) => t.id === from)?.focus : (focus ?? undefined);
    if (!text.trim() || pending) return;
    setMessage("");
    setFocus(null);
    setEditing(null);
    await session.send(
      text,
      {
        scope: activeScope,
        depth,
        check: check === "on",
        mode,
        focus: asked,
        headers: human.headers,
      },
      from,
    );
    human.reset(); // Single-use token, even when the request failed.
  }
  function newChat() {
    setFocus(null);
    setEditing(null);
    session.reset();
    setMessage("");
    setCopyError("");
    composer.current?.focus();
  }
  registerNewChat(newChat);
  // Saved as Markdown by the reader: questions and answers, never the evidence pointers.
  const exportChat = useRef(() => {});
  exportChat.current = () => {
    if (!turns.length) return;
    const day = new Date().toISOString().slice(0, 10);
    download(`pramana-conversation-${day}.md`, "text/markdown", conversationMarkdown(turns));
  };
  function editQuestion(turn: Turn) {
    setEditing(turn.id);
    setFocus(null);
    setMessage(turn.question);
    requestAnimationFrame(() => {
      const input = composer.current;
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    });
  }
  function onAnswerSelect() {
    setQuote(noting ? null : quoteFromSelection());
  }
  function askAboutQuote() {
    if (!quote) return;
    const prefix = `About “${quote.text}”: `;
    setMessage(message.trim() ? `${message.trim()} ${prefix}` : prefix);
    setQuote(null);
    window.getSelection()?.removeAllRanges();
    requestAnimationFrame(() => {
      const input = composer.current;
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    });
  }
  // Highlights and notes on answers are saved to My notes with the question they answered.
  function saveQuote(q: Quote, note: string) {
    study.add({
      kind: "answer",
      turn_id: q.turn,
      question: turns.find((t) => t.id === q.turn)?.question ?? "",
      quote: q.full,
      note,
    });
    window.getSelection()?.removeAllRanges();
  }
  async function copy(turn: Turn) {
    try {
      await navigator.clipboard.writeText(
        [turn.answer!, ...(turn.perspectives ?? []).map((p) => `${p.thinker}\n${p.view}`)].join(
          "\n\n",
        ),
      );
      setCopied(turn.id);
      setCopyError("");
    } catch {
      setCopyError("Copy is unavailable. Select the answer text to copy it.");
    }
  }

  return (
    <div className={`view ${hasConversation ? "in-conversation" : "welcome"}`} hidden={!active}>
      <a className="skip-link" href="#message">
        Skip to message
      </a>
      <main id="main">
        {!hasConversation ? (
          <Welcome onAsk={(q) => void send(q)} />
        ) : (
          <section
            className="conversation"
            aria-label="Conversation"
            aria-busy={pending}
            onMouseUp={onAnswerSelect}
            onKeyUp={onAnswerSelect}
            onTouchEnd={() => setTimeout(onAnswerSelect, 0)}
          >
            {quote && (
              <SelectionTools
                quote={quote}
                onAsk={askAboutQuote}
                onHighlight={() => {
                  saveQuote(quote, "");
                  setQuote(null);
                }}
                onNote={() => {
                  setNoting({ ...quote, note: "" });
                  setQuote(null);
                }}
                onClose={() => setQuote(null)}
              />
            )}
            {noting && (
              <NoteEditor
                noting={noting}
                onChange={(note) => setNoting({ ...noting, note })}
                onSave={() => {
                  saveQuote(noting, noting.note.trim());
                  setNoting(null);
                }}
                onClose={() => setNoting(null)}
              />
            )}
            <div className="conversation-kicker">
              <span /> A THREAD OF INQUIRY
              <button
                type="button"
                className="export-chat"
                onClick={() => exportChat.current()}
                disabled={pending}
              >
                <Download size={12} /> Save as Markdown
              </button>
            </div>
            {turns.map((turn, index) => (
              <TurnView
                key={turn.id}
                turn={turn}
                index={index}
                canRetry={index === turns.length - 1 && !pending}
                canEdit={!pending && turn.state !== "pending"}
                copied={copied === turn.id}
                glossary={glossary}
                onCopy={() => void copy(turn)}
                onRetry={() => void send(turn.question, turn.id)}
                onEdit={() => editQuestion(turn)}
              />
            ))}
            {copyError && (
              <p className="small-notice" role="alert">
                {copyError}
                <button aria-label="Dismiss copy error" onClick={() => setCopyError("")}>
                  <X size={14} />
                </button>
              </p>
            )}
            <p className="sr-only" aria-live="polite">
              {copied ? "Answer copied." : ""}
            </p>
            <div ref={bottom} className="conversation-bottom" />
          </section>
        )}
      </main>
      <Composer
        composer={composer}
        message={message}
        setMessage={setMessage}
        settings={{
          scope: activeScope,
          setScope,
          depth,
          setDepth,
          mode,
          setMode,
          check,
          setCheck,
        }}
        options={options}
        pending={pending}
        ready={human.ready}
        hasConversation={hasConversation}
        hasFocus={!!focus}
        onClearFocus={() => setFocus(null)}
        onSend={() => void send(message, editing ?? undefined)}
        editing={!!editing}
        onCancelEdit={() => {
          setEditing(null);
          setMessage("");
        }}
        onStop={session.stop}
        storageError={session.storageError}
        humanCheck={human.hosted && <div className="human-check" ref={human.holder} />}
        above={
          hasConversation &&
          !atBottom && (
            <button
              className="jump-bottom"
              aria-label="Jump to latest message"
              onClick={() => bottom.current?.scrollIntoView({ behavior: "smooth" })}
            >
              <ArrowDown size={16} />
            </button>
          )
        }
      />
      <footer className="page-footer">
        <span>
          प्रमाण <span className="footer-divider">/</span> a means of knowledge
        </span>
        <span>Stay curious.</span>
      </footer>
    </div>
  );
}
