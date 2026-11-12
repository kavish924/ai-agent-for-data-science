"""Provider-agnostic LLM interface (tech-stack.md: Gemini behind an interface).

The rest of the app depends only on `LLMClient`; swapping providers means adding one
adapter. Clients return raw text: parsing and validation belong to the caller's gate.
"""

from __future__ import annotations

import time
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
    never contain prompt or response content. `status` is the provider's HTTP status
    when there is one.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


_sleep = time.sleep  # replaced in tests


def transport_error_class(exc: LLMError) -> str:
    """What `llm_calls.error` records for a transport failure (Spec 03 FR-PL-18)."""
    return f"transport:{exc.status}" if exc.status else f"transport:{type(exc).__name__}"


def backoff(attempt: int) -> None:
    """Wait before retrying after transport failure `attempt` (2 s, 4 s, ... by default)."""
    from ..config import settings

    _sleep(settings.llm_retry_backoff_s * 2 ** (attempt - 1))


class LLMClient(Protocol):
    model: str

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        """Return the model's JSON answer as text; raise LLMError on transport failure."""
        ...
