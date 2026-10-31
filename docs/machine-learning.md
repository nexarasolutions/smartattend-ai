# Attendance Prediction: ML Design and Limits

## Scope and data

The model is an early-warning estimate for a student's future subject attendance, not an attendance record, disciplinary decision or guaranteed outcome. Only actual attendance records in the Manus-managed database are eligible. The dashboard's clearly labeled fictional preview fixtures are not imported, used for training or returned by a live prediction endpoint.

Training starts with `RandomForestRegressor` from Scikit-learn. The feature set is subject-specific:

1. `total_classes`: number of recorded classes before the prediction cutoff.
2. `present_classes`: Present or Late records before the cutoff.
3. `attendance_percentage`: historical Present/Late percentage before cutoff.
4. `recent_attendance_percentage`: Present/Late percentage over the most recent up-to-five records.
5. `attendance_trend`: least-squares slope across that recent sequence.

At least three past observations are required to construct features. The target is the student's attendance percentage (Present or Late) in the *next three recorded sessions* for that subject. There are no future-derived feature values; future sessions are labels only. Each persisted prediction retains its model version, latest-history cutoff and generated time.

## Evaluation and model lifecycle

Training requires at least 12 valid rolling windows, five distinct chronological cutoffs, and enough rows on both sides of the holdout. The split is by time, not randomly by rows; a purge removes training examples whose future target window overlaps the validation start. A Random Forest (300 trees, fixed random seed, leaf size 2) is evaluated against a persistence baseline that predicts the current historical attendance percentage.

Metrics retained for a candidate include the chronological validation boundary, training/validation counts, MAE and RMSE in percentage points, optional R², baseline MAE, whether the candidate beats the baseline, a model-artifact hash, and feature importance. Small/inadequate datasets fail closed with a descriptive response and create no model. Model candidates begin in a review state. An Admin explicitly activates a candidate version; prediction generation uses only the active version and persists forecast rows separately from attendance facts.

The Admin UI exposes training, candidate review, version activation, prediction generation and evaluation metrics. Student/Staff/Admin reads are filtered by server-side database role and class scope. These responses do not fall back to preview fixtures.

## Risk and confidence

The model returns a predicted percentage, a threshold-based risk category and a small set of influential features. The risk category is a prioritization aid, not a probability or diagnosis. `calibrated_confidence` remains `null`: uncertainty intervals/probabilities are not calibrated, and the implementation does not claim otherwise.

## Limitations

- A small or uneven historical cohort may not support reliable forecasts; current checks require adequate chronological windows.
- Subject-specific histories may differ from a student's overall attendance and may be sparse.
- A retrospective chronological holdout is not a prospective deployment study and may not capture changes in term policy, schedule, teacher, sensor quality or student circumstances.
- Association/feature importance is not causal explanation; it should not be used to label or punish a student.
- The rolling target is limited to the next three observed sessions, not the entire term or a fixed calendar horizon.
- Predictions can be stale after new attendance until Admin-triggered regeneration; generated time/cutoff are part of every persisted result.
- No calibrated confidence interval is provided. Do not present the figure as certainty or as a substitute for a human conversation.

Before institutional use, review the local attendance policy, data-minimization/legal basis, student notice/access controls, fairness and subgroup performance, prospective calibration, operational threshold choices and model-monitoring/rollback process. No production dataset was fabricated to make a model appear trained.
