"""Bundle deliverables without credentials, venv, caches, or machine-specific DB files."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from src.config import ROOT

folders = ['src','sql','data/raw','data/processed','data/rejected','models','reports',
           'dashboards','powerbi','docs','notebooks','tests','scripts']
files = ['README.md','requirements.txt','requirements-tested.txt','.env.example','.gitignore',
         'pytest.ini','data/sample_new_shipments.csv']
destination = ROOT/'SupplyChainAnalytics.zip'
with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
    selected = [ROOT/name for name in files]
    for folder in folders:
        selected.extend(path for path in (ROOT/folder).rglob('*') if path.is_file()
                        and '__pycache__' not in path.parts and path.suffix != '.pyc')
    for path in sorted(set(selected)):
        archive.write(path, 'SupplyChainAnalytics/'+path.relative_to(ROOT).as_posix())
print(f'Packaged {len(selected)} files into {destination.name}')
