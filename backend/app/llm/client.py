"""Provider-agnostic LLM interface (tech-stack.md: Gemini behind an interface).

The rest of the app depends only on `LLMClient`; swapping providers means adding one
adapter. Clients return raw text: parsing and validation belong to the caller's gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class LLMError(Exception):
    """Transport/provider failure (timeout, quota, 5xx, blocked response).

    Counted as a failed attempt by the planner (Spec 03 FR-PL-16). The message must
    never contain prompt or response content.
    """


class LLMClient(Protocol):
    model: str

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        """Return the model's JSON answer as text; raise LLMError on transport failure."""
        ...
