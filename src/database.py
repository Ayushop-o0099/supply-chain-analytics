"""Shared relational schema and transactional, idempotent upserts."""
import math
import pandas as pd
from sqlalchemy import (MetaData, Table, Column, Integer, String, Float, DateTime,
                        ForeignKey, Index, create_engine, event, text)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .config import database_url

metadata = MetaData()
carriers = Table('carriers', metadata, Column('carrier_id', Integer, primary_key=True), Column('carrier_name', String(80), nullable=False))
ports = Table('ports', metadata, Column('port_id', Integer, primary_key=True), Column('port_name', String(80), nullable=False),
              Column('country', String(80)), Column('latitude', Float), Column('longitude', Float))
routes = Table('routes', metadata, Column('route_id', Integer, primary_key=True),
               Column('origin_port_id', Integer, ForeignKey('ports.port_id'), nullable=False),
               Column('destination_port_id', Integer, ForeignKey('ports.port_id'), nullable=False), Column('distance_km', Float, nullable=False))
shipments = Table('shipments', metadata, Column('shipment_id', String(32), primary_key=True),
    Column('carrier_id', Integer, ForeignKey('carriers.carrier_id'), nullable=False),
    Column('route_id', Integer, ForeignKey('routes.route_id'), nullable=False),
    Column('service_level', String(20), nullable=False), Column('weight_kg', Float, nullable=False),
    Column('shipping_cost_usd', Float, nullable=False), Column('dispatch_at', DateTime, nullable=False),
    Column('promised_delivery_at', DateTime, nullable=False), Column('actual_delivery_at', DateTime), Column('status', String(20), nullable=False))
events = Table('shipment_events', metadata, Column('event_id', Integer, primary_key=True, autoincrement=False),
    Column('shipment_id', String(32), ForeignKey('shipments.shipment_id'), nullable=False),
    Column('event_type', String(30), nullable=False), Column('event_at', DateTime, nullable=False),
    Column('port_id', Integer, ForeignKey('ports.port_id'), nullable=False))
predictions = Table('shipment_predictions', metadata,
    Column('shipment_id', String(32), ForeignKey('shipments.shipment_id'), primary_key=True),
    Column('model_version', String(64), primary_key=True), Column('delay_probability', Float, nullable=False),
    Column('predicted_delayed', Integer, nullable=False), Column('threshold', Float, nullable=False),
    Column('scored_at', DateTime, nullable=False))
etl_runs = Table('etl_runs', metadata, Column('run_id', String(36), primary_key=True), Column('started_at', DateTime),
    Column('completed_at', DateTime), Column('status', String(20)), Column('input_rows', Integer),
    Column('accepted_rows', Integer), Column('rejected_rows', Integer), Column('message', String(1000)))
Index('ix_shipments_dispatch', shipments.c.dispatch_at)
Index('ix_shipments_carrier_route', shipments.c.carrier_id, shipments.c.route_id)
Index('ix_events_shipment', events.c.shipment_id)


def engine_for(url=None):
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def foreign_keys(dbapi_connection, _):
            dbapi_connection.execute('PRAGMA foreign_keys=ON')
    elif engine.dialect.name != 'mysql':
        raise ValueError('Supported databases: sqlite and mysql')
    return engine


def records(frame):
    clean = frame.astype(object).where(pd.notna(frame), None)
    return [{k: v.to_pydatetime() if isinstance(v, pd.Timestamp) else v for k, v in row.items()}
            for row in clean.to_dict(orient='records')]


def upsert(conn, table_name, frame):
    table = metadata.tables[table_name]
    data = records(frame)
    for start in range(0, len(data), 500):
        batch = data[start:start+500]
        if conn.dialect.name == 'mysql':
            stmt = mysql_insert(table).values(batch)
            stmt = stmt.on_duplicate_key_update(**{c.name: stmt.inserted[c.name] for c in table.columns if not c.primary_key})
        else:
            stmt = sqlite_insert(table).values(batch)
            stmt = stmt.on_conflict_do_update(index_elements=[c.name for c in table.primary_key],
                set_={c.name: stmt.excluded[c.name] for c in table.columns if not c.primary_key})
        conn.execute(stmt)


def create_views(conn):
    hours = ("TIMESTAMPDIFF(SECOND, s.promised_delivery_at, s.actual_delivery_at)/3600.0"
             if conn.dialect.name == 'mysql' else "(julianday(s.actual_delivery_at)-julianday(s.promised_delivery_at))*24.0")
    transit = ("TIMESTAMPDIFF(SECOND, s.dispatch_at, s.actual_delivery_at)/3600.0"
               if conn.dialect.name == 'mysql' else "(julianday(s.actual_delivery_at)-julianday(s.dispatch_at))*24.0")
    conn.execute(text('DROP VIEW IF EXISTS vw_shipment_performance'))
    conn.execute(text(f'''CREATE VIEW vw_shipment_performance AS
        SELECT s.*, c.carrier_name, r.distance_km, r.origin_port_id, r.destination_port_id,
        p.port_name AS origin_port, q.port_name AS destination_port,
        CASE WHEN s.status='Delivered' THEN CASE WHEN s.actual_delivery_at > s.promised_delivery_at THEN 1 ELSE 0 END ELSE NULL END AS is_delayed,
        CASE WHEN s.status='Delivered' THEN CASE WHEN s.actual_delivery_at > s.promised_delivery_at THEN {hours} ELSE 0 END ELSE NULL END AS delay_hours,
        CASE WHEN s.status='Delivered' THEN {transit} ELSE NULL END AS transit_hours
        FROM shipments s JOIN carriers c ON c.carrier_id=s.carrier_id
        JOIN routes r ON r.route_id=s.route_id JOIN ports p ON p.port_id=r.origin_port_id
        JOIN ports q ON q.port_id=r.destination_port_id'''))
