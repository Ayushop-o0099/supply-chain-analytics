-- Generated from src/database.py. MySQL 8.0+.
CREATE DATABASE IF NOT EXISTS supply_chain CHARACTER SET utf8mb4;
USE supply_chain;


CREATE TABLE IF NOT EXISTS carriers (
	carrier_id INTEGER NOT NULL AUTO_INCREMENT,
	carrier_name VARCHAR(80) NOT NULL,
	PRIMARY KEY (carrier_id)
)

;


CREATE TABLE IF NOT EXISTS etl_runs (
	run_id VARCHAR(36) NOT NULL,
	started_at DATETIME,
	completed_at DATETIME,
	status VARCHAR(20),
	input_rows INTEGER,
	accepted_rows INTEGER,
	rejected_rows INTEGER,
	message VARCHAR(1000),
	PRIMARY KEY (run_id)
)

;


CREATE TABLE IF NOT EXISTS ports (
	port_id INTEGER NOT NULL AUTO_INCREMENT,
	port_name VARCHAR(80) NOT NULL,
	country VARCHAR(80),
	latitude FLOAT,
	longitude FLOAT,
	PRIMARY KEY (port_id)
)

;


CREATE TABLE IF NOT EXISTS routes (
	route_id INTEGER NOT NULL AUTO_INCREMENT,
	origin_port_id INTEGER NOT NULL,
	destination_port_id INTEGER NOT NULL,
	distance_km FLOAT NOT NULL,
	PRIMARY KEY (route_id),
	FOREIGN KEY(origin_port_id) REFERENCES ports (port_id),
	FOREIGN KEY(destination_port_id) REFERENCES ports (port_id)
)

;


CREATE TABLE IF NOT EXISTS shipments (
	shipment_id VARCHAR(32) NOT NULL,
	carrier_id INTEGER NOT NULL,
	route_id INTEGER NOT NULL,
	service_level VARCHAR(20) NOT NULL,
	weight_kg FLOAT NOT NULL,
	shipping_cost_usd FLOAT NOT NULL,
	dispatch_at DATETIME NOT NULL,
	promised_delivery_at DATETIME NOT NULL,
	actual_delivery_at DATETIME,
	status VARCHAR(20) NOT NULL,
	PRIMARY KEY (shipment_id),
	FOREIGN KEY(carrier_id) REFERENCES carriers (carrier_id),
	FOREIGN KEY(route_id) REFERENCES routes (route_id)
)

;

CREATE INDEX ix_shipments_carrier_route ON shipments (carrier_id, route_id);

CREATE INDEX ix_shipments_dispatch ON shipments (dispatch_at);


CREATE TABLE IF NOT EXISTS shipment_events (
	event_id INTEGER NOT NULL,
	shipment_id VARCHAR(32) NOT NULL,
	event_type VARCHAR(30) NOT NULL,
	event_at DATETIME NOT NULL,
	port_id INTEGER NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(shipment_id) REFERENCES shipments (shipment_id),
	FOREIGN KEY(port_id) REFERENCES ports (port_id)
)

;

CREATE INDEX ix_events_shipment ON shipment_events (shipment_id);


CREATE TABLE IF NOT EXISTS shipment_predictions (
	shipment_id VARCHAR(32) NOT NULL,
	model_version VARCHAR(64) NOT NULL,
	delay_probability FLOAT NOT NULL,
	predicted_delayed INTEGER NOT NULL,
	threshold FLOAT NOT NULL,
	scored_at DATETIME NOT NULL,
	PRIMARY KEY (shipment_id, model_version),
	FOREIGN KEY(shipment_id) REFERENCES shipments (shipment_id)
)

;
