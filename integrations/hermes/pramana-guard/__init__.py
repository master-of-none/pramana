"""pramana-guard: a Hermes plugin that keeps the bot to Pramana's texts, whatever the model does.

A prompt can be argued with; these hooks cannot. They run in Hermes, around the model:

- ``pre_tool_call``: the only tools allowed are reading skills, saving memory, and one terminal
  command shape, a read-only ``curl`` to the Pramana excerpt API. Everything else (running code,
  files, the web, editing skills, creating cron jobs, any other command) is blocked. Hermes
  blocks the tool if this hook errors or times out.
- ``transform_llm_output``: the model's reply is never sent as written. The bot sends the
  excerpt(s) Pramana returned in this turn, a fixed note, or the app's own refusal. Hermes skips
  a hook that raises, which would let the model's text through, so every error here returns the
  refusal instead.
- ``post_gateway_admission``: a greeting or "help" gets fixed help text without the model.

Standard library only. Install by copying this folder to ``~/.hermes/plugins/pramana-guard/``,
then ``hermes plugins enable pramana-guard`` and ``hermes gateway restart``.
"""

import json
import logging
import re
import threading
import time

# Word for word the Pramana chat's reply to an unrelated question (pramana.answering.UNRELATED).
REFUSAL = (
    "Neti, neti: not this, not this. I give knowledge, but this is not the knowledge you "
    "seek. For that, another teacher awaits; for the Self, Brahman, or what the sages "
    "taught, ask me."
)
HELP = (
    "Ask me for today's verse, another one, or a few verses about a theme, for example: "
    '"three verses about fear".'
)
NOTED = "Noted."
NOT_FOUND = "The texts have nothing for that. Try other words."
UNAVAILABLE = "The texts cannot be reached right now. Try again later."
SHOW_SOURCE = False  # True: also send each excerpt's reference line
KEEP_SECONDS = 900  # a fetched excerpt is never reused after this, even within a turn

SAFE_TOOLS = {"memory", "skill_view", "skills_list"}
COMMAND = re.compile(
    r'curl -fsS -H "Authorization: Bearer \$PRAMANA_AGENT_TOKEN" '
    r'"\$PRAMANA_URL/api/excerpts/(?:today|random|search)\?[\w=&%+.,:/\-]*"'
)
GREETING = re.compile(
    r"^\s*(hi|hello|hey|namaste|namaskar|namaskaram|hari om|help|start|/start|/help)\s*[!.?]*\s*$",
    re.IGNORECASE,
)
BLOCKED = (
    "Blocked by pramana-guard. The only command allowed is the pramana-excerpt curl, written "
    "exactly as in the skill, with format=text or format=json and + between words."
)

log = logging.getLogger("pramana_guard")
_lock = threading.Lock()
_state: dict = {}


def _reset() -> None:
    with _lock:
        _state.clear()
        _state.update(turn=0.0, message=None, outputs=[], memory=0.0)


_reset()


def allowed_command(command: object) -> bool:
    """The whole command must be the one read-only curl shape, and nothing more."""
    if not isinstance(command, str) or not COMMAND.fullmatch(command.strip()):
        return False
    formats = re.findall(r"format=(\w+)", command)
    return len(formats) == 1 and formats[0] in ("text", "json")


def _is_terminal(name: str) -> bool:
    name = name.lower()
    return "terminal" in name or "shell" in name or name == "bash"


def _command(args: object) -> object:
    if not isinstance(args, dict):
        return None
    for key in ("command", "cmd"):
        if key in args:
            return args[key]
    strings = [v for v in args.values() if isinstance(v, str)]
    return strings[0] if len(strings) == 1 else None


def _text(result: object) -> str:
    """The command's output, whether the tool returns plain text or a JSON envelope."""
    if not isinstance(result, str):
        result = json.dumps(result) if isinstance(result, (dict, list)) else str(result or "")
    try:
        data = json.loads(result)
    except ValueError:
        return result
    if isinstance(data, dict):
        for key in ("output", "stdout", "result", "content"):
            if isinstance(data.get(key), str):
                return data[key]
    return result


