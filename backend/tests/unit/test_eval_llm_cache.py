"""Spec 10 NFR-13: LLM record/replay cache for the eval."""

from __future__ import annotations

import json

import pytest

from app.llm.client import LLMError
from app.llm.fake import ScriptedLLM
from eval import llm_cache
from eval.llm_cache import CachingLLM

SECRET_PROMPT = "profile: column Age has 177 missing values"


def test_nfr_ac11_hit_does_not_call_provider(tmp_path):
    inner = ScriptedLLM([{"steps": []}])
    llm = CachingLLM(inner, tmp_path)
    first = llm.generate_json(system="sys", prompt=SECRET_PROMPT)
    second = llm.generate_json(system="sys", prompt=SECRET_PROMPT)
    assert first.text == second.text == '{"steps": []}'
    assert len(inner.prompts) == 1
    assert (llm.hits, llm.misses) == (1, 1)
    assert llm.model == inner.model
    # a fresh wrapper over the same dir replays from disk
    again = CachingLLM(ScriptedLLM([]), tmp_path)
    assert again.generate_json(system="sys", prompt=SECRET_PROMPT).text == first.text


def test_nfr_ac11_run_tag_and_prompt_change_the_key(tmp_path):
    inner = ScriptedLLM(["a", "b", "c"])
    CachingLLM(inner, tmp_path, run_tag="r1").generate_json(system="s", prompt="p")
    CachingLLM(inner, tmp_path, run_tag="r2").generate_json(system="s", prompt="p")
    CachingLLM(inner, tmp_path, run_tag="r1").generate_json(system="s", prompt="q")
    assert len(inner.prompts) == 3


def test_nfr_ac11_transport_errors_are_not_cached(tmp_path):
    inner = ScriptedLLM([LLMError("quota", status=429), "ok"])
    llm = CachingLLM(inner, tmp_path)
    with pytest.raises(LLMError):
        llm.generate_json(system="s", prompt="p")
    assert llm.generate_json(system="s", prompt="p").text == "ok"
    assert len(inner.prompts) == 2


def test_nfr_ac11_replay_only_miss_raises_without_calling(tmp_path):
    inner = ScriptedLLM(["never"])
    llm = CachingLLM(inner, tmp_path, replay_only=True)
    with pytest.raises(LLMError, match="cache:miss"):
        llm.generate_json(system="s", prompt="p")
    assert inner.prompts == []


def test_nfr_ac11_cache_file_holds_no_prompt(tmp_path):
    CachingLLM(ScriptedLLM(["{}"]), tmp_path).generate_json(system="sys", prompt=SECRET_PROMPT)
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    raw = files[0].read_text(encoding="utf-8")
    assert "177" not in raw and "Age" not in raw
    assert set(json.loads(raw)) == {"key", "model", "text", "prompt_tokens", "output_tokens"}


def test_nfr_ac11_min_interval_between_provider_calls_only(tmp_path, monkeypatch):
    now = [100.0]
    slept: list[float] = []
    monkeypatch.setattr(llm_cache, "_now", lambda: now[0])
    monkeypatch.setattr(llm_cache, "_sleep", lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    llm = CachingLLM(ScriptedLLM(["a", "b"]), tmp_path, min_interval_s=5.0)
    llm.generate_json(system="s", prompt="p1")   # first call: no wait
    now[0] += 1.0
    llm.generate_json(system="s", prompt="p1")   # hit: no wait
    llm.generate_json(system="s", prompt="p2")   # provider call 1 s later: waits 4 s
    assert slept == [pytest.approx(4.0)]
