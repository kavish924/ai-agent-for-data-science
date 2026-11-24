# Eval results — offline

LLM: `rule-based-fake`

| Metric (PRD §9) | Value |
|---|---|
| Schema validity (first attempt) | 100% |
| Mean planner attempts | 1 |
| Planner transport errors (API, not the plan) | 0 |
| Plan quality (sensible plans) | 0% |
| Approval rate (golden reviewer) | 100% |
| Mean step F1 (NFR-14) | 0.5834 |
| Forbidden-step rate | 0% |
| Mean time to report | 9.6 s |

## Datasets

| Dataset | Status | Plan | Sensible | Recall | F1 | Approved | Attempts | Best model | Score (dummy) | Summary | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| titanic__s1.csv | ok | drop_duplicates(), drop_column(Parch,Cabin), impute(Age), impute(Fare), impute(Embarked) | **NO** | 0.5455 | 0.7059 | 5/5 | 1 | logistic_regression | f1_macro 1.000 (0.381) | template | 4.8 s |
| titanic__s2.csv | ok | drop_duplicates(), drop_column(Parch,Cabin), impute(PassengerId), impute(Age), impute(Embarked) | **NO** | 0.5455 | 0.7059 | 5/5 | 1 | logistic_regression | f1_macro 1.000 (0.381) | template | 3.6 s |
| titanic__s3.csv | ok | drop_duplicates(), drop_column(SibSp,Cabin), impute(Age), impute(Parch), impute(Embarked) | **NO** | 0.5455 | 0.7059 | 5/5 | 1 | logistic_regression | f1_macro 1.000 (0.381) | template | 4.3 s |
| housing__s1.csv | ok | drop_duplicates(), drop_column(total_rooms), impute(latitude), impute(total_bedrooms) | **NO** | 0.4444 | 0.6154 | 4/4 | 1 | linear_regression | rmse 0.000 (115617.185) | template | 11.2 s |
| housing__s2.csv | ok | drop_duplicates(), drop_column(latitude), impute(total_rooms), impute(total_bedrooms) | **NO** | 0.4444 | 0.6154 | 4/4 | 1 | linear_regression | rmse 0.000 (115617.185) | template | 10.9 s |
| housing__s3.csv | ok | drop_duplicates(), drop_column(housing_median_age), impute(latitude), impute(total_bedrooms) | **NO** | 0.4444 | 0.6154 | 4/4 | 1 | linear_regression | rmse 0.000 (115617.185) | template | 11.0 s |
| telco_churn__s1.csv | ok | drop_duplicates(), drop_column(SeniorCitizen), impute(tenure) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.424) | template | 8.0 s |
| telco_churn__s2.csv | ok | drop_duplicates(), drop_column(SeniorCitizen), impute(tenure) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.424) | template | 8.0 s |
| telco_churn__s3.csv | ok | drop_duplicates(), drop_column(Dependents), impute(SeniorCitizen) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.424) | template | 8.0 s |
| credit-g__s1.csv | ok | drop_duplicates(), drop_column(age), impute(num_dependents) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.412) | template | 4.8 s |
| credit-g__s2.csv | ok | drop_duplicates(), drop_column(duration), impute(existing_credits) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.412) | template | 4.8 s |
| credit-g__s3.csv | ok | drop_duplicates(), drop_column(residence_since), impute(duration) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.412) | template | 4.8 s |
| diabetes__s1.csv | ok | drop_duplicates(), drop_column(pres), impute(plas) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.394) | template | 3.1 s |
| diabetes__s2.csv | ok | drop_duplicates(), drop_column(pres), impute(mass) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.394) | template | 3.1 s |
| diabetes__s3.csv | ok | drop_duplicates(), drop_column(insu), impute(mass) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.394) | template | 3.1 s |
| adult__s1.csv | ok | drop_duplicates(), drop_column(capital-loss), impute(age), impute(workclass), impute(occupation), impute(native-country) | **NO** | 0.375 | 0.5455 | 6/6 | 1 | logistic_regression | f1_macro 1.000 (0.432) | template | 26.7 s |
| adult__s2.csv | ok | drop_duplicates(), drop_column(hours-per-week), impute(workclass), impute(fnlwgt), impute(occupation), impute(native-country) | **NO** | 0.375 | 0.5455 | 6/6 | 1 | logistic_regression | f1_macro 1.000 (0.432) | template | 26.3 s |
| adult__s3.csv | ok | drop_duplicates(), drop_column(hours-per-week), impute(workclass), impute(occupation), impute(capital-gain), impute(native-country) | **NO** | 0.375 | 0.5455 | 6/6 | 1 | logistic_regression | f1_macro 1.000 (0.432) | template | 25.9 s |
| bank-marketing__s1.csv | ok | drop_duplicates(), drop_column(V1), impute(V6) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.469) | template | 19.4 s |
| bank-marketing__s2.csv | ok | drop_duplicates(), drop_column(V15), impute(V12) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.469) | template | 19.4 s |
| bank-marketing__s3.csv | ok | drop_duplicates(), drop_column(V15), impute(V6) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.469) | template | 22.3 s |
| blood-transfusion__s1.csv | ok | drop_duplicates(), drop_column(V3), impute(V2) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.433) | template | 2.9 s |
| blood-transfusion__s2.csv | ok | drop_duplicates(), drop_column(V1), impute(V3) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.433) | template | 3.1 s |
| blood-transfusion__s3.csv | ok | drop_duplicates(), drop_column(V1), impute(V3) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.433) | template | 2.8 s |
| breast-w__s1.csv | ok | drop_duplicates(), drop_column(Marginal_Adhesion), impute(Cell_Shape_Uniformity), impute(Bare_Nuclei) | **NO** | 0.4286 | 0.6 | 4/4 | 1 | random_forest | f1_macro 1.000 (0.396) | template | 4.3 s |
| breast-w__s2.csv | ok | drop_duplicates(), drop_column(Mitoses), impute(Cell_Size_Uniformity), impute(Bare_Nuclei) | **NO** | 0.4286 | 0.6 | 4/4 | 1 | random_forest | f1_macro 1.000 (0.396) | template | 3.7 s |
| breast-w__s3.csv | ok | drop_duplicates(), drop_column(Cell_Size_Uniformity), impute(Marginal_Adhesion), impute(Bare_Nuclei) | **NO** | 0.4286 | 0.6 | 4/4 | 1 | random_forest | f1_macro 1.000 (0.396) | template | 3.5 s |
| spambase__s1.csv | ok | drop_duplicates(), drop_column(char_freq_%28), impute(word_freq_free) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.377) | template | 9.7 s |
| spambase__s2.csv | ok | drop_duplicates(), drop_column(word_freq_report), impute(word_freq_our) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.377) | template | 9.1 s |
| spambase__s3.csv | ok | drop_duplicates(), drop_column(word_freq_pm), impute(word_freq_hp) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.377) | template | 9.1 s |
| phoneme__s1.csv | ok | drop_duplicates(), drop_column(V1), impute(V2) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.414) | template | 3.5 s |
| phoneme__s2.csv | ok | drop_duplicates(), drop_column(V5), impute(V1) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.414) | template | 3.5 s |
| phoneme__s3.csv | ok | drop_duplicates(), drop_column(V5), impute(V3) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.414) | template | 3.4 s |
| kc1__s1.csv | ok | drop_duplicates(), drop_column(t), impute(b) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.458) | template | 4.9 s |
| kc1__s2.csv | ok | drop_duplicates(), drop_column(total_Op), impute(lOComment) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.458) | template | 5.0 s |
| kc1__s3.csv | ok | drop_duplicates(), drop_column(e), impute(l) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.458) | template | 4.9 s |
| ilpd__s1.csv | ok | drop_duplicates(), drop_column(V6), impute(V5) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.417) | template | 3.6 s |
| ilpd__s2.csv | ok | drop_duplicates(), drop_column(V5), impute(V3) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.417) | template | 3.5 s |
| ilpd__s3.csv | ok | drop_duplicates(), drop_column(V1), impute(V10) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.417) | template | 3.5 s |
| vehicle__s1.csv | ok | drop_duplicates(), drop_column(PR.AXIS_ASPECT_RATIO), impute(COMPACTNESS) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.102) | template | 5.0 s |
| vehicle__s2.csv | ok | drop_duplicates(), drop_column(MAX.LENGTH_RECTANGULARITY), impute(KURTOSIS_ABOUT_MAJOR) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.102) | template | 5.3 s |
| vehicle__s3.csv | ok | drop_duplicates(), drop_column(CIRCULARITY), impute(PR.AXIS_RECTANGULARITY) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.102) | template | 5.2 s |
| wdbc__s1.csv | ok | drop_duplicates(), drop_column(V22), impute(V6) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 1.000 (0.385) | template | 6.6 s |
| wdbc__s2.csv | ok | drop_duplicates(), drop_column(V3), impute(V17) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 0.998 (0.385) | template | 5.9 s |
| wdbc__s3.csv | ok | drop_duplicates(), drop_column(V27), impute(V22) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | logistic_regression | f1_macro 0.998 (0.385) | template | 5.5 s |
| house-prices__s1.csv | ok | drop_duplicates(), drop_column(Alley,Fireplaces,PoolQC,Fence,MiscFeature), impute(LotFrontage), impute(MasVnrType), impute(MasVnrArea), impute(BsmtQual), impute(BsmtCond), impute(BsmtExposure), impute(BsmtFinType1), impute(BsmtFinType2), impute(Electrical), impute(LowQualFinSF), impute(FireplaceQu), impute(GarageType), impute(GarageYrBlt), impute(GarageFinish), impute(GarageQual), impute(GarageCond) | **NO** | 0.375 | 0.5455 | 18/18 | 1 | linear_regression | rmse 0.000 (77160.108) | template | 13.6 s |
| house-prices__s2.csv | ok | drop_duplicates(), drop_column(Alley,FullBath,PoolQC,Fence,MiscFeature), impute(LotFrontage), impute(MasVnrType), impute(MasVnrArea), impute(BsmtQual), impute(BsmtCond), impute(BsmtExposure), impute(BsmtFinType1), impute(BsmtFinSF1), impute(BsmtFinType2), impute(Electrical), impute(FireplaceQu), impute(GarageType), impute(GarageYrBlt), impute(GarageFinish), impute(GarageQual), impute(GarageCond) | **NO** | 0.375 | 0.5455 | 18/18 | 1 | linear_regression | rmse 0.000 (77160.108) | template | 12.9 s |
| house-prices__s3.csv | ok | drop_duplicates(), drop_column(Alley,1stFlrSF,PoolQC,Fence,MiscFeature), impute(Id), impute(LotFrontage), impute(MasVnrType), impute(MasVnrArea), impute(BsmtQual), impute(BsmtCond), impute(BsmtExposure), impute(BsmtFinType1), impute(BsmtFinType2), impute(Electrical), impute(FireplaceQu), impute(GarageType), impute(GarageYrBlt), impute(GarageFinish), impute(GarageQual), impute(GarageCond) | **NO** | 0.375 | 0.5455 | 18/18 | 1 | linear_regression | rmse 0.000 (77160.108) | template | 12.9 s |
| diamonds__s1.csv | ok | drop_duplicates(), drop_column(z), impute(x) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (4002.180) | template | 25.1 s |
| diamonds__s2.csv | ok | drop_duplicates(), drop_column(y), impute(depth) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (4002.180) | template | 25.3 s |
| diamonds__s3.csv | ok | drop_duplicates(), drop_column(table), impute(depth) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (4002.180) | template | 36.0 s |
| bike-sharing__s1.csv | ok | drop_duplicates(), drop_column(windspeed), impute(year) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (182.179) | template | 9.3 s |
| bike-sharing__s2.csv | ok | drop_duplicates(), drop_column(temp), impute(feel_temp) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (182.179) | template | 10.4 s |
| bike-sharing__s3.csv | ok | drop_duplicates(), drop_column(weekday), impute(temp) | **NO** | 0.375 | 0.5455 | 3/3 | 1 | linear_regression | rmse 0.000 (182.179) | template | 9.4 s |
| house-sales__s1.csv | ok | drop_duplicates(), drop_column(floors), impute(zipcode) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | linear_regression | rmse 0.000 (360733.786) | template | 14.4 s |
| house-sales__s2.csv | ok | drop_duplicates(), drop_column(sqft_basement), impute(sqft_above) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | linear_regression | rmse 0.000 (360733.786) | template | 14.0 s |
| house-sales__s3.csv | ok | drop_duplicates(), drop_column(zipcode), impute(waterfront) | **NO** | 0.4286 | 0.6 | 3/3 | 1 | linear_regression | rmse 0.000 (360733.786) | template | 13.5 s |

