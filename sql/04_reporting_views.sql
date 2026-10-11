USE supply_chain;
CREATE OR REPLACE VIEW vw_shipment_performance AS
SELECT s.*,c.carrier_name,r.distance_km,r.origin_port_id,r.destination_port_id,
       p.port_name AS origin_port,q.port_name AS destination_port,
       CASE WHEN s.status='Delivered' THEN (s.actual_delivery_at>s.promised_delivery_at) END AS is_delayed,
       CASE WHEN s.status='Delivered' THEN GREATEST(0,TIMESTAMPDIFF(SECOND,s.promised_delivery_at,s.actual_delivery_at)/3600.0) END AS delay_hours,
       CASE WHEN s.status='Delivered' THEN TIMESTAMPDIFF(SECOND,s.dispatch_at,s.actual_delivery_at)/3600.0 END AS transit_hours
FROM shipments s JOIN carriers c ON c.carrier_id=s.carrier_id
JOIN routes r ON r.route_id=s.route_id JOIN ports p ON p.port_id=r.origin_port_id
JOIN ports q ON q.port_id=r.destination_port_id;
