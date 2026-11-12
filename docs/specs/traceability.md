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
| 03 | AC-12 | `test_pl_ac12_offline_provider_plans_without_a_key` | `routers/plans.py`, `llm/fake.py` |
| 03 | AC-13 | `test_pl_ac13_transport_errors_back_off_then_succeed`, `test_pl_ac13_gate_rejection_is_reprompted_without_waiting`, `test_pl_ac13_no_wait_after_the_last_attempt` | `services/planner.py`, `llm/client.py` (`backoff`), `llm/gemini.py` |
| 03 | AC-7 | `test_pl_ac7_column_dropped_earlier_is_rejected`, `test_pl_ac7_cast_changes_type_for_later_steps` | `services/gate.py` |
| 03 | AC-8 | `test_pl_ac8_target_cannot_be_imputed`, `test_pl_ac8_target_cannot_be_dropped`, `test_pl_ac8_plan_cannot_touch_target` | `services/gate.py` |
| 04 | AC-1 | `test_rv_ac1_renders_every_step_in_order` | `frontend: PlanReview.tsx` |
| 04 | AC-2 | `test_rv_ac2_skipped_step_is_submitted_as_disabled` | `frontend: PlanReview.tsx`, `lib/plan.ts` |
| 04 | AC-3 | `test_rv_ac3_constant_without_value_blocks_approval` | `frontend: ParamEditor.tsx`, `lib/plan.ts` |
| 04 | AC-4 | `test_rv_ac4_edited_step_is_labelled_and_submitted`, `test_rv_fr09_param_change_becomes_edited` | `frontend: PlanReview.tsx`; `services/plan_review.py` |
| 04 | AC-5 | `test_rv_ac5_approve_disabled_until_every_step_decided`, `test_ap_ac6_execute_before_approve_is_409` | `frontend: PlanReview.tsx`; `routers/execution.py` |
| 04 | AC-6 | `test_rv_ac6_regenerate_shows_the_new_version`, `test_ap_ac8_history_keeps_every_version` | `frontend: PlanReview.tsx`; `routers/plans.py` (history view: M7) |
| 04 | AC-7 | `test_rv_ac7_destructive_steps_name_what_is_lost` | `frontend: lib/plan.ts` |
| 04 | AC-8 | `test_rv_ac8_server_issues_shown_on_their_step` | `frontend: PlanReview.tsx` |
| 04 | AC-9 | `test_rv_ac9_upload_error_shows_server_message` | `frontend: UploadScreen.tsx` |
| 04 | AC-10 | `test_rv_ac10_id_like_columns_not_offered_as_target` | `frontend: ProfileScreen.tsx` |
| 04 | AC-11 | `test_rv_ac11_tabs_follow_the_aria_pattern`, `test_rv_ac11_active_tab_lives_in_the_url` | `frontend: ResultsTabs.tsx`, `AgentFlow.tsx` |
| 04 | AC-12 | `test_rv_ac12_report_tab_embeds_a_sandboxed_report` | `frontend: ReportView.tsx` |
| 04 | AC-13 | `test_rv_ac13_plan_history_shows_versions_read_only` | `frontend: PlanHistory.tsx` |
| 04 | AC-14 | `test_rv_ac14_missing_session_and_network_errors_offer_a_next_step` | `frontend: ErrorState.tsx`, `AgentFlow.tsx` |
| 04 | AC-15 | `test_rv_ac15_focus_moves_to_the_new_heading_and_is_announced`, `test_rv_ac15_skip_link_targets_main`, `test_rv_ac15_stepper_reads_finished_steps` | `frontend: useScreenFocus.ts`, `Shell.tsx` |
| 04 | AC-16 | `test_rv_ac16_no_framer_motion_imports` | `frontend: package.json` |
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
| 06 | AC-1 | `test_ch_ac1_titanic_standard_charts` | `services/charts.py` |
| 06 | AC-2 | `test_ch_ac2_cap_enforced_and_skips_recorded` | `services/charts.py` |
| 06 | AC-3 | `test_ch_ac3_no_nulls_means_no_missing_map`, `test_ch_fr05_missing_map_when_nulls_remain` | `services/charts.py` |
| 06 | AC-4 | `test_ch_ac4_png_bytes_are_deterministic` | `services/charts.py` |
| 06 | AC-5 | `test_ch_ac5_text_only_dataset_does_not_crash` | `services/charts.py` |
| 06 | AC-6 | `test_ch_ac6_chart_failure_never_fails_the_run`, `test_ch_ac6_failed_charts_explained_without_breaking` | `services/orchestrator.py`; `frontend: ChartGallery.tsx` |
| 06 | AC-7 | `test_ch_ac7_after_profile_reflects_cleaning` | `services/orchestrator.py` |
| 06 | AC-8 | `test_ch_ac8_before_overlay_only_on_changed_columns`, `test_ch_ac8_imputed_column_has_before_overlay` | `services/charts.py`, `services/orchestrator.py` |
| 06 | AC-9 | `test_ch_ac9_chart_files_are_whitelisted` | `routers/execution.py` |
| 06 | AC-10 | `test_ch_ac10_gallery_shows_each_chart_and_skips`, `test_ch_fr13_chart_opens_large_and_closes_with_escape` | `frontend: ChartGallery.tsx` |
| 07 | AC-1 | `test_ml_ac1_titanic_is_classification_with_three_baselines` | `services/analyst.py` |
| 07 | AC-2 | `test_ml_ac2_continuous_target_is_regression` | `services/analyst.py` |
| 07 | AC-3 | `test_ml_ac3_identifier_target_rejected` | `services/analyst.py` |
| 07 | AC-4 | `test_ml_ac4_preprocessing_lives_inside_the_pipeline` | `services/analyst.py` (`build_pipeline`) |
| 07 | AC-5 | `test_ml_ac5_scores_are_reproducible` | `services/analyst.py` |
| 07 | AC-6 | `test_ml_ac6_feature_nulls_are_handled_in_pipeline` | `services/analyst.py` |
| 07 | AC-7 | `test_ml_ac7_statistical_steps_are_not_replayed` | `services/analyst.py`, `services/transformers.py` |
| 07 | AC-8 | `test_ml_ac8_target_suggestions_for_titanic`, `test_ml_fr01_profile_screen_offers_the_top_suggestion` | `services/analyst.py`; `frontend: ProfileScreen.tsx` |
| 07 | AC-9 | `test_ml_ac9_training_flow`, `test_ml_ac9_invalid_targets_rejected`, `test_ml_ac9_training_failure_returns_to_executed` | `routers/models.py` |
| 07 | AC-10 | `test_ml_ac10_best_model_is_never_the_dummy` | `services/analyst.py` |
| 07 | AC-11 | `test_ml_ac11_results_table_marks_the_best_model`, `test_ml_ac11_train_sends_the_chosen_target` | `frontend: ModelPanel.tsx` |
| 07 | AC-12 | `test_ml_ac12_targets_changed_by_the_plan_are_flagged`, `test_ml_ac12_model_panel_hides_targets_changed_by_the_plan` | `routers/models.py`; `frontend: ModelPanel.tsx` |
| 08 | AC-1 | `test_rp_ac1_seven_sections_in_order` | `services/reporter.py`, `templates/report.html.j2` |
| 08 | AC-2 | `test_rp_ac2_step_shows_rationale_status_and_logged_counts` | `services/reporter.py` |
| 08 | AC-3 | `test_rp_ac3_numbers_come_from_artifacts`, `test_rp_ac3_render_fills_numbers_from_facts` | `services/reporter.py`, `services/narrator.py` |
| 08 | AC-4 | `test_rp_ac4_narration_failure_uses_template`, `test_rp_ac4_transport_failure_falls_back_to_template` | `services/narrator.py` |
| 08 | AC-5 | `test_rp_ac5_report_404_until_created` | `routers/reports.py` |
| 08 | AC-6 | `test_rp_ac6_bundle_holds_every_deliverable` | `services/reporter.py` (`build_bundle`) |
| 08 | AC-7 | `test_rp_ac7_all_steps_disabled_renders_no_changes` | `templates/report.html.j2` |
| 08 | AC-8 | `test_rp_ac8_digit_in_answer_is_rejected_and_reprompted`, `test_rp_ac8_template_after_exhausting_retries` | `services/narrator.py` |
| 08 | AC-9 | `test_rp_ac9_rerender_is_byte_identical_and_offline` | `services/reporter.py` |
| 08 | AC-10 | `test_rp_ac10_no_model_run_says_training_skipped` | `templates/report.html.j2` |
| 08 | AC-11 | `test_rp_ac11_create_report_before_one_exists`, `test_rp_ac11_links_and_summary_source_once_reported` | `frontend: ReportPanel.tsx` |
| 08 | AC-12 | `test_rp_ac12_transport_error_backs_off_then_uses_llm` | `services/narrator.py` |
| 09 | AC-1 | `test_file_too_large_413`, `test_get_plan_before_created_409`, `test_ap_ac6_execute_before_approve_is_409`, `test_ap_ac9_cleaned_csv_download` | `routers/sessions.py` |
| 09 | AC-2 | `test_unknown_session_404_with_envelope`, `test_missing_file_422` | `errors.py` |
| 09 | AC-3 | `test_ap_ac3_review_edits_are_regated` | `routers/sessions.py` |
| 09 | AC-4 | `test_full_flow_plan_review_approve_execute` | `routers/sessions.py` |
| 09 | AC-5 | `test_ap_ac5_openapi_matches_spec` | `routers/sessions.py` |
| 09 | AC-6 | `test_ap_ac6_execute_before_approve_is_409`, `test_ap_ac6_approve_with_proposed_steps_is_422`, `test_ap_ac6_execute_runs_the_frozen_approved_plan` | `routers/sessions.py` |
| 09 | AC-7 | `test_ap_ac7_second_execute_is_rejected` | `db/session_store.py` (`transition`) |
| 09 | AC-8 | `test_ap_ac8_history_keeps_every_version` | `storage/artifacts.py` |
| 09 | AC-9 | `test_ap_ac9_cleaned_csv_download` | `routers/sessions.py` |
| 09 | AC-10 | `test_ap_ac10_execution_log_endpoint` | `routers/execution.py` |
| 09 | AC-11 | `test_ap_ac11_chart_endpoints` | `routers/execution.py` |
| 09 | AC-12 | `test_ap_ac12_model_and_targets_endpoints` | `routers/models.py` |
| 09 | AC-13 | `test_ap_ac13_report_and_bundle_endpoints` | `routers/reports.py` |
| 10 | AC-1 | `test_nfr_ac1_replayed_plan_is_byte_identical` (also `test_deterministic_outputs_across_sessions`, `test_ch_ac4_png_bytes_are_deterministic`, `test_ml_ac5_scores_are_reproducible`) | `eval/harness.py` |
| 10 | AC-2 | `test_nfr_ac2_no_data_or_prompt_in_logs` | `services/planner.py`, `logging_setup.py` |
| 10 | AC-3 | `test_nfr_ac3_retention_sweep_deletes_expired_sessions` | `services/retention.py` |
| 10 | AC-4 | `test_nfr_ac4_one_completion_line_per_stage` | `routers/plans.py`, `services/reporter.py` |
| 10 | AC-5 | `test_nfr_ac5_llm_failure_is_visible_and_recoverable` | `routers/plans.py` |
| 10 | AC-6 | `test_nfr_ac6_performance_baseline_is_recorded` | `eval/harness.py` (`perf_baseline`) |
| 10 | AC-7 | `test_nfr_ac7_inflight_sessions_recovered_on_startup` | `db/session_store.py` (`recover_inflight`) |
| 10 | AC-8 | `test_nfr_ac8_matching_by_column_drop_list_and_wildcard`, `test_nfr_ac8_sensible_plan_and_scripted_review`, `test_nfr_ac8_missing_or_forbidden_steps_are_not_sensible`, `test_nfr_ac8_empty_expectations_and_empty_plan` | `eval/metrics.py`, `eval/golden.json` |
| 10 | AC-9 | `test_nfr_ac9_summary_metrics` | `eval/metrics.py` |
| 10 | AC-10 | `test_nfr_ac10_offline_eval_runs_every_stage_and_writes_results` | `eval/harness.py`, `eval/run.py` |
