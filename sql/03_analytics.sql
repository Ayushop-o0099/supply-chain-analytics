-- MySQL 8.0+. All rates use completed deliveries unless explicitly noted.
USE supply_chain;

-- 1. Executive KPIs, without event fan-out.
SELECT COUNT(*) AS total_shipments,
       SUM(status='Delivered') AS delivered_shipments,
       AVG(CASE WHEN status='Delivered' THEN 1-is_delayed END) AS on_time_rate,
       AVG(delay_hours) AS mean_delay_hours
FROM vw_shipment_performance;

-- 2. Carrier performance using joins and aggregations.
SELECT c.carrier_name, COUNT(*) AS delivered, AVG(s.actual_delivery_at > s.promised_delivery_at) AS delay_rate
FROM shipments s JOIN carriers c ON s.carrier_id=c.carrier_id
WHERE s.status='Delivered' GROUP BY c.carrier_id,c.carrier_name ORDER BY delay_rate DESC;

-- 3. Route reliability, with minimum sample size.
SELECT route_id, origin_port, destination_port, COUNT(*) AS delivered, AVG(is_delayed) AS delay_rate
FROM vw_shipment_performance WHERE status='Delivered'
GROUP BY route_id,origin_port,destination_port HAVING COUNT(*) >= 100 ORDER BY delay_rate DESC;

-- 4. Month-over-month on-time performance. Cohorts are dispatch months.
WITH monthly AS (
 SELECT DATE_FORMAT(dispatch_at,'%Y-%m') AS month, COUNT(*) AS delivered, AVG(1-is_delayed) AS on_time_rate
 FROM vw_shipment_performance WHERE status='Delivered' GROUP BY month
)
SELECT *, on_time_rate-LAG(on_time_rate) OVER(ORDER BY month) AS change_vs_previous_month FROM monthly;

-- 5. Carrier ranking within route, using a window function.
WITH performance AS (
 SELECT route_id,carrier_name,COUNT(*) AS delivered,AVG(is_delayed) AS delay_rate
 FROM vw_shipment_performance WHERE status='Delivered' GROUP BY route_id,carrier_name HAVING COUNT(*)>=30
)
SELECT *,DENSE_RANK() OVER(PARTITION BY route_id ORDER BY delay_rate) AS carrier_rank FROM performance;

-- 6. Routes worse than the network average, using a subquery.
SELECT route_id,COUNT(*) AS delivered,AVG(is_delayed) AS delay_rate
FROM vw_shipment_performance WHERE status='Delivered' GROUP BY route_id
HAVING COUNT(*)>=100 AND AVG(is_delayed)>(SELECT AVG(is_delayed) FROM vw_shipment_performance WHERE status='Delivered');

-- 7. Shipments whose transit exceeds their route's average.
WITH route_baseline AS (
 SELECT route_id,AVG(transit_hours) AS mean_hours FROM vw_shipment_performance WHERE status='Delivered' GROUP BY route_id
)
SELECT s.shipment_id,s.route_id,s.transit_hours,b.mean_hours
FROM vw_shipment_performance s JOIN route_baseline b ON s.route_id=b.route_id WHERE s.transit_hours>b.mean_hours;

-- 8. Compare carriers within the same route AND service level.
SELECT route_id,service_level,carrier_name,COUNT(*) AS delivered,AVG(is_delayed) AS delay_rate
FROM vw_shipment_performance WHERE status='Delivered'
GROUP BY route_id,service_level,carrier_name HAVING COUNT(*)>=30 ORDER BY route_id,service_level,delay_rate;

-- 9. Open overdue shipments at the fixed synthetic snapshot.
SELECT shipment_id,carrier_id,route_id,promised_delivery_at,
       TIMESTAMPDIFF(HOUR,promised_delivery_at,'2026-01-01 00:00:00') AS overdue_hours
FROM shipments WHERE status='In Transit' AND promised_delivery_at<'2026-01-01 00:00:00';

-- 10. Port dwell: aggregate events first, pair by shipment and port.
WITH visits AS (
 SELECT shipment_id,port_id,
 MIN(CASE WHEN event_type='Port Arrived' THEN event_at END) AS arrived,
 MIN(CASE WHEN event_type='Port Departed' THEN event_at END) AS departed
 FROM shipment_events GROUP BY shipment_id,port_id
)
SELECT p.port_name,COUNT(*) AS completed_visits,AVG(TIMESTAMPDIFF(SECOND,v.arrived,v.departed)/3600.0) AS mean_dwell_hours
FROM visits v JOIN ports p ON p.port_id=v.port_id WHERE v.arrived IS NOT NULL AND v.departed>=v.arrived
GROUP BY p.port_id,p.port_name;

-- 11. Cost and distance by service (synthetic quoted cost, all statuses).
SELECT service_level,COUNT(*) AS shipments,AVG(shipping_cost_usd) AS mean_cost_usd,
SUM(shipping_cost_usd)/SUM(distance_km) AS cost_per_shipment_km FROM vw_shipment_performance GROUP BY service_level;

-- 12. Delivery status distribution.
SELECT status,COUNT(*) AS shipments,COUNT(*)*1.0/SUM(COUNT(*)) OVER() AS share FROM shipments GROUP BY status;

-- 13. Event completeness without multiplying shipment costs.
WITH event_counts AS (SELECT shipment_id,COUNT(*) AS events FROM shipment_events GROUP BY shipment_id)
SELECT s.shipment_id,s.shipping_cost_usd,COALESCE(e.events,0) AS events FROM shipments s LEFT JOIN event_counts e ON s.shipment_id=e.shipment_id;

-- 14. Most recent available score per shipment across model versions.
WITH ranked AS (
 SELECT p.*,ROW_NUMBER() OVER(PARTITION BY shipment_id ORDER BY scored_at DESC,model_version) AS rn
 FROM shipment_predictions p
)
SELECT r.shipment_id,r.delay_probability,r.predicted_delayed,r.model_version,s.status
FROM ranked r JOIN shipments s ON s.shipment_id=r.shipment_id WHERE r.rn=1 ORDER BY delay_probability DESC;

-- 15. ETL audit trail.
SELECT run_id,started_at,status,input_rows,accepted_rows,rejected_rows FROM etl_runs ORDER BY started_at DESC;
