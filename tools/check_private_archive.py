"""Privately acquired archive checksum only; never upload/download photos."""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audit_dataset import EXPECTED_SHA256
if __name__=='__main__':
 p=ROOT/'data/raw/TWI_1_1.zip';actual=hashlib.sha256(p.read_bytes()).hexdigest()
 if actual!=EXPECTED_SHA256:raise SystemExit('Private archive identity mismatch; owner dataset protocol review required')
 (ROOT/'data/raw.sha256').write_text(actual+'\n')
 print('Private archive verified; local checksum receipt written; no upload')
