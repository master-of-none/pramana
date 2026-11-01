import { ArrowRight, BookOpen, Feather } from "lucide-react";

// Themed starters (docs/plans/ux.md): the Self, Brahman, māyā, liberation, and the two
// commentators compared.
const suggestions = [
  {
    topic: "THE SELF",
    question: "How does Shankara explain that the Self neither acts nor is acted upon?",
  },
  {
    topic: "BRAHMAN",
    question: "What does the Ananda-valli teach about Brahman as bliss?",
  },
  {
    topic: "MĀYĀ",
    question: "What is māyā, and how can the world appear if only Brahman is real?",
  },
  {
    topic: "LIBERATION",
    question: "Why does Shankara say action alone cannot lead to liberation?",
  },
  {
    topic: "TWO READINGS",
    question: "How do Śaṅkara and Rāmānuja differ on the relation of the self to Brahman?",
  },
];

export function Welcome({ onAsk }: { onAsk: (question: string) => void }) {
  return (
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
          <button key={s.topic} onClick={() => onAsk(s.question)}>
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
  );
}
