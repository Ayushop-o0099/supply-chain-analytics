# Exploratory analysis

Synthetic data, as of 2026-01-01 00:00:00 UTC. These patterns reflect the generator.

- 19,223 of 20,000 shipments are delivered.
- On-time rate is 71.9% among completed deliveries.
- Atlas Freight has the lowest observed delay rate (12.0%).
- Falcon Shipping has the highest observed delay rate (43.6%).
- Median transit time is 404.6 hours.
- The 90th percentile delay across delivered shipments is 39.8 hours.
- 17 open shipments are overdue at the fixed cutoff.

Carrier CSV includes 95% Wilson intervals. Rates are descriptive; route mix and service levels confound raw comparisons. Use SQL query 8 to compare carriers within routes. Recent dispatch cohorts are incomplete, so their delivered-only rates may be optimistic. Port dwell uses only visits with both arrival and departure events.
