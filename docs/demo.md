# Demo script (about 8 minutes)

A walkthrough on `samples/titanic.csv` that shows the core promise: **the AI plans, you approve, and code does the work.**

## Before you start

- Start `backend` (Gemini, needs `GEMINI_API_KEY` in `.env`) or `backend-offline` (no key;
  a deterministic rule-based planner), plus `frontend`. Both are in `.claude/launch.json`, or use the
  commands in the README.
- Open http://localhost:3000. Have `backend/eval/results/offline.md` open in another tab.
- If the Gemini quota is low (HTTP 429), use `backend-offline`. The flow is identical, and the summary
  comes from the template.

## 1. Upload (30 s)

- Click the **titanic.csv** sample, or drag the file in.
- Point out the limits (25 MB, 100k rows) and that the original upload is stored read-only.

## 2. Profile and target (1 min)

- The snapshot shows 891 rows and 12 columns, with Age about 20% missing, Cabin about 77% missing and Embarked 2 missing.
- `PassengerId` and `Name` are typed as **identifiers** and excluded from targets.
- Accept the suggested target **Survived**. Explain that it is now protected: no step may impute, clip or drop it.
- Read the privacy notice: only aggregate statistics go to the LLM, never rows, names or IDs.

## 3. Plan review (2 min)

- Generate the plan. Typical steps: drop `Cabin`, impute `Age` (median), impute `Embarked` (mode).
- Each step has a rationale. Drop steps are flagged as destructive.
- **Edit** a parameter (for example Age median → mean) and **skip** one step to show you're in control.
  An invalid edit (a column that was already dropped) is rejected inline by the Gate.
- Open **Plan history**: the generated and approved versions are both kept.

## 4. Run (1 min)

- Approve and run, and watch the progress.
- The **Overview** tab shows rows, columns and missing cells before and after, plus the step log.
- Download the **cleaned CSV**.

## 5. Charts (1 min)

- The **Charts** tab shows the missing-value map, correlation heatmap and distributions. Age's
  distribution carries a "before" outline, because the plan changed it.
- Enlarge a chart; Escape closes it.

## 6. Models (1 min)

- **Train** in the Models tab. Random forest scores about 0.80 macro F1 against a dummy floor of about 0.38.
- Leakage-safe: imputation and clipping are fitted inside each CV fold, not on all the data.

## 7. Report (1 min)

- The **Report** tab shows the report embedded in the page: snapshot, every step and why, before/after, charts,
  models and a written summary.
- The summary can only cite numbers through placeholders filled from the artifacts, so it cannot invent a figure.
- **Download all (.zip)** gives the report, cleaned CSV, charts, plan and logs. Re-rendering is byte-identical.

## 8. Evaluation (30 s)

- Show `offline.md`:
  - all three samples produce sensible plans;
  - every reproducibility check is identical;
  - the 100k-row fixture runs within budget.
- Mention the live finding: transient Gemini errors used up the planner's retries, which led to the
  backoff fix (Spec 03 FR-PL-18).

## Likely questions

- **Can the AI run code?** No. It can only pick from 7 whitelisted operations, and each step is
  validated by Pydantic plus the Gate before anyone sees it.
- **What if the AI is down?** The error is shown, the session stays where it was, and you can retry. Transport failures back off
  2 s then 4 s. The report falls back to the template summary.
- **Is it reproducible?** Same CSV and approved plan give the same bytes: cleaned CSV, charts, scores and report.
