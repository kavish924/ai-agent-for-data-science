"""LLM record/replay cache for the eval (Spec 10 NFR-13).

Wraps any `LLMClient`. Answers are stored on disk keyed by the SHA-256 of model, system
prompt, prompt and a run tag, so reruns, metric fixes and ablations cost no API calls on
a rate-limited key. Cache files hold the key, model, response text and token counts only:
never the prompt. Transport errors are not cached.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.llm.client import LLMClient, LLMError, LLMResponse

_now = time.monotonic  # replaced in tests
_sleep = time.sleep


def cache_key(model: str, system: str, prompt: str, run_tag: str) -> str:
    payload = json.dumps([model, system, prompt, run_tag], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingLLM:
    def __init__(self, inner: LLMClient, cache_dir: Path | str, *, run_tag: str = "",
                 replay_only: bool = False, min_interval_s: float = 0.0) -> None:
        self.inner = inner
        self.model = inner.model
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_tag = run_tag
        self.replay_only = replay_only
        self.min_interval_s = min_interval_s
        self.hits = 0
        self.misses = 0
        self._last_call: float | None = None

    def generate_json(self, *, system: str, prompt: str) -> LLMResponse:
        key = cache_key(self.model, system, prompt, self.run_tag)
        path = self.dir / f"{key}.json"
        if path.exists():
            self.hits += 1
            d = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(text=d["text"], model=d["model"], prompt_tokens=d["prompt_tokens"],
                               output_tokens=d["output_tokens"])
        self.misses += 1
        if self.replay_only:
            raise LLMError("cache:miss")
        self._pace()
        resp = self.inner.generate_json(system=system, prompt=prompt)  # LLMError propagates, uncached
        record = {"key": key, "model": resp.model, "text": resp.text,
                  "prompt_tokens": resp.prompt_tokens, "output_tokens": resp.output_tokens}
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return resp

    def _pace(self) -> None:
        if self._last_call is not None and self.min_interval_s > 0:
            wait = self.min_interval_s - (_now() - self._last_call)
            if wait > 0:
                _sleep(wait)
        self._last_call = _now()

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}
