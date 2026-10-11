USE supply_chain;
-- Each query should return zero violations after ETL.
SELECT shipment_id,COUNT(*) FROM shipments GROUP BY shipment_id HAVING COUNT(*)>1;
SELECT shipment_id FROM shipments WHERE weight_kg<=0 OR shipping_cost_usd<0;
SELECT shipment_id FROM shipments WHERE promised_delivery_at<dispatch_at OR actual_delivery_at<dispatch_at;
SELECT shipment_id FROM shipments WHERE (status='Delivered')<>(actual_delivery_at IS NOT NULL);
SELECT s.shipment_id FROM shipments s LEFT JOIN carriers c ON s.carrier_id=c.carrier_id WHERE c.carrier_id IS NULL;
SELECT e.event_id FROM shipment_events e LEFT JOIN shipments s ON e.shipment_id=s.shipment_id WHERE s.shipment_id IS NULL;
SELECT e.event_id FROM shipment_events e JOIN shipments s ON e.shipment_id=s.shipment_id WHERE e.event_at<s.dispatch_at;
