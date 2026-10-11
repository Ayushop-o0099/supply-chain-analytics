import json
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import text
from .config import ROOT
from .database import engine_for


def load_performance(url=None):
    engine = engine_for(url)
    with engine.connect() as conn:
        frame = pd.read_sql(text('SELECT * FROM vw_shipment_performance'), conn)
    engine.dispose()
    for col in ['dispatch_at', 'promised_delivery_at', 'actual_delivery_at']:
        frame[col] = pd.to_datetime(frame[col])
    return frame


def summarize(df, as_of):
    delivered = df[df.status.eq('Delivered')]
    return {'total_shipments': len(df), 'delivered_shipments': len(delivered),
            'delayed_shipments': int(delivered.is_delayed.sum()),
            'on_time_rate': float(1-delivered.is_delayed.mean()) if len(delivered) else None,
            'mean_delay_hours_delivered': float(delivered.delay_hours.mean()) if len(delivered) else None,
            'overdue_open': int((df.status.eq('In Transit') & df.promised_delivery_at.lt(pd.Timestamp(as_of))).sum()),
            'cancelled_shipments': int(df.status.eq('Cancelled').sum()),
            'total_shipping_cost_usd': float(df.shipping_cost_usd.sum()),
            'as_of_utc': as_of, 'synthetic': True}


def grouped_performance(df, keys):
    return df[df.status.eq('Delivered')].groupby(keys, observed=True).agg(
        delivered_shipments=('shipment_id', 'size'), delayed_shipments=('is_delayed', 'sum'),
        delay_rate=('is_delayed', 'mean'), mean_delay_hours=('delay_hours', 'mean'),
        median_transit_hours=('transit_hours', 'median'),
        p90_delay_hours=('delay_hours', lambda s: s.quantile(.9))).reset_index()


def wilson_interval(count, n):
    z = 1.96
    p = count/n
    center = (p + z*z/(2*n))/(1+z*z/n)
    width = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return center-width, center+width


def run(url=None):
    df = load_performance(url)
    as_of = json.loads((ROOT / 'data/raw/manifest.json').read_text())['as_of_utc']
    df['dispatch_date'] = df.dispatch_at.dt.strftime('%Y-%m-%d')
    df['dispatch_month'] = df.dispatch_at.dt.strftime('%Y-%m')
    df['is_overdue_open'] = (df.status.eq('In Transit') & df.promised_delivery_at.lt(pd.Timestamp(as_of))).astype(int)
    kpis = summarize(df, as_of)
    carrier = grouped_performance(df, ['carrier_id', 'carrier_name'])
    bounds = [wilson_interval(row.delayed_shipments, row.delivered_shipments) for row in carrier.itertuples()]
    carrier['delay_rate_ci95_low'], carrier['delay_rate_ci95_high'] = zip(*bounds)
    routes = grouped_performance(df, ['route_id', 'origin_port', 'destination_port'])
    monthly = grouped_performance(df, ['dispatch_month'])
    engine = engine_for(url)
    with engine.connect() as conn:
        events = pd.read_sql(text('SELECT * FROM shipment_events'), conn)
    engine.dispose()
    paired = events[events.event_type.isin(['Port Arrived', 'Port Departed'])].pivot_table(
        index=['shipment_id', 'port_id'], columns='event_type', values='event_at', aggfunc='first').reset_index()
    for col in ['Port Arrived', 'Port Departed']:
        if col not in paired:
            paired[col] = pd.NaT
        paired[col] = pd.to_datetime(paired[col])
    paired['dwell_hours'] = (paired['Port Departed']-paired['Port Arrived']).dt.total_seconds()/3600
    dwell = paired.dropna(subset=['dwell_hours']).groupby('port_id').agg(
        completed_port_visits=('shipment_id', 'size'), mean_dwell_hours=('dwell_hours', 'mean')).reset_index()
    ports = pd.read_csv(ROOT/'data/raw/ports.csv')
    dwell = dwell.merge(ports[['port_id', 'port_name']], on='port_id', validate='one_to_one')
    calendar = pd.DataFrame({'date': pd.date_range(df.dispatch_at.min().normalize(), df.dispatch_at.max().normalize())})
    calendar['year'] = calendar.date.dt.year
    calendar['month_number'] = calendar.date.dt.month
    calendar['year_month'] = calendar.date.dt.strftime('%Y-%m')
    calendar['quarter'] = calendar.date.dt.quarter
    for name, frame in {'shipment_performance': df, 'carrier_performance': carrier, 'route_performance': routes,
                        'monthly_performance': monthly, 'port_dwell': dwell, 'dim_date': calendar}.items():
        frame.to_csv(ROOT/'data/processed'/f'{name}.csv', index=False)
    (ROOT/'reports/kpis.json').write_text(json.dumps(kpis, indent=2))
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout='constrained')
    order = carrier.sort_values('delay_rate')
    axes[0, 0].barh(order.carrier_name, order.delay_rate*100, color='#198b87')
    axes[0, 0].set(title='Carrier delay rate', xlabel='% of delivered shipments')
    axes[0, 1].plot(monthly.dispatch_month, (1-monthly.delay_rate)*100, color='#198b87', marker='o')
    axes[0, 1].tick_params(axis='x', rotation=60)
    axes[0, 1].set(title='On-time rate by dispatch month', ylabel='% of delivered shipments')
    delivered = df[df.status.eq('Delivered')]
    axes[1, 0].hist(delivered.delay_hours[delivered.is_delayed.eq(1)], bins=35, color='#de9141')
    axes[1, 0].set(title='Delay duration among late deliveries', xlabel='Hours late', ylabel='Shipments')
    axes[1, 1].barh(dwell.port_name, dwell.mean_dwell_hours, color='#4865ad')
    axes[1, 1].set(title='Completed destination-port visits', xlabel='Mean dwell hours')
    fig.suptitle('Shipment analytics | Synthetic portfolio dataset', fontsize=18)
    fig.savefig(ROOT/'reports/eda.png', dpi=150)
    plt.close(fig)
    best, worst = carrier.loc[carrier.delay_rate.idxmin()], carrier.loc[carrier.delay_rate.idxmax()]
    findings = f'''# Exploratory analysis\n\nSynthetic data, as of {as_of} UTC. These patterns reflect the generator.\n\n- {kpis['delivered_shipments']:,} of {len(df):,} shipments are delivered.\n- On-time rate is {kpis['on_time_rate']:.1%} among completed deliveries.\n- {best.carrier_name} has the lowest observed delay rate ({best.delay_rate:.1%}).\n- {worst.carrier_name} has the highest observed delay rate ({worst.delay_rate:.1%}).\n- Median transit time is {delivered.transit_hours.median():.1f} hours.\n- The 90th percentile delay across delivered shipments is {delivered.delay_hours.quantile(.9):.1f} hours.\n- {kpis['overdue_open']} open shipments are overdue at the fixed cutoff.\n\nCarrier CSV includes 95% Wilson intervals. Rates are descriptive; route mix and service levels confound raw comparisons. Use SQL query 8 to compare carriers within routes. Recent dispatch cohorts are incomplete, so their delivered-only rates may be optimistic. Port dwell uses only visits with both arrival and departure events.\n'''
    (ROOT/'reports/eda_findings.md').write_text(findings, encoding='utf-8')
    return kpis


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
