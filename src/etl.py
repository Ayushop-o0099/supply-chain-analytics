import json
import uuid
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import insert, update
from .config import ROOT, prepare_dirs
from .database import engine_for, metadata, etl_runs, upsert, create_views
from .validation import validate_shipments, validate_dimensions, validate_events


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run(url=None):
    prepare_dirs()
    manifest = json.loads((ROOT / 'data/raw/manifest.json').read_text())
    tables = {name: pd.read_csv(ROOT / 'data/raw' / f'{name}.csv') for name in
              ['carriers', 'ports', 'routes', 'shipments', 'shipment_events']}
    engine = engine_for(url)
    metadata.create_all(engine)
    run_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(insert(etl_runs).values(run_id=run_id, started_at=utc_now(), status='Running'))
    try:
        validate_dimensions(tables)
        valid, rejected = validate_shipments(tables['shipments'], tables['carriers'], tables['routes'], manifest['as_of_utc'])
        valid_events, rejected_events = validate_events(tables['shipment_events'], valid, tables['ports'], manifest['as_of_utc'])
        rejected.to_csv(ROOT / 'data/rejected/shipments.csv', index=False)
        rejected_events.to_csv(ROOT / 'data/rejected/shipment_events.csv', index=False)
        accepted = {**tables, 'shipments': valid, 'shipment_events': valid_events}
        with engine.begin() as conn:
            for name in ['carriers', 'ports', 'routes', 'shipments', 'shipment_events']:
                upsert(conn, name, accepted[name])
        # MySQL DDL implicitly commits: view refresh is deliberately outside the data transaction.
        with engine.begin() as conn:
            create_views(conn)
        quality = {'run_id': run_id, 'input_shipments': len(tables['shipments']),
                   'accepted_shipments': len(valid), 'rejected_shipments': len(rejected),
                   'accepted_events': len(valid_events), 'rejected_events': len(rejected_events),
                   'as_of_utc': manifest['as_of_utc'], 'synthetic': True,
                   'rejection_reasons': rejected.rejection_reason.value_counts().to_dict()}
        (ROOT / 'reports/data_quality.json').write_text(json.dumps(quality, indent=2))
        with engine.begin() as conn:
            conn.execute(update(etl_runs).where(etl_runs.c.run_id == run_id).values(
                status='Success', completed_at=utc_now(), input_rows=len(tables['shipments']),
                accepted_rows=len(valid), rejected_rows=len(rejected), message='Idempotent upsert completed'))
        return quality
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(update(etl_runs).where(etl_runs.c.run_id == run_id).values(
                status='Failed', completed_at=utc_now(), message=type(exc).__name__))
        raise
    finally:
        engine.dispose()


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
