"""Build a self-contained HTML report from the curated shipment export."""
import json
import pandas as pd
from .config import ROOT


def build():
    df = pd.read_csv(ROOT/'data/processed/shipment_performance.csv')
    cols = ['shipment_id', 'carrier_name', 'origin_port', 'destination_port', 'service_level',
            'dispatch_month', 'status', 'is_delayed', 'delay_hours', 'is_overdue_open', 'shipping_cost_usd']
    payload = df[cols].to_json(orient='records')
    template = (ROOT/'dashboards/dashboard_template.html').read_text(encoding='utf-8')
    as_of = json.loads((ROOT/'data/raw/manifest.json').read_text())['as_of_utc']
    html = template.replace('__SHIPMENT_DATA__', payload.replace('</', '<\\/')).replace('__AS_OF__', as_of)
    (ROOT/'reports/dashboard.html').write_text(html, encoding='utf-8')


if __name__ == '__main__':
    build()
