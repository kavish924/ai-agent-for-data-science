# Traceability Matrix — AC → test → module

> Enforced by `backend/scripts/check_traceability.py` (runs in CI). Every AC of a spec
> whose status is `In progress` or `Done` must have a row here. Every listed test must
> exist. `pending (Mx)` is allowed only while the spec is not `Done`.

| Spec | AC | Tests | Module |
|---|---|---|---|
| 01 | AC-1 | `test_upload_and_profile_happy_path` | `routers/sessions.py` |
| 01 | AC-2 | `test_parse_upload_semicolon_latin1` | `services/ingestion.py` |
| 01 | AC-3 | `test_file_too_large_413` | `routers/sessions.py` |
| 01 | AC-4 | `test_too_many_rows_413` | `routers/sessions.py` |
| 01 | AC-5 | `test_non_csv_rejected_415`, `test_parse_upload_rejects_binary_junk` | `services/ingestion.py` |
| 01 | AC-6 | `test_upload_original_is_immutable`, `test_full_flow_plan_review_approve_execute` | `storage/artifacts.py` |
| 01 | AC-7 | `test_up_ac7_oversized_upload_writes_nothing` | `routers/sessions.py` |
| 01 | AC-8 | `test_up_ac8_profiling_retry` | `routers/sessions.py` |
| 02 | AC-1 | `test_pr_ac1_titanic_age_and_sex` | `services/profiler.py` |
| 02 | AC-2 | `test_id_like_near_unique_strings` | `services/profiler.py` |
| 02 | AC-3 | `test_iqr_outlier_count` | `services/profiler.py` |
| 02 | AC-4 | `test_duplicate_rows_counted` | `services/profiler.py` |
| 02 | AC-5 | `test_top_k_capping_not_full_column_dump` | `services/profiler.py` |
| 02 | AC-6 | `test_all_empty_column_flagged` | `services/profiler.py` |
| 02 | AC-7 | `test_pr_ac7_titanic_passenger_id_is_id_like`, `test_pr_fr11_id_name_hint_with_unique_integers` | `services/profiler.py` |
| 02 | AC-8 | `test_pr_ac8_comma_numbers_parsed_consistently`, `test_pr_fr10_strips_thousands_separators_and_spaces` | `services/numeric.py` |
| 02 | AC-9 | `test_pr_ac9_llm_profile_excludes_text_and_id_values` | `services/profiler.py` (`llm_profile`) |
| 03 | AC-1 | `test_pl_ac1_valid_plan_on_first_attempt`, `test_pl_ac1_generate_titanic_plan` (fake LLM; live plan quality is measured in M8) | `services/planner.py` |
| 03 | AC-2 | `test_pl_ac2_unknown_op_rejected_and_reprompted` | `services/planner.py` |
| 03 | AC-3 | `test_pl_ac3_typo_column_rejected_and_reprompted` | `services/planner.py` |
| 03 | AC-4 | `test_pl_ac4_retry_budget_is_exact` | `services/planner.py` |
| 03 | AC-5 | `test_pl_ac5_llm_calls_hold_metadata_not_content` | `db/session_store.py` (`llm_calls`) |
| 03 | AC-6 | `test_pl_ac6_same_responses_same_plan`, `test_pl_ac6_execution_never_calls_the_llm` | `services/planner.py` |
| 03 | AC-9 | `test_pl_ac9_no_api_key_is_503_and_changes_nothing` | `routers/plans.py` |
| 03 | AC-10 | `test_pl_ac10_prompt_has_no_raw_text_or_id_values`, `test_pl_ac10_retry_prompt_lists_previous_issues` | `llm/prompts.py` |
| 03 | AC-11 | `test_pl_ac11_transport_error_then_success` | `services/planner.py` |
| 03 | AC-7 | `test_pl_ac7_column_dropped_earlier_is_rejected`, `test_pl_ac7_cast_changes_type_for_later_steps` | `services/gate.py` |
| 03 | AC-8 | `test_pl_ac8_target_cannot_be_imputed`, `test_pl_ac8_target_cannot_be_dropped`, `test_pl_ac8_plan_cannot_touch_target` | `services/gate.py` |
| 04 | AC-5 | `test_ap_ac6_execute_before_approve_is_409` | `routers/sessions.py` |
| 05 | AC-1 | `test_full_flow_plan_review_approve_execute` | `services/executor.py` |
| 05 | AC-2 | `test_ap_ac6_execute_runs_the_frozen_approved_plan` | `services/executor.py` |
| 05 | AC-3 | `test_ex_fr05_failing_step_returns_to_review_and_keeps_log`, `test_cast_type_str_to_int_fails_dry_run` | `services/executor.py` |
| 05 | AC-4 | `test_full_flow_plan_review_approve_execute` | `services/executor.py` |
| 05 | AC-5 | `test_drop_column` | `services/executor.py` |
| 05 | AC-6 | `test_deterministic_outputs_across_sessions` | `services/executor.py` |
| 05 | AC-7 | `test_parse_datetime_coerces_junk` | `services/executor.py` |
| 05 | AC-8 | `test_ex_ac8_bool_cast_maps_values_not_truthiness`, `test_ex_ac8_bool_cast_rejects_unknown_values` | `services/executor.py` |
| 05 | AC-9 | `test_ex_ac9_int_cast_allows_nulls`, `test_ex_ac9_int_cast_rejects_fractions` | `services/executor.py` |
| 05 | AC-10 | `test_ex_ac10_clip_keeps_unparseable_values`, `test_ex_fr13_impute_median_ignores_unparseable_and_keeps_them` | `services/executor.py` |
| 05 | AC-11 | `test_ex_ac11_unexpected_exception_never_leaves_executing` | `services/executor.py` |
| 09 | AC-1 | `test_file_too_large_413`, `test_get_plan_before_created_409`, `test_ap_ac6_execute_before_approve_is_409`, `test_ap_ac9_cleaned_csv_download` | `routers/sessions.py` |
| 09 | AC-2 | `test_unknown_session_404_with_envelope`, `test_missing_file_422` | `errors.py` |
| 09 | AC-3 | `test_ap_ac3_review_edits_are_regated` | `routers/sessions.py` |
| 09 | AC-4 | `test_full_flow_plan_review_approve_execute` | `routers/sessions.py` |
| 09 | AC-5 | `test_ap_ac5_openapi_matches_spec` | `routers/sessions.py` |
| 09 | AC-6 | `test_ap_ac6_execute_before_approve_is_409`, `test_ap_ac6_approve_with_proposed_steps_is_422`, `test_ap_ac6_execute_runs_the_frozen_approved_plan` | `routers/sessions.py` |
| 09 | AC-7 | `test_ap_ac7_second_execute_is_rejected` | `db/session_store.py` (`transition`) |
| 09 | AC-8 | `test_ap_ac8_history_keeps_every_version` | `storage/artifacts.py` |
| 09 | AC-9 | `test_ap_ac9_cleaned_csv_download` | `routers/sessions.py` |
| 10 | AC-1 | pending (M5) | — |
| 10 | AC-2 | `test_nfr_ac2_no_data_or_prompt_in_logs` | `services/planner.py`, `logging_setup.py` |
| 10 | AC-3 | `test_nfr_ac3_retention_sweep_deletes_expired_sessions` | `services/retention.py` |
| 10 | AC-4 | pending (M6) | — |
| 10 | AC-5 | `test_nfr_ac5_llm_failure_is_visible_and_recoverable` | `routers/plans.py` |
| 10 | AC-6 | pending (M8) | — |
| 10 | AC-7 | `test_nfr_ac7_inflight_sessions_recovered_on_startup` | `db/session_store.py` (`recover_inflight`) |
