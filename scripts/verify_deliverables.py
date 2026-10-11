"""Read-only integration checks after the complete pipeline run."""
import ast
import hashlib
import json
import contextlib
import io
import matplotlib
matplotlib.use('Agg')
import pandas as pd
from sqlalchemy import text
from src.config import ROOT
from src.database import engine_for

manifest = json.loads((ROOT/'data/raw/manifest.json').read_text())
for name, info in manifest['files'].items():
    path = ROOT/'data/raw'/f'{name}.csv'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']
    assert len(pd.read_csv(path)) == info['rows']
engine = engine_for()
with engine.connect() as conn:
    counts = {name: conn.execute(text(f'SELECT COUNT(*) FROM {name}')).scalar() for name in ['shipments','shipment_events']}
    assert counts['shipments'] == manifest['valid_shipments']
    assert counts['shipment_events'] == manifest['files']['shipment_events']['rows']
    sql_kpi = conn.execute(text("SELECT COUNT(*),SUM(is_delayed),AVG(1-is_delayed) FROM vw_shipment_performance WHERE status='Delivered'")).one()
engine.dispose()
kpis = json.loads((ROOT/'reports/kpis.json').read_text())
assert sql_kpi[0] == kpis['delivered_shipments']
assert sql_kpi[1] == kpis['delayed_shipments']
assert abs(sql_kpi[2]-kpis['on_time_rate']) < 1e-10
data = pd.read_csv(ROOT/'data/processed/shipment_performance.csv')
assert len(data) == counts['shipments']
assert data.shipment_id.is_unique
assert data.loc[data.status.ne('Delivered'), 'is_delayed'].isna().all()
namespace = {}
notebook = json.loads((ROOT/'notebooks/01_eda.ipynb').read_text())
with contextlib.redirect_stdout(io.StringIO()):
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            ast.parse(source)
            exec(compile(source, '01_eda.ipynb', 'exec'), namespace)
print(json.dumps({'source_hashes':'pass','database_counts':counts,'sql_python_kpis':'match',
                  'notebook_code_cells':'executed successfully'},indent=2))
