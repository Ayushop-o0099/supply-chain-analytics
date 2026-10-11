# Delay model evaluation

Synthetic data. Selected model: **logistic_regression**.

Threshold: 0.25. Train / validation / test rows: 13336 / 2516 / 2475.


| Test metric | Value |
|---|---|

| precision | 0.4176 |

| recall | 0.7570 |

| f1 | 0.5382 |

| roc_auc | 0.7098 |

| average_precision | 0.5160 |


Confusion matrix (actual rows, predicted columns; on-time then delayed): `[[927, 795], [183, 570]]`.


Only dispatch-time features are used. Training outcomes must be known before validation starts; validation outcomes must be known before testing starts.


Synthetic data. Delivered-only test outcomes exclude unresolved shipments; recent cohorts are censored. Model scores are not calibrated operational probabilities.