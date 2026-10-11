import argparse
import json
import logging
from .config import ROOT, prepare_dirs
from .generate_data import generate
from .etl import run as run_etl
from .analytics import run as run_analytics
from .model import train
from .dashboard import build


def main():
    p = argparse.ArgumentParser(description='Generate, validate, load, analyze and optionally train.')
    p.add_argument('--generate', action='store_true', help='Regenerate raw synthetic CSVs with fixed seed')
    p.add_argument('--train', action='store_true', help='Train/evaluate models; separate from routine refresh')
    p.add_argument('--rows', type=int, default=20000)
    args = p.parse_args()
    prepare_dirs()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(ROOT/'logs/pipeline.log')])
    if args.generate or not (ROOT/'data/raw/manifest.json').exists():
        logging.info('Generating synthetic dataset')
        generate(args.rows)
    logging.info('Validating and loading relational database')
    quality = run_etl()
    logging.info('Accepted %s shipments; quarantined %s', quality['accepted_shipments'], quality['rejected_shipments'])
    logging.info('Exporting analytics and charts')
    run_analytics()
    if args.train:
        logging.info('Training and evaluating models')
        report = train()
        logging.info('Selected %s; test ROC-AUC %.3f', report['selected_model'], report['test_metrics']['roc_auc'])
    logging.info('Building offline interactive report')
    build()
    logging.info('Complete. Open reports/dashboard.html and README.md')


if __name__ == '__main__':
    main()
