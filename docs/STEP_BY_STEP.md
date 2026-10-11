# Learn by running the project

## 1. Inspect the data

Open the first few rows of `data/raw/shipments.csv`, then read the data dictionary. Find one shipment and locate its carrier, route, ports and events. Explain why the events table has more rows than shipments.

## 2. Understand generation

Read `src/generate_data.py`. Change the seed only for a separate experiment using a fresh database. Identify the carrier, route and seasonal effects, and explain why random variation prevents perfect prediction.

## 3. Validate and load

Run `python -m src.etl` using the project venv. Inspect `reports/data_quality.json` and `data/rejected/shipments.csv`. Explain all five rejection categories. Rerun ETL and confirm shipment/event counts stay unchanged while `etl_runs` gains a new audit row.

## 4. Practice SQL

Connect MySQL as described in README. Run the numbered queries in `sql/03_analytics.sql`. Explain a join, a CTE, the difference between RANK and DENSE_RANK, and why LAG is useful for monthly comparisons. Compare carrier rates within a route/service to reduce mix differences.

## 5. Explore with Pandas

Open `notebooks/01_eda.ipynb` with a Jupyter-capable editor, or read/run `src/analytics.py` directly. Compare a grouped delay rate to the SQL result. Explain why average delay across all deliveries differs from average delay among late deliveries.

## 6. Inspect modeling

Run `python -m src.model`. Read the validation comparison and held-out metrics. Use the confusion matrix to explain precision and recall. Change the decision threshold on validation data to explore the tradeoff, keeping test data reserved for final evaluation. Inspect the feature allowlist and temporal label-availability checks.

## 7. Score a shipment

Run `python -m src.predict data/sample_new_shipments.csv reports/new_predictions.csv`. Review scores and threshold labels. No actual delivery information is required.

## 8. Build Power BI

Follow `powerbi/BUILD_GUIDE.md` and save your native report. Reconcile totals and on-time rate with `reports/kpis.json`, then test carrier/route/date slicers. Add your own dashboard screenshots to the README.

## 9. Explain your work

Describe the business question, table grain, validation choices, KPI denominator, leakage prevention, baseline comparison and synthetic-data limitations. Use actual metrics from your run instead of invented performance claims.
