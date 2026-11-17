"""Abstraction LLM.

Principe d'architecture : les LLM ne calculent rien et n'inventent aucun chiffre.
Ils traduisent (document → JSON, langage naturel → patch, résultats → texte).
Toute sortie structurée est contrainte par un schéma JSON (format Ollama) puis
revalidée par Pydantic.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..settings import Settings, get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    model: str

    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T: ...

    def text(self, prompt: str, system: str | None = None) -> str: ...


class OllamaClient:
    """Client minimal pour l'API /api/chat d'Ollama (sorties structurées via ``format``)."""

    def __init__(
        self,
        model: str,
        settings: Settings | None = None,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
    ):
        self.settings = settings or get_settings()
        self.model = model
        self.max_retries = max_retries
        self._http = http_client or httpx.Client(
            base_url=self.settings.ollama_url, timeout=self.settings.ollama_timeout
        )

    def _chat(self, messages: list[dict], fmt: dict | None = None, temperature: float = 0.0) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.settings.ollama_think,
            "options": {"temperature": temperature},
        }
        if fmt is not None:
            payload["format"] = fmt
        try:
            r = self._http.post("/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(
                f"Ollama injoignable ou erreur ({e}). Vérifiez `ollama serve` et `ollama pull {self.model}`."
            ) from e
        return r.json()["message"]["content"]

    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            content = self._chat(messages, fmt=schema.model_json_schema())
            try:
                return schema.model_validate_json(content)
            except ValidationError as e:
                last_err = e
                log.warning("Sortie LLM invalide (tentative %d) : %s", attempt + 1, e)
                messages += [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"Ta réponse ne respecte pas le schéma : {e}. Corrige-la."},
                ]
        raise LLMError(f"Sortie structurée invalide après {self.max_retries + 1} tentatives : {last_err}")

    def text(self, prompt: str, system: str | None = None) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        return self._chat(messages, temperature=0.2)


class FakeLLM:
    """LLM de test/hors-ligne : renvoie des réponses programmées."""

    model = "fake"

    def __init__(
        self,
        structured_handler: Callable[[str, type[BaseModel]], BaseModel | dict] | None = None,
        text_handler: Callable[[str], str] | None = None,
    ):
        self.structured_handler = structured_handler
        self.text_handler = text_handler
        self.calls: list[str] = []

    def structured(self, prompt: str, schema: type[T], system: str | None = None) -> T:
        self.calls.append(prompt)
        if self.structured_handler is None:
            return schema()
        out = self.structured_handler(prompt, schema)
        if isinstance(out, BaseModel):
            return schema.model_validate(out.model_dump())
        if isinstance(out, str):
            return schema.model_validate(json.loads(out))
        return schema.model_validate(out)

    def text(self, prompt: str, system: str | None = None) -> str:
        self.calls.append(prompt)
        return self.text_handler(prompt) if self.text_handler else ""


def get_llm(role: str = "extraction", settings: Settings | None = None) -> LLMClient | None:
    """Renvoie le client adapté au rôle (extraction | report | configurator), ou None si désactivé."""
    s = settings or get_settings()
    if not s.llm_enabled:
        return None
    model = {"extraction": s.model_extraction, "report": s.model_report, "configurator": s.model_configurator}[role]
    return OllamaClient(model=model, settings=s)
