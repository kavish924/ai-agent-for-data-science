"""Narrator numbers-only gate (Spec 08 FR-RP-03/04/11) - scripted LLM, never the network."""

from __future__ import annotations

import pytest

from app.db import session_store
from app.llm.client import LLMError
from app.llm.fake import ScriptedLLM
from app.services.narrator import SECTIONS, build_prompt, narrate, render

FACTS = {
    "rows_before": 891,
    "rows_after": 891,
    "null_cells_before": 866,
    "null_cells_after": 0,
    "best_model": "Random forest",
    "best_score": 0.801478,
    "primary_metric": "F1 (macro)",
}
KNOWN = {"Age", "Embarked", "Cabin", "x01", "Random forest", "F1 (macro)"}

GOOD = {
    "overview": "The dataset has {{rows_after}} rows after cleaning.",
    "cleaning": "Missing cells fell from {{null_cells_before}} to {{null_cells_after}}; Cabin was dropped.",
    "modeling": "{{best_model}} scored {{best_score}} on {{primary_metric}}.",
    "next_steps": "Try tuning the model and engineering features from x01.",
}


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "app.db"
    session_store.init_db(path)
    session_store.create_session(path, session_id="sid", original_filename="t.csv", state="modeled")
    return path


def _narrate(db, llm, retries=2):
    return narrate(llm, FACTS, KNOWN, max_retries=retries, db_path=db, session_id="sid")


def test_rp_fr11_valid_answer_is_used(db):
    narration = _narrate(db, ScriptedLLM([GOOD]))
    assert narration.source == "llm"
    assert set(narration.sections) == set(SECTIONS)
    assert narration.sections["cleaning"].startswith("Missing cells fell from {{null_cells_before}}")


def test_rp_ac8_digit_in_answer_is_rejected_and_reprompted(db):
    bad = {**GOOD, "overview": "The dataset has 891 rows."}
    llm = ScriptedLLM([bad, GOOD])
    narration = _narrate(db, llm)
    assert narration.source == "llm"
    assert "overview" in llm.prompts[1] and "digit" in llm.prompts[1]
    calls = session_store.list_llm_calls(db, "sid")
    assert [(c["stage"], c["valid"], c["error"]) for c in calls] == [
        ("narrator", 0, "numbers_in_text"), ("narrator", 1, None)]


def test_rp_ac8_template_after_exhausting_retries(db):
    bad = {**GOOD, "modeling": "It reached 80% accuracy."}
    narration = _narrate(db, ScriptedLLM([bad, bad]), retries=2)
    assert narration.source == "template"
    assert all(narration.sections[s].strip() for s in SECTIONS)
    assert len(session_store.list_llm_calls(db, "sid")) == 2


def test_rp_ac4_transport_failure_falls_back_to_template(db):
    narration = _narrate(db, ScriptedLLM([LLMError("down"), LLMError("down")]))
    assert narration.source == "template"


def test_rp_fr11_no_llm_configured_uses_template(db):
    narration = _narrate(db, None)
    assert narration.source == "template"
    assert session_store.list_llm_calls(db, "sid") == []


def test_rp_fr11_unknown_placeholder_rejected(db):
    bad = {**GOOD, "overview": "Rows: {{row_count_made_up}}."}
    llm = ScriptedLLM([bad, GOOD])
    _narrate(db, llm)
    assert "row_count_made_up" in llm.prompts[1]


def test_rp_fr11_known_names_with_digits_are_allowed(db):
    narration = _narrate(db, ScriptedLLM([GOOD]))  # "x01" and "F1 (macro)" contain digits
    assert narration.source == "llm"


def test_rp_fr11_missing_section_rejected(db):
    bad = {k: v for k, v in GOOD.items() if k != "next_steps"}
    llm = ScriptedLLM([bad, GOOD])
    assert _narrate(db, llm).source == "llm"
    assert "next_steps" in llm.prompts[1]


def test_rp_ac3_render_fills_numbers_from_facts():
    text = render(GOOD["cleaning"], FACTS)
    assert text == "Missing cells fell from 866 to 0; Cabin was dropped."
    assert render("{{best_score}}", FACTS) == "0.801"
    assert render("{{rows_after}} rows", {"rows_after": 20640}) == "20,640 rows"


def test_rp_fr11_prompt_carries_facts_not_data():
    prompt = build_prompt(FACTS, KNOWN)
    assert '"null_cells_before": 866' in prompt
    assert "{{" in prompt  # explains the placeholder syntax
