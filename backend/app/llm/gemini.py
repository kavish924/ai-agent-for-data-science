"""Google Gemini adapter (`google-genai` SDK) for the LLMClient protocol."""

from __future__ import annotations

from google import genai
from google.genai import errors, types

from .client import LLMError, LLMResponse


class GeminiClient:
    """JSON-mode Gemini calls at temperature 0 with a pinned seed (Spec 03 FR-PL-10).

    No `response_schema` is passed: the whitelist is described in the prompt and enforced
    by Pydantic + the Gate (see Spec 03 Interfaces).
    """

    def __init__(self, *, api_key: str, model: str, seed: int, timeout_s: float) -> None:
        self.model = model
        self._seed = seed
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),  # milliseconds
        )

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            seed=self._seed,
            response_mime_type="application/json",
        )
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except errors.APIError as exc:  # 4xx/5xx from the API
            code = getattr(exc, "code", None)
            raise LLMError(f"gemini API error {code or '?'}",
                           status=code if isinstance(code, int) else None) from exc
        except Exception as exc:  # network, timeout, SDK errors
            raise LLMError(f"gemini call failed: {type(exc).__name__}") from exc

        text = response.text
        if not text:
            raise LLMError("gemini returned no text (blocked or empty response)")
        usage = response.usage_metadata
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )
