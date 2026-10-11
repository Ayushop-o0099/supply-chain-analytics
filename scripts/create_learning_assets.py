"""Create the notebook and an example inference CSV from generated data."""
import json
import importlib.metadata
import pandas as pd
from src.config import ROOT

(ROOT/'notebooks').mkdir(exist_ok=True)
def md(text):
    return {'cell_type':'markdown','metadata':{},'source':text.splitlines(keepends=True)}
def code(text):
    return {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[], 'source':text.splitlines(keepends=True)}
cells = [
    md('# Shipment analytics walkthrough\nSynthetic portfolio dataset, snapshot 1 January 2026 UTC. Run the pipeline first. This notebook reads the generated exports and does not mutate the database.'),
    code("from pathlib import Path\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport json\nROOT = Path.cwd() if (Path.cwd() / 'src').exists() else Path.cwd().parent\ndf = pd.read_csv(ROOT / 'data/processed/shipment_performance.csv', parse_dates=['dispatch_at','promised_delivery_at','actual_delivery_at'])\ndf.head()"),
    md('## Data quality\nUndelivered shipments legitimately have missing outcomes. Inspect rejection reasons separately.'),
    code("df.info()\nprint(df.isna().sum())\nquality = json.loads((ROOT / 'reports/data_quality.json').read_text())\nquality"),
    md('## Calculate KPIs\nThe denominator is delivered shipments; unresolved shipments are not on-time.'),
    code("delivered = df[df.status.eq('Delivered')]\n{'shipments': len(df), 'delivered': len(delivered), 'on_time_rate': 1-delivered.is_delayed.mean(), 'mean_delay_hours': delivered.delay_hours.mean()}"),
    md('## Carrier comparisons\nShow volumes and confidence intervals. Route and service mix can confound these unadjusted rates.'),
    code("carriers = pd.read_csv(ROOT / 'data/processed/carrier_performance.csv')\ncarriers.sort_values('delay_rate')"),
    code("carriers.sort_values('delay_rate').plot.barh(x='carrier_name', y='delay_rate', legend=False, title='Synthetic carrier delay rates')\nplt.xlabel('Fraction of delivered shipments delayed')\nplt.show()"),
    md('## Seasonal patterns\nGroup by dispatch month. Recent cohorts are incomplete.'),
    code("monthly = delivered.assign(month=delivered.dispatch_at.dt.to_period('M')).groupby('month').is_delayed.mean()\n(1-monthly).plot(marker='o', figsize=(12,4), title='On-time delivery rate by dispatch cohort')\nplt.show()"),
    md('## Route and service comparisons'),
    code("delivered.groupby(['route_id','service_level','carrier_name']).agg(delivered=('shipment_id','size'), delay_rate=('is_delayed','mean')).query('delivered >= 30').sort_values(['route_id','service_level','delay_rate']).head(20)"),
    md('## Model evaluation\nRead validation candidates separately from the one held-out test result. Synthetic results do not establish real-world accuracy.'),
    code("metrics = json.loads((ROOT / 'reports/model_metrics.json').read_text())\nprint('Selected model:', metrics['selected_model'])\nprint('Temporal split sizes:', metrics['split_rows'])\npd.DataFrame(metrics['validation_candidates']).T"),
    code("metrics['test_metrics']"),
    md('## Next exercise\nExplain which columns would leak future information at dispatch. Then inspect `src/model.py` and the temporal split tests. Assemble the native Power BI report using `powerbi/BUILD_GUIDE.md`.'),
]
notebook = {'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                                    'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
for i, cell in enumerate(cells):
    cell['id'] = f'cell-{i:03d}'
(ROOT/'notebooks/01_eda.ipynb').write_text(json.dumps(notebook,indent=2),encoding='utf-8')
df = pd.read_csv(ROOT/'data/processed/shipment_performance.csv')
cols = ['shipment_id','carrier_id','route_id','service_level','weight_kg','distance_km','dispatch_at','promised_delivery_at']
sample = df[df.status.eq('In Transit')].head(5)[cols].copy()
sample.to_csv(ROOT/'data/sample_new_shipments.csv',index=False)
versions = {p:importlib.metadata.version(p) for p in ['pandas','numpy','SQLAlchemy','PyMySQL','scikit-learn','matplotlib','seaborn','joblib','python-dotenv','pytest']}
(ROOT/'requirements-tested.txt').write_text('\n'.join(f'{k}=={v}' for k,v in versions.items())+'\n')
