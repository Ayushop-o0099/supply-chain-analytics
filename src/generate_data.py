"""Generate fictional shipments. No real company/customer performance is represented."""
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from .config import ROOT, AS_OF, prepare_dirs


def generate(n=20000, seed=42):
    if n < 1000:
        raise ValueError('Use at least 1,000 shipments for chronological model evaluation.')
    prepare_dirs()
    rng = np.random.default_rng(seed)
    carriers = pd.DataFrame({
        'carrier_id': range(1, 7),
        'carrier_name': ['Atlas Freight', 'BlueHarbor Cargo', 'Cedar Logistics',
                         'Delta Transit', 'Evergreen Link', 'Falcon Shipping'],
    })
    ports = pd.DataFrame([
        (1, 'Mumbai', 'India', 19.08, 72.88), (2, 'Chennai', 'India', 13.08, 80.27),
        (3, 'Singapore', 'Singapore', 1.29, 103.85), (4, 'Dubai', 'UAE', 25.20, 55.27),
        (5, 'Rotterdam', 'Netherlands', 51.92, 4.48), (6, 'Shanghai', 'China', 31.23, 121.47),
        (7, 'Los Angeles', 'USA', 33.74, -118.27), (8, 'Hamburg', 'Germany', 53.55, 9.99),
    ], columns=['port_id', 'port_name', 'country', 'latitude', 'longitude'])
    pairs = [(a, b) for a in range(1, 9) for b in range(1, 9) if a != b]
    chosen = rng.choice(len(pairs), size=24, replace=False)
    routes = pd.DataFrame([
        (i + 1, *pairs[j], int(rng.integers(1500, 18000))) for i, j in enumerate(chosen)
    ], columns=['route_id', 'origin_port_id', 'destination_port_id', 'distance_km'])
    start = pd.Timestamp('2024-01-01')
    cutoff = pd.Timestamp(AS_OF)
    dispatch = start + pd.to_timedelta(np.sort(rng.integers(0, int((cutoff-start).total_seconds()), n)), unit='s')
    route_idx = rng.integers(0, len(routes), n)
    carrier = rng.integers(1, 7, n)
    service = rng.choice(['Standard', 'Priority'], n, p=[0.72, 0.28])
    weight = np.round(rng.lognormal(7.5, 0.8, n), 2)
    distance = routes.distance_km.to_numpy()[route_idx]
    planned_hours = distance / 30 + 72 - (service == 'Priority') * 36
    promised = dispatch + pd.to_timedelta(planned_hours, unit='h')
    # A stochastic process: route, carrier, season and shipment size influence risk.
    route_effect = rng.normal(0, 0.6, len(routes))[route_idx]
    carrier_effect = np.array([-0.9, -0.4, 0.0, 0.4, 0.75, 1.0])[carrier - 1]
    peak = np.isin(dispatch.month, [7, 8, 11, 12])
    logit = -1.1 + carrier_effect + route_effect + 0.65*peak + 0.25*np.log(weight/1800) - 0.65*(service == 'Priority')
    late = rng.random(n) < 1/(1 + np.exp(-logit))
    deviation = np.where(late, rng.gamma(2.5, 14, n)+1, -rng.uniform(1, 30, n))
    actual = dispatch + pd.to_timedelta(planned_hours + deviation, unit='h')
    # Cancelled here means an operational cancellation after dispatch.
    cancelled = rng.random(n) < 0.015
    status = np.where(cancelled, 'Cancelled', np.where(actual <= cutoff, 'Delivered', 'In Transit'))
    actual_visible = pd.Series(actual).where(status == 'Delivered')
    shipments = pd.DataFrame({
        'shipment_id': [f'SHP{i:07d}' for i in range(1, n+1)],
        'carrier_id': carrier, 'route_id': route_idx+1, 'service_level': service,
        'weight_kg': weight,
        'shipping_cost_usd': np.round(100 + distance*0.06 + weight*0.03 + (service == 'Priority')*200 + rng.uniform(0,100,n), 2),
        'dispatch_at': dispatch, 'promised_delivery_at': promised,
        'actual_delivery_at': actual_visible, 'status': status,
    })
    events = []
    for i, s in shipments.iterrows():
        route = routes.iloc[route_idx[i]]
        arrival = s.dispatch_at + pd.Timedelta(hours=float((planned_hours[i]+deviation[i])*0.6))
        departure = arrival + pd.Timedelta(hours=float((planned_hours[i]+deviation[i])*0.15))
        candidates = [('Dispatched', s.dispatch_at, route.origin_port_id)]
        if s.status == 'Cancelled':
            cancel_at = min(s.dispatch_at + pd.Timedelta(hours=6), cutoff)
            candidates.append(('Cancelled', cancel_at, route.origin_port_id))
        else:
            candidates.extend([('Port Arrived', arrival, route.destination_port_id),
                               ('Port Departed', departure, route.destination_port_id),
                               ('Delivered', actual[i], route.destination_port_id)])
        for event_type, at, port in candidates:
            if at <= cutoff:
                events.append((len(events)+1, s.shipment_id, event_type, at, int(port)))
    event_df = pd.DataFrame(events, columns=['event_id', 'shipment_id', 'event_type', 'event_at', 'port_id'])
    # Append 100 bad records without corrupting the 20,000 legitimate source rows.
    bad = shipments.iloc[:100].copy()
    for i in range(20, 100):
        bad.loc[i, 'shipment_id'] = f'BAD{i:07d}'
    bad.loc[20:39, 'weight_kg'] = -5
    bad.loc[40:59, 'carrier_id'] = 999
    bad.loc[60:79, 'promised_delivery_at'] = bad.loc[60:79, 'dispatch_at'] - pd.Timedelta(days=1)
    bad.loc[80:99, 'actual_delivery_at'] = bad.loc[80:99, 'dispatch_at'] - pd.Timedelta(days=1)
    raw = pd.concat([shipments, bad], ignore_index=True)
    tables = {'carriers': carriers, 'ports': ports, 'routes': routes, 'shipments': raw, 'shipment_events': event_df}
    manifest = {'synthetic': True, 'seed': seed, 'as_of_utc': AS_OF, 'valid_shipments': n,
                'deliberate_invalid_rows': 100, 'files': {}}
    for name, frame in tables.items():
        path = ROOT / 'data/raw' / f'{name}.csv'
        frame.to_csv(path, index=False, date_format='%Y-%m-%d %H:%M:%S')
        manifest['files'][name] = {'rows': len(frame), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (ROOT / 'data/raw/manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rows', type=int, default=20000)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    print(json.dumps(generate(args.rows, args.seed), indent=2))
