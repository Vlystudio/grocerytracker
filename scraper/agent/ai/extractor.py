"""AI extraction with graceful fallback: Ollama -> OpenAI -> Anthropic.

Each provider is asked for strict JSON; the result is validated against the
`AIExtraction` model. If every provider is unavailable/fails, we degrade
gracefully and return an empty extraction (the parser-derived fields still get
stored), so a missing AI layer never blocks the pipeline.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import requests
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..config import settings
from ..logging_conf import get_logger
from .prompts import SYSTEM_PROMPT, build_user_prompt

log = get_logger(__name__)


class AIExtraction(BaseModel):
    """Validated shape of the model's JSON output."""

    summary: Optional[str] = None
    study_type: Optional[str] = None
    sample_size: Optional[int] = None
    key_findings: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    engine: Optional[str] = None  # filled in by the extractor, not the model

    @field_validator("sample_size", mode="before")
    @classmethod
    def _coerce_int(cls, v):
        if v in (None, "", "null"):
            return None
        if isinstance(v, int):
            return v
        m = re.search(r"\d[\d,]*", str(v))
        return int(m.group().replace(",", "")) if m else None

    @field_validator("key_findings", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x).strip() for x in v if str(x).strip()]


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (tolerates fences)."""
    text = text.strip()
    # Remove ```json ... ``` fences if present.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    # Grab the outermost {...}.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


class AIExtractor:
    """Picks a provider based on config + availability and runs extraction."""

    def __init__(self) -> None:
        self.provider_order = self._resolve_order()

    def _resolve_order(self) -> list[str]:
        choice = settings.ai_provider
        if choice == "none":
            return []
        if choice in ("ollama", "openai", "anthropic"):
            return [choice]
        # auto: prefer local, then paid APIs that have keys configured.
        order: list[str] = []
        if self._ollama_up():
            order.append("ollama")
        if settings.openai_api_key:
            order.append("openai")
        if settings.anthropic_api_key:
            order.append("anthropic")
        if not order:
            log.warning(
                "No AI provider available (Ollama down, no API keys). "
                "Records will use parser-only fields."
            )
        return order

    # ---- Public API ----------------------------------------------------

    def extract(
        self,
        title: Optional[str],
        existing_abstract: Optional[str],
        keywords: list[str],
        body_text: str,
    ) -> AIExtraction:
        prompt = build_user_prompt(title, existing_abstract, keywords, body_text)

        for provider in self.provider_order:
            try:
                raw = self._call(provider, prompt)
                data = _extract_json(raw)
                result = AIExtraction(**data)  # validates here
                result.engine = provider
                log.debug("AI extraction via %s succeeded", provider)
                return result
            except (ValidationError, ValueError, json.JSONDecodeError) as e:
                log.warning("%s returned invalid JSON: %s", provider, e)
            except Exception as e:
                log.warning("%s extraction call failed: %s", provider, e)

        # Everything failed or AI disabled — return empty (non-fatal).
        return AIExtraction(engine="parser")

    # ---- Provider implementations -------------------------------------

    def _call(self, provider: str, prompt: str) -> str:
        if provider == "ollama":
            return self._call_ollama(prompt)
        if provider == "openai":
            return self._call_openai(prompt)
        if provider == "anthropic":
            return self._call_anthropic(prompt)
        raise ValueError(f"Unknown provider: {provider}")

    def _ollama_up(self) -> bool:
        try:
            r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
            return r.ok
        except requests.RequestException:
            return False

    def _call_ollama(self, prompt: str) -> str:
        resp = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "format": "json",  # ask Ollama to constrain output to JSON
                "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=settings.http_timeout * 4,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or "{}"

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate text blocks from the response.
        return "".join(
            block.text for block in resp.content if block.type == "text"
        )
