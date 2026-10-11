import numpy as np
import pandas as pd

DATE_COLS = ['dispatch_at', 'promised_delivery_at', 'actual_delivery_at']
SHIPMENT_COLUMNS = ['shipment_id', 'carrier_id', 'route_id', 'service_level', 'weight_kg',
                    'shipping_cost_usd', *DATE_COLS, 'status']


def validate_shipments(raw, carriers, routes, as_of):
    missing = set(SHIPMENT_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f'Missing shipment columns: {sorted(missing)}')
    df = raw[SHIPMENT_COLUMNS].copy().reset_index(drop=True)
    reasons = pd.Series('', index=df.index)

    def reject(mask, reason):
        mask = pd.Series(mask, index=df.index).fillna(True)
        reasons.loc[mask] += reason + '; '

    for col in DATE_COLS:
        original = df[col]
        df[col] = pd.to_datetime(original, errors='coerce', utc=True).dt.tz_localize(None)
        reject(original.notna() & df[col].isna(), f'invalid {col}')
    for col in ['carrier_id', 'route_id', 'weight_kg', 'shipping_cost_usd']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        reject(df[col].isna() | ~np.isfinite(df[col]), f'invalid {col}')
    reject(df.shipment_id.isna() | df.shipment_id.astype(str).str.strip().eq(''), 'missing shipment_id')
    # Keep first occurrence deterministically; later duplicates are quarantined.
    reject(df.shipment_id.duplicated(), 'duplicate shipment_id')
    reject(~df.carrier_id.isin(carriers.carrier_id), 'unknown carrier')
    reject(~df.route_id.isin(routes.route_id), 'unknown route')
    reject(df.weight_kg <= 0, 'nonpositive weight')
    reject(df.shipping_cost_usd < 0, 'negative cost')
    reject(df.dispatch_at.isna() | df.promised_delivery_at.isna(), 'missing required timestamp')
    reject(df.promised_delivery_at < df.dispatch_at, 'promise before dispatch')
    reject(df.actual_delivery_at < df.dispatch_at, 'delivery before dispatch')
    reject(~df.status.isin(['Delivered', 'In Transit', 'Cancelled']), 'unknown status')
    reject(~df.service_level.isin(['Standard', 'Priority']), 'unknown service')
    reject((df.status == 'Delivered') != df.actual_delivery_at.notna(), 'status/delivery mismatch')
    reject((df.dispatch_at > pd.Timestamp(as_of)) | (df.actual_delivery_at > pd.Timestamp(as_of)), 'future actual timestamp')
    valid = df.loc[reasons.eq('')].copy()
    invalid = raw.reset_index(drop=True).loc[reasons.ne('')].copy()
    invalid['rejection_reason'] = reasons.loc[reasons.ne('')].str.rstrip('; ')
    return valid, invalid


def validate_dimensions(tables):
    for name, key in [('carriers', 'carrier_id'), ('ports', 'port_id'), ('routes', 'route_id')]:
        frame = tables[name]
        if frame[key].isna().any() or frame[key].duplicated().any():
            raise ValueError(f'{name}: missing or duplicate primary key')
    r, p = tables['routes'], tables['ports']
    if not (r.origin_port_id.isin(p.port_id) & r.destination_port_id.isin(p.port_id)).all():
        raise ValueError('routes: unknown port')
    if not (r.distance_km.gt(0) & r.origin_port_id.ne(r.destination_port_id)).all():
        raise ValueError('routes: invalid distance or identical ports')


def validate_events(raw, shipments, ports, as_of):
    df = raw.copy()
    df['event_at'] = pd.to_datetime(df.event_at, errors='coerce', utc=True).dt.tz_localize(None)
    dispatch = df.shipment_id.map(shipments.set_index('shipment_id').dispatch_at)
    bad = (df.event_id.isna() | df.event_id.duplicated() | ~df.shipment_id.isin(shipments.shipment_id)
           | ~df.port_id.isin(ports.port_id) | df.event_at.isna()
           | (df.event_at < dispatch) | (df.event_at > pd.Timestamp(as_of))
           | ~df.event_type.isin(['Dispatched', 'Port Arrived', 'Port Departed', 'Delivered', 'Cancelled']))
    rejected = raw.loc[bad].copy()
    rejected['rejection_reason'] = 'invalid event key, reference, type, or timestamp'
    return df.loc[~bad].copy(), rejected
