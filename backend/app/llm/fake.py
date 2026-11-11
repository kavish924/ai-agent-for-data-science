"""Offline LLM clients for tests and the smoke script. Never used in production paths.

* `ScriptedLLM` replays fixed responses and records every prompt it receives.
* `RuleBasedLLM` answers planner prompts with a deterministic plan derived from the
  `llm_profile()` JSON embedded in the prompt, so the full pipeline can run offline.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from .client import LLMResponse
from .prompts import PROFILE_MARKER


class ScriptedLLM:
    model = "scripted-fake"

    def __init__(
        self,
        responses: Iterable[str | dict[str, Any] | Exception],
        *,
        prompt_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self._responses = list(responses)
        self._tokens = (prompt_tokens, output_tokens)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        self.systems.append(system)
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("unexpected LLM call: no scripted response left")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        text = item if isinstance(item, str) else json.dumps(item)
        return LLMResponse(text=text, model=self.model, prompt_tokens=self._tokens[0],
                           output_tokens=self._tokens[1])


class RuleBasedLLM:
    """Deterministic stand-in for the planner LLM (offline demos and smoke runs)."""

    model = "rule-based-fake"

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        match = re.search(re.escape(PROFILE_MARKER) + r"\s*(\{.*\})\s*$", prompt, re.DOTALL)
        profile = json.loads(match.group(1)) if match else {"columns": []}
        target = profile.get("target")
        steps: list[dict[str, Any]] = []
        if profile.get("duplicate_rows"):
            steps.append({"op": "drop_duplicates", "column": None, "params": {},
                          "rationale": f"{profile['duplicate_rows']} duplicate rows found."})
        heavy = [c["name"] for c in profile["columns"]
                 if c.get("null_pct", 0) > 60 and c["name"] != target]
        if heavy:
            steps.append({"op": "drop_column", "column": None, "params": {"columns": heavy},
                          "rationale": "More than 60% of values are missing."})
        for col in profile["columns"]:
            name, kind, pct = col["name"], col["type"], col.get("null_pct", 0)
            if name == target or name in heavy or not col.get("nulls"):
                continue
            if kind == "numeric":
                steps.append({"op": "impute", "column": name, "params": {"strategy": "median"},
                              "rationale": f"{pct}% missing; the median is robust to outliers."})
            elif kind in ("categorical", "boolean"):
                steps.append({"op": "impute", "column": name, "params": {"strategy": "mode"},
                              "rationale": f"{pct}% missing; fill with the most frequent value."})
        return LLMResponse(text=json.dumps({"schema": "v1", "steps": steps}), model=self.model)