def _mark_turn() -> None:
    with _lock:
        _state["turn"] = time.time()


def render(output: str) -> str | None:
    """What to send for one Pramana output; None if it holds no excerpt."""
    text = output.strip()
    if text.startswith("curl:") or "returned error" in text:
        return NOT_FOUND if re.search(r"error:? 404", text) else UNAVAILABLE
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        items = data["results"] if isinstance(data.get("results"), list) else [data]
        blocks = []
        for number, item in enumerate(items, 1):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                return None
            block = "“" + " ".join(item["text"].split()) + "”"
            if len(items) > 1:
                block = f"{number}. {block}"
            if SHOW_SOURCE and isinstance(item.get("reference"), str):
                block += f"\n— {item['reference']}"
            blocks.append(block)
        return "\n\n".join(blocks) or None
    if SHOW_SOURCE:
        return text if text.lstrip().startswith(("“", "1.")) else None
    quotes = [line.strip() for line in text.splitlines() if re.match(r"\s*(\d+\.\s*)?“", line)]
    return "\n\n".join(quotes) or None


def decide() -> str:
    """The reply for this turn, built only from what Pramana returned."""
    with _lock:
        since = max(_state["turn"], time.time() - KEEP_SECONDS)
        outputs = [text for at, text in _state["outputs"] if at >= since]
        noted = _state["memory"] >= _state["turn"]
    for output in reversed(outputs):
        reply = render(output)
        if reply:
            return reply
    return NOTED if noted else REFUSAL


def on_pre_tool_call(**kwargs):
    try:
        name = str(kwargs.get("tool_name") or "")
        args = kwargs.get("args", kwargs.get("params"))
        if name in SAFE_TOOLS:
            return None
        if _is_terminal(name) and allowed_command(_command(args)):
            return None
        log.warning("pramana-guard blocked tool %r", name)
    except Exception:
        log.exception("pramana-guard failed in pre_tool_call; blocking")
    return {"action": "block", "message": BLOCKED}


def on_post_tool_call(**kwargs):
    try:
        name = str(kwargs.get("tool_name") or "")
        args = kwargs.get("args", kwargs.get("params"))
        now = time.time()
        with _lock:
            _state["outputs"] = [o for o in _state["outputs"] if o[0] >= now - KEEP_SECONDS]
            if name in ("memory",):
                _state["memory"] = now
            elif _is_terminal(name) and allowed_command(_command(args)):
                _state["outputs"].append((now, _text(kwargs.get("result"))))
    except Exception:
        log.exception("pramana-guard failed in post_tool_call")


def on_pre_llm_call(**kwargs):
    try:
        message = kwargs.get("user_message")
        with _lock:
            if message != _state["message"]:
                _state["message"] = message
                _state["turn"] = time.time()
    except Exception:
        log.exception("pramana-guard failed in pre_llm_call")


def on_transform_llm_output(**kwargs):
    try:
        reply = decide()
    except Exception:
        log.exception("pramana-guard failed in transform_llm_output; refusing")
        return REFUSAL
    if reply != kwargs.get("response_text"):
        log.info("pramana-guard replaced the model's reply")
    return reply


def on_post_gateway_admission(**kwargs):
    try:
        _mark_turn()
        with _lock:
            _state["message"] = None
        if GREETING.match(str(kwargs.get("text") or "")):
            return {"action": "handled", "reply": HELP}
    except Exception:
        log.exception("pramana-guard failed in post_gateway_admission")
    return None


def register(ctx):
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("transform_llm_output", on_transform_llm_output)
    ctx.register_hook("post_gateway_admission", on_post_gateway_admission)
    log.warning("pramana-guard active: replies are limited to Pramana's texts")
