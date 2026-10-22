"""Explicitly labelled objection/reply roles in commentary text.

Only printed labels such as "Objection:" or "Answer:—", and the translator's explicit
role formulas at sentence start ("The pûrvapakshin maintains", "To this we reply"),
and standalone headings ("THE GREAT PÛRVAPAKSHA."),
are recognised; unlabelled text is never assigned a role by inference.
Offsets are Python code points.
"""

import re
from typing import Literal

Role = Literal["objection", "reply", "unmarked"]

OBJECTION = r"Objection|Question|Doubt|Opponent|P[uū]rvapak[sṣ]h?a|Prima facie view"
REPLY = r"Answer|Reply|Ans|Siddh[aā]nta"
MARKER = re.compile(
    r"(?:^|(?<=\n)|(?<=[.?!;] )|(?<=[.?!;][\"'’”] ))\s*\(?\s*"
    rf"(?:(?P<objection>{OBJECTION})|(?P<reply>{REPLY}))"
    r"\s*\)?\s*(?::\s*[—–-]*|—|–|--|\.\s*[—–-]+)"
)
START = r"(?:^|(?<=\n)|(?<=[.?!;] )|(?<=[.?!;][\"'’”] ))"
PHRASE = re.compile(
    START + r"(?:(?P<objection>(?:Here )?[Tt]he (?:p[uûū]rvapak[sṣ]h?in|opponent) "
    r"(?:maintains|says|argues|objects|holds|contends)\b)"
    r"|(?P<reply>To this(?: objection)? we (?:make the following reply|reply|answer)\b"
    r"|We reply\b))"
)
# Standalone printed headings, e.g. "THE GREAT PÛRVAPAKSHA." / "THE SMALL SIDDHÂNTA."
HEADING = re.compile(
    r"(?m)^(?:THE )?(?:[A-Z]+ )?(?:(?P<objection>P[UÛŪ]RVAPAK[SṢ]H?A)|(?P<reply>SIDDH[AÂĀ]NTA))\.?$"
)
LOOKBACK, LOOKAHEAD, FOLLOW = 3000, 1500, 700


def markers(text: str) -> list[tuple[int, Role]]:
    found = [*MARKER.finditer(text), *PHRASE.finditer(text), *HEADING.finditer(text)]
    return sorted((m.start(), "objection" if m["objection"] else "reply") for m in found)


def segments(text: str, initial: Role = "unmarked") -> list[dict]:
    """Split text at labels into consecutive {role, text} parts covering all of it."""
    found = markers(text)
    cuts = found if found[:1] and found[0][0] == 0 else [(0, initial), *found]
    parts = []
    for (start, role), (end, _) in zip(cuts, [*cuts[1:], (len(text), "unmarked")], strict=True):
        if end > start:  # Keep whitespace-only parts so segments rejoin exactly.
            parts.append({"role": role, "text": text[start:end]})
    return parts


def annotate(chapter_text: str, start: int, end: int) -> dict:
    """Roles for chapter_text[start:end], with the reply that follows a trailing objection.

    A role carries into the passage only from a label in the preceding LOOKBACK
    characters; a passage ending inside an objection includes the next labelled
    reply found within LOOKAHEAD characters, so objections are not read as conclusions.
    """
    before = markers(chapter_text[max(0, start - LOOKBACK) : start])
    parts = segments(chapter_text[start:end], before[-1][1] if before else "unmarked")
    result: dict = {"segments": parts}
    if parts and parts[-1]["role"] == "objection":
        ahead = chapter_text[end : end + LOOKAHEAD]
        replies = [i for i, role in markers(ahead) if role == "reply"]
        if replies:
            result["following_reply"] = ahead[replies[0] : replies[0] + FOLLOW]
    return result
