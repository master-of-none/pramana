// Opening words of an argument step. A leading cue sentence ("To this we make the
// following reply.", "THE GREAT PÛRVAPAKSHA.") is skipped when content follows it.
// Only a sentence that is nothing but a cue is skipped.
const CUE =
  /^(?:the (?:great |small )?(?:p[uûū]rvapak[sṣ]h?a|siddh[aâā]nta)|to this(?: objection)? we (?:make the following reply|reply|answer)|we reply)[.:]?$/i;

// A reply formula run together with its content ("…reply:--In the passage…").
const PREFIX =
  /^(?:to this(?: objection)? we (?:make the following reply|reply|answer)|we reply)\s*[:.]?\s*(?:-{2}|[—–])\s*/i;

export function opening(text: string, limit = 150): string {
  const clean = text
    .replace(/\s+/g, " ")
    .trim()
    .replace(PREFIX, "")
    .replace(/^[-—–:\s]+/, "");
  const sentences = clean
    .match(/[^.?!]+(?:[.?!]+|$)/g)
    ?.map((s) => s.trim()) ?? [clean];
  let first = sentences[0] ?? "";
  if (sentences.length > 1 && first.length <= 60 && CUE.test(first))
    first = sentences[1];
  if (first.length <= limit) return first;
  const cut = first.lastIndexOf(" ", limit);
  return first.slice(0, cut > 0 ? cut : limit) + "…";
}
