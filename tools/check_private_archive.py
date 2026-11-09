"""Privately acquired archive checksum only; never upload/download photos."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())];sys.path.insert(0,str(ROOT/'classifiers/common'))
from audit_dataset import EXPECTED_SHA256
if __name__=='__main__':
 p=ROOT/'data/raw/TWI_1_1.zip';actual=hashlib.sha256(p.read_bytes()).hexdigest()
 if actual!=EXPECTED_SHA256:raise SystemExit('Private archive identity mismatch; owner dataset protocol review required')
 (ROOT/'data/raw.sha256').write_text(actual+'\n')
 print('Private archive verified; local checksum receipt written; no upload')