Plan issues:
- titanic__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Survived_copy'}, {'op': 'clip_outliers', 'column': 'PassengerId'}, {'op': 'standardize_text', 'column': 'Sex'}]; forbidden []
- titanic__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Survived_copy'}, {'op': 'clip_outliers', 'column': 'Fare'}, {'op': 'standardize_text', 'column': 'Sex'}]; forbidden []
- titanic__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Survived_copy'}, {'op': 'clip_outliers', 'column': 'PassengerId'}, {'op': 'standardize_text', 'column': 'Sex'}]; forbidden []
- housing__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'median_house_value_copy'}, {'op': 'clip_outliers', 'column': 'longitude'}, {'op': 'standardize_text', 'column': 'ocean_proximity'}]; forbidden []
- housing__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'median_house_value_copy'}, {'op': 'clip_outliers', 'column': 'households'}, {'op': 'standardize_text', 'column': 'ocean_proximity'}]; forbidden []
- housing__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'median_house_value_copy'}, {'op': 'clip_outliers', 'column': 'median_income'}, {'op': 'standardize_text', 'column': 'ocean_proximity'}]; forbidden []
- telco_churn__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Churn_copy'}, {'op': 'clip_outliers', 'column': 'MonthlyCharges'}, {'op': 'standardize_text', 'column': 'OnlineSecurity'}]; forbidden []
- telco_churn__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Churn_copy'}, {'op': 'clip_outliers', 'column': 'MonthlyCharges'}, {'op': 'standardize_text', 'column': 'StreamingMovies'}]; forbidden []
- telco_churn__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Churn_copy'}, {'op': 'clip_outliers', 'column': 'tenure'}, {'op': 'standardize_text', 'column': 'Partner'}]; forbidden []
- credit-g__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'credit_amount'}, {'op': 'standardize_text', 'column': 'housing'}]; forbidden []
- credit-g__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'age'}, {'op': 'standardize_text', 'column': 'personal_status'}]; forbidden []
- credit-g__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'credit_amount'}, {'op': 'standardize_text', 'column': 'purpose'}]; forbidden []
- diabetes__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'pedi'}]; forbidden []
- diabetes__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'preg'}]; forbidden []
- diabetes__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'age'}]; forbidden []
- adult__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'education-num'}, {'op': 'standardize_text', 'column': 'sex'}]; forbidden []
- adult__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'capital-loss'}, {'op': 'standardize_text', 'column': 'sex'}]; forbidden []
- adult__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'education-num'}, {'op': 'standardize_text', 'column': 'race'}]; forbidden []
- bank-marketing__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V13'}, {'op': 'standardize_text', 'column': 'V3'}]; forbidden []
- bank-marketing__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V13'}, {'op': 'standardize_text', 'column': 'V9'}]; forbidden []
- bank-marketing__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V12'}, {'op': 'standardize_text', 'column': 'V4'}]; forbidden []
- blood-transfusion__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}]; forbidden []
- blood-transfusion__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}]; forbidden []
- blood-transfusion__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}]; forbidden []
- breast-w__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'Bland_Chromatin'}]; forbidden []
- breast-w__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'Single_Epi_Cell_Size'}]; forbidden []
- breast-w__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'Single_Epi_Cell_Size'}]; forbidden []
- spambase__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'word_freq_1999'}]; forbidden []
- spambase__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'word_freq_all'}]; forbidden []
- spambase__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'class_copy'}, {'op': 'clip_outliers', 'column': 'word_freq_credit'}]; forbidden []
- phoneme__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V5'}]; forbidden []
- phoneme__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V3'}]; forbidden []
- phoneme__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}]; forbidden []
- kc1__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'defects_copy'}, {'op': 'clip_outliers', 'column': 'lOCode'}]; forbidden []
- kc1__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'defects_copy'}, {'op': 'clip_outliers', 'column': 'uniq_Op'}]; forbidden []
- kc1__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'defects_copy'}, {'op': 'clip_outliers', 'column': 'total_Opnd'}]; forbidden []
- ilpd__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V10'}, {'op': 'standardize_text', 'column': 'V2'}]; forbidden []
- ilpd__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}, {'op': 'standardize_text', 'column': 'V2'}]; forbidden []
- ilpd__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V4'}, {'op': 'standardize_text', 'column': 'V2'}]; forbidden []
- vehicle__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'MAX.LENGTH_RECTANGULARITY'}]; forbidden []
- vehicle__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'SCATTER_RATIO'}]; forbidden []
- vehicle__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'SCALED_VARIANCE_MAJOR'}]; forbidden []
- wdbc__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V16'}]; forbidden []
- wdbc__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V30'}]; forbidden []
- wdbc__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'Class_copy'}, {'op': 'clip_outliers', 'column': 'V17'}]; forbidden []
- house-prices__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'SalePrice_copy'}, {'op': 'clip_outliers', 'column': 'BsmtUnfSF'}, {'op': 'standardize_text', 'column': 'HouseStyle'}]; forbidden []
- house-prices__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'SalePrice_copy'}, {'op': 'clip_outliers', 'column': 'LowQualFinSF'}, {'op': 'standardize_text', 'column': 'MSZoning'}]; forbidden []
- house-prices__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'SalePrice_copy'}, {'op': 'clip_outliers', 'column': 'BsmtUnfSF'}, {'op': 'standardize_text', 'column': 'Condition2'}]; forbidden []
- diamonds__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'table'}, {'op': 'standardize_text', 'column': 'color'}]; forbidden []
- diamonds__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'table'}, {'op': 'standardize_text', 'column': 'color'}]; forbidden []
- diamonds__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'z'}, {'op': 'standardize_text', 'column': 'clarity'}]; forbidden []
- bike-sharing__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'count_copy'}, {'op': 'clip_outliers', 'column': 'temp'}, {'op': 'standardize_text', 'column': 'season'}]; forbidden []
- bike-sharing__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'count_copy'}, {'op': 'clip_outliers', 'column': 'windspeed'}, {'op': 'standardize_text', 'column': 'season'}]; forbidden []
- bike-sharing__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'count_copy'}, {'op': 'clip_outliers', 'column': 'humidity'}, {'op': 'standardize_text', 'column': 'season'}]; forbidden []
- house-sales__s1.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'long'}]; forbidden []
- house-sales__s2.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'sqft_living15'}]; forbidden []
- house-sales__s3.csv: missing [{'op': 'drop_column', 'column': 'record_id'}, {'op': 'drop_column', 'column': 'export_batch'}, {'op': 'drop_column', 'column': 'price_copy'}, {'op': 'clip_outliers', 'column': 'sqft_lot15'}]; forbidden []

