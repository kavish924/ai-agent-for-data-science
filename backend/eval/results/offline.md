# Eval results — offline

LLM: `rule-based-fake`

| Metric (PRD §9) | Value |
|---|---|
| Schema validity (first attempt) | 100% |
| Mean planner attempts | 1 |
| Plan quality (sensible plans) | 100% |
| Approval rate (golden reviewer) | 100% |
| Mean time to report | 8.6 s |

## Datasets

| Dataset | Status | Plan | Sensible | Recall | Approved | Attempts | Best model | Score (dummy) | Summary | Time |
|---|---|---|---|---|---|---|---|---|---|---|
| titanic.csv | ok | drop_column(Cabin), impute(Age), impute(Embarked) | yes | 1.0 | 3/3 | 1 | random_forest | f1_macro 0.801 (0.381) | template | 4.6 s |
| housing.csv | ok | impute(total_bedrooms) | yes | 1.0 | 1/1 | 1 | random_forest | rmse 49281.127 (115617.185) | template | 11.1 s |
| telco_churn.csv | ok | — | yes | 1.0 | 0/0 | 1 | logistic_regression | f1_macro 0.731 (0.424) | template | 10.0 s |

## Stage times (ms)

| Dataset | Upload+profile | Plan | Execute (+charts) | Models | Report |
|---|---|---|---|---|---|
| titanic.csv | 179 | 31 | 1429 | 2735 | 147 |
| housing.csv | 505 | 20 | 1749 | 8641 | 157 |
| telco_churn.csv | 874 | 24 | 1775 | 7115 | 148 |

## Reproducibility (NFR-11: executed plan replayed in a fresh session)

| Dataset | Cleaned CSV | Charts | Model scores | Report re-render | Report across sessions |
|---|---|---|---|---|---|
| titanic.csv | yes | yes (9) | yes | yes | yes |
| housing.csv | yes | yes (11) | yes | yes | yes |
| telco_churn.csv | yes | yes (12) | yes | yes | yes |

## Performance baseline (NFR-12)

100,000 rows × 21 columns (13.14 MB): upload+profile 11259 ms, execute (+re-profile, charts) 19642 ms; budget 60 s each — within budget.

Environment: Python 3.11.6 on Windows 10
