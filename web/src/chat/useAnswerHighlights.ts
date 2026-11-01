import { useEffect } from "react";
import type { StudyNote } from "../lib/notes.ts";

// Whitespace-collapsed text of an answer, with the DOM position of each character.
function flatten(box: Element) {
  const map: [Text, number][] = [];
  let flat = "";
  const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    if (node.parentElement?.closest(".term-card")) continue; // glossary card text
    for (let i = 0; i < node.data.length; i++) {
      const space = /\s/.test(node.data[i]);
      if (space && (flat.endsWith(" ") || !flat)) continue;
      flat += space ? " " : node.data[i];
      map.push([node, i]);
    }
  }
  return { flat, map };
}

// Draw saved highlights on the answers still in this conversation (CSS Highlight API:
// no change to the answer's markup; browsers without it simply show no tint). Every
// occurrence of a highlighted quote is tinted, and each answer is walked once.
export function useAnswerHighlights(notes: StudyNote[], redraw: unknown[]) {
  useEffect(() => {
    const registry = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
    const HighlightType = (window as unknown as { Highlight?: new (...r: Range[]) => unknown })
      .Highlight;
    if (!registry || !HighlightType) return;
    const byTurn = new Map<string, string[]>();
    for (const n of notes)
      if (n.kind === "answer" && n.turn_id && n.quote)
        byTurn.set(n.turn_id, [...(byTurn.get(n.turn_id) ?? []), n.quote]);
    // After paint: glossary annotation re-renders answers, replacing their text nodes.
    const frame = requestAnimationFrame(() => {
      const ranges: Range[] = [];
      for (const [turn, quotes] of byTurn) {
        const box = document.querySelector(`[data-turn="${CSS.escape(turn)}"] .answer-prose`);
        if (!box) continue;
        const { flat, map } = flatten(box);
        for (const quote of new Set(quotes)) {
          for (let at = flat.indexOf(quote); at >= 0; at = flat.indexOf(quote, at + quote.length)) {
            const range = document.createRange();
            const [startNode, startOffset] = map[at];
            const [endNode, endOffset] = map[at + quote.length - 1];
            range.setStart(startNode, startOffset);
            range.setEnd(endNode, endOffset + 1);
            ranges.push(range);
          }
        }
      }
      registry.set("pramana-note", new HighlightType(...ranges));
    });
    return () => cancelAnimationFrame(frame);
  }, [notes, ...redraw]);
}
