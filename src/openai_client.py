"""Volání OpenAI s ošetřením pastí reasoning modelů (prázdný text, žádné temperature)."""
import json
import logging

from openai import OpenAI

from config_loader import secret

log = logging.getLogger("openai")

_client = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=secret("OPENAI_API_KEY"))
    return _client


def chat(model: str, system: str, user: str, max_tokens: int, json_mode: bool = False, effort: str | None = None) -> str:
    """Vrátí text odpovědi. Při prázdné odpovědi vyhodí chybu místo tichého selhání."""
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}  # přes extra_body funguje s každou verzí knihovny
    resp = client().chat.completions.create(**kwargs)
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    usage = getattr(resp, "usage", None)
    reasoning = None
    if usage is not None:
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details else None
    log.info("model=%s finish=%s reasoning_tokens=%s délka=%d", model, choice.finish_reason, reasoning, len(text))
    if not text:
        raise RuntimeError(f"Model {model} vrátil prázdný text (finish_reason={choice.finish_reason}). Zvyšte max_tokens v settings.yaml.")
    return text


def chat_json(model: str, system: str, user: str, max_tokens: int, effort: str | None = None) -> dict:
    text = chat(model, system, user, max_tokens, json_mode=True, effort=effort)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
