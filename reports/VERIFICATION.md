# Verification results

Verified on 10 October 2026 using the versions in `requirements-tested.txt`.

| Check | Result |
|---|---|
| Full generation, ETL, analytics, training, scoring and report build | Passed |
| Shipment rows accepted / rejected | 20,000 / 100 |
| Shipment events loaded | 78,282 |
| Repeat ETL against the same database | Counts unchanged; upserts and audit record succeeded |
| Automated tests | 11 passed |
| Raw CSV manifest counts and SHA-256 hashes | Matched |
| Python and SQL shipment counts, delayed counts and on-time rates | Matched |
| Notebook code cells | Executed successfully with a non-interactive plotting backend |
| Saved model inference | Five example shipments scored successfully |
| Python source compilation | Passed |
| HTML JavaScript syntax | Passed Node.js syntax check |
| Static EDA chart | Visually inspected |

## Measured results on synthetic data

- Delivered: 19,223; delayed among delivered: 5,397.
- On-time rate: 71.9243%; overdue open: 17; cancelled: 292.
- Selected model: logistic regression; validation-selected threshold: 0.25.
- Held-out test precision: 0.4176; recall: 0.7570; F1: 0.5382; ROC-AUC: 0.7098.

## MySQL and Power BI follow-up verification

- User-provided terminal output confirms connection to MySQL 8.0.42, successful ETL with 20,000 shipments and 78,282 events, and a successful analytics refresh. Workbench screenshots confirm delivery KPIs, carrier and route analyses, monthly LAG, carrier DENSE_RANK, a network-average subquery, and persisted model predictions. This is interactive user-run verification; the automated test suite was originally run against SQLite.
- The native file `powerbi/SupplyChainAnalyticsPolished.pbix` exists in the project. User-provided screenshots show four pages built in Power BI Desktop. The saved binary has not been independently reopened by the assistant.
- Executive Overview: 20K shipments, 71.92% on-time, 17 overdue open. Atlas Freight filter: 3,310 total, 87.99% on-time, 1 overdue open.
- Carrier Performance totals: 19,223 delivered, 28.08% delayed, 10.14 mean delay hours. Route table: Chennai to Singapore, 791 delivered and 57.27% delayed. Port chart uses Average; its summary table is disconnected from shipment filters.
- Prediction Monitoring: 5,917 scored and 3,105 flagged without filters; In Transit selection shows 485 scored and 279 flagged. Percent formatting and status-filtered rows were confirmed from screenshots.
- Screenshots are preserved under `reports/screenshots`. The synthetic snapshot note appears on Carrier Performance; Executive Overview screenshot does not show it. Widening the prediction table to show full headers would improve presentation but does not affect the checked results.

## Remaining limitations

- Power BI imports curated CSVs. CSV source paths must be updated when moving the project, and Power BI must be refreshed after regenerating the exports.
- Browser security policy blocked the local-file HTML preview. JavaScript syntax was checked, but browser rendering, slicer interaction and CSV download were not exercised through browser automation.
- Test warnings were limited to intentionally malformed date parsing and headless notebook display. All validation assertions passed.
