## Pace baselines (2025 holdout)

| model | mae_s | rmse_s | r2 | n_laps_evaluated | notes |
|---|---|---|---|---|---|
| persistence | 0,408 | 0,762 | 0,995 | 21247 | y_pred = Prev_LapTime |
| team_circuit_median | 3,062 | 4,712 | 0,798 | 21247 | median LapTime_s from 2023+2024 by (Team, GP_Name) |
| xgb_delta_prod | 0,410 | 0,765 | 0,995 | 21247 | XGBoost delta + Prev_LapTime, 25 production features |
