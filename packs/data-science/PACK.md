# Data science knowledge

## Profile before analysis (always first)

- Shape, dtypes, null counts, duplicates, and cardinality per column.
- Target balance for classification; range and outliers for regression.
- Time coverage and entity counts — know the unit of analysis.

## Validation traps that invalidate results

- **Leakage**: any feature unavailable at prediction time (post-outcome fields, aggregates over the future, target-derived encodings). Split by time/entity before encoding.
- **Duplication across splits**: same entity in train and test → inflated scores. Group-split by entity ID.
- **Silent coercion**: dates parsed as strings, IDs as numbers, NaN vs empty string. Assert dtypes explicitly.
- **Selection bias**: state how rows were selected; a number without provenance is not evidence.

## Modeling discipline

- Baseline first (mean / majority / trivial rule). Every model must beat it measurably.
- One change per experiment; log configuration, seed, and data hash with each result.
- Metrics must match the decision (precision/recall trade-off, calibration, cost) — accuracy alone is not evidence.

## Reproducibility contract

- Pin data version + code version + seed for every reported number.
- Analysis scripts run top-to-bottom from raw inputs; no hidden notebook state.
- Derived artifacts (cleaned data, features, models) carry provenance: which script, which inputs, which parameters.

## Communication

- Report uncertainty (intervals, sample sizes) — a point estimate without spread is a guess.
- Charts: label axes with units, title states the takeaway, annotate the baseline.
- Distinguish "the data shows" from "I hypothesize" in every summary.

## Agent-specific pitfalls

- Never impute the target; never fit scalers/encoders on the test split.
- Cap printed output: profile summaries, not full dumps.
- If a result looks too good (>0.99 AUC on real data), hunt leakage before celebrating.