## Stage times (ms)

| Dataset | Upload+profile | Plan | Execute (+charts) | Models | Report |
|---|---|---|---|---|---|
| titanic__s1.csv | 177 | 28 | 1606 | 2785 | 121 |
| titanic__s2.csv | 150 | 19 | 1012 | 2334 | 103 |
| titanic__s3.csv | 157 | 19 | 1134 | 2824 | 101 |
| housing__s1.csv | 973 | 16 | 2581 | 7463 | 113 |
| housing__s2.csv | 891 | 16 | 2414 | 7401 | 106 |
| housing__s3.csv | 937 | 17 | 2453 | 7467 | 104 |
| telco_churn__s1.csv | 746 | 16 | 2105 | 4980 | 106 |
| telco_churn__s2.csv | 728 | 16 | 2107 | 4996 | 103 |
| telco_churn__s3.csv | 737 | 17 | 2135 | 5020 | 109 |
| credit-g__s1.csv | 136 | 16 | 1234 | 3283 | 115 |
| credit-g__s2.csv | 137 | 16 | 1188 | 3343 | 107 |
| credit-g__s3.csv | 146 | 16 | 1194 | 3278 | 109 |
| diabetes__s1.csv | 78 | 16 | 941 | 1899 | 105 |
| diabetes__s2.csv | 80 | 16 | 930 | 1923 | 95 |
| diabetes__s3.csv | 79 | 16 | 941 | 1885 | 96 |
| adult__s1.csv | 3052 | 16 | 9079 | 14423 | 108 |
| adult__s2.csv | 3047 | 22 | 9250 | 13847 | 102 |
| adult__s3.csv | 2908 | 17 | 8849 | 13999 | 105 |
| bank-marketing__s1.csv | 2409 | 16 | 5442 | 11348 | 106 |
| bank-marketing__s2.csv | 2412 | 16 | 5452 | 11387 | 101 |
| bank-marketing__s3.csv | 2436 | 16 | 5472 | 14280 | 102 |
| blood-transfusion__s1.csv | 67 | 16 | 595 | 2105 | 91 |
| blood-transfusion__s2.csv | 70 | 17 | 761 | 2151 | 87 |
| blood-transfusion__s3.csv | 72 | 23 | 781 | 1758 | 91 |
| breast-w__s1.csv | 80 | 17 | 1395 | 2595 | 148 |
| breast-w__s2.csv | 118 | 26 | 1114 | 2261 | 107 |
| breast-w__s3.csv | 79 | 17 | 1111 | 2175 | 109 |
| spambase__s1.csv | 706 | 31 | 2117 | 6626 | 128 |
| spambase__s2.csv | 507 | 17 | 1838 | 6563 | 168 |
| spambase__s3.csv | 502 | 17 | 1880 | 6558 | 109 |
| phoneme__s1.csv | 217 | 16 | 910 | 2195 | 85 |
| phoneme__s2.csv | 223 | 16 | 955 | 2158 | 83 |
| phoneme__s3.csv | 233 | 17 | 937 | 2142 | 80 |
| kc1__s1.csv | 158 | 17 | 1385 | 3227 | 109 |
| kc1__s2.csv | 175 | 17 | 1273 | 3359 | 105 |
| kc1__s3.csv | 157 | 16 | 1291 | 3277 | 109 |
| ilpd__s1.csv | 74 | 16 | 1113 | 2248 | 121 |
| ilpd__s2.csv | 80 | 21 | 1089 | 2132 | 112 |
| ilpd__s3.csv | 81 | 17 | 1125 | 2098 | 108 |
| vehicle__s1.csv | 107 | 17 | 1179 | 3558 | 121 |
| vehicle__s2.csv | 122 | 17 | 1364 | 3663 | 120 |
| vehicle__s3.csv | 123 | 18 | 1356 | 3554 | 118 |
| wdbc__s1.csv | 130 | 23 | 1659 | 4556 | 147 |
| wdbc__s2.csv | 142 | 23 | 1540 | 4024 | 119 |
| wdbc__s3.csv | 125 | 22 | 1254 | 3906 | 118 |
| house-prices__s1.csv | 435 | 22 | 4974 | 7973 | 113 |
| house-prices__s2.csv | 400 | 19 | 4711 | 7656 | 118 |
| house-prices__s3.csv | 407 | 19 | 4643 | 7645 | 112 |
| diamonds__s1.csv | 2447 | 20 | 4665 | 17822 | 109 |
| diamonds__s2.csv | 2433 | 16 | 4708 | 17948 | 112 |
| diamonds__s3.csv | 2530 | 19 | 6006 | 27276 | 106 |
| bike-sharing__s1.csv | 843 | 18 | 2353 | 5967 | 120 |
| bike-sharing__s2.csv | 816 | 16 | 2365 | 7084 | 126 |
| bike-sharing__s3.csv | 1291 | 17 | 2284 | 5649 | 101 |
| house-sales__s1.csv | 1230 | 17 | 2572 | 10400 | 109 |
| house-sales__s2.csv | 1133 | 16 | 2690 | 10006 | 105 |
| house-sales__s3.csv | 1136 | 16 | 2669 | 9559 | 109 |

## Reproducibility (NFR-11: executed plan replayed in a fresh session)

| Dataset | Cleaned CSV | Charts | Model scores | Report re-render | Report across sessions |
|---|---|---|---|---|---|

Environment: Python 3.11.9 on Windows 10
