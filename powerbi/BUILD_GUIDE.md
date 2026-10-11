# Build the Power BI report

The native report is now saved as `SupplyChainAnalyticsPolished.pbix`, built by the user in Power BI Desktop. Screenshots and reconciliation results are recorded in `reports/VERIFICATION.md`. The steps below remain a rebuild guide. The interactive report in `reports/dashboard.html` is a separate HTML report.

## Import (no database credentials required)

1. Open Power BI Desktop and create a blank report.
2. Transform data > Manage parameters: create a Text parameter named `ProjectFolder`, set to this project's absolute folder.
3. New source > Blank query > Advanced Editor: paste `Shipments.pq`. Name the query **Shipments**.
4. Import `data/processed/dim_date.csv` as **Dates**, with `date` typed as Date. Mark it as a date table.
5. Import `data/processed/shipment_predictions.csv` as **Predictions**. Set probability and threshold to Decimal Number, predicted_delayed to Whole Number, scored_at to Date/Time.
6. Import `data/processed/model_metrics.csv` as **ModelMetrics** and `data/processed/port_dwell.csv` as **PortDwell**. These are summary tables; do not join PortDwell directly to the fact table or imply that carrier slicers filter it.
7. Relate Dates[date] (one) to Shipments[dispatch_date] (many), single-direction.
8. Relate Shipments[shipment_id] (one) to Predictions[shipment_id] (many), single-direction. The export contains the current model only, one prediction per scored shipment.
9. Create the measures in `measures.dax` one at a time. Set rates to Percentage and cost to USD currency. Set IDs to Do not summarize.
10. View > Themes > Browse: import `theme.json`.

## Page 1: Executive overview

Five cards: Total Shipments, Delivered Shipments, On-Time Rate, Overdue Open, Mean Delay Hours.
Line chart: Dates[year_month] vs On-Time Rate.
Stacked column chart: Dates[year_month], count of shipments, status legend.
Slicers: dispatch date, carrier_name, service_level, origin_port.
Subtitle: **Synthetic data. Snapshot: 1 January 2026 UTC.**

## Page 2: Carrier benchmarking

Bar chart: carrier_name vs Delay Rate. Table: carrier, delivered volume, rate, mean transit.
Matrix: route_id rows, carrier_name columns, Delay Rate values.
Add service level and route slicers to compare similar shipment mixes.

## Page 3: Route and port performance

Table: origin_port, destination_port, Delivered Shipments, Delay Rate, Mean Delay Hours.
Bar chart from PortDwell: port_name vs mean_dwell_hours. Label this chart **All completed port visits; independent of shipment slicers**. Do not summarize means across ports.

## Page 4: Prediction monitoring

Cards: Scored Shipments and Flagged Shipments. Table: shipment_id, carrier_name, status, delay_probability, predicted_delayed.
Use conditional formatting on delay_probability. Add a status slicer to find currently open shipments.
ModelMetrics table: model, split, precision, recall, f1, roc_auc. Keep validation and test rows clearly separated.
Scores are generated retrospectively using dispatch-time features after the training cutoff. The model has not been validated against real operations.

## MySQL alternative

After configuring `.env` and running ETL, connect using Get Data > MySQL database, server `localhost`, database `supply_chain`. Import `vw_shipment_performance`. Install Oracle MySQL Connector/NET if required by the connector.
Add dispatch_date and is_overdue_open in Power Query using the fixed snapshot cutoff to match CSV behavior. Use the CSV route first if you are learning Power BI.
Connector reference: https://learn.microsoft.com/en-us/power-query/connectors/mysql-database

## Reconciliation

With no filters, compare cards to `reports/kpis.json`. On-time rate excludes cancelled and in-transit records. Blank outcomes must stay blank. Check filtered counts against the HTML report. Do not join raw events into Shipments; each shipment has multiple events.
Save the completed report as `powerbi/SupplyChainAnalyticsPolished.pbix`.
