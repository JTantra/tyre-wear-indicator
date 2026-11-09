"""Explicit pinned public-only downloader, verifies before atomic replacement."""
import hashlib,json,urllib.request
from pathlib import Path
def verify(path,record):
 path=Path(path)
 if not path.is_file():raise FileNotFoundError('Public backbone missing; use method weights/fetch.py explicitly or --backbone')
 if path.stat().st_size!=record['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Pinned checkpoint hash/size mismatch')
 return path
def fetch(weights):
 weights=Path(weights)
 for row in json.loads((weights/'pretrained.json').read_text()):
  path=weights/row['file'];path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():verify(path,row);continue
  tmp=path.with_name(path.name+'.part')
  try:
   urllib.request.urlretrieve(row['url'],tmp);verify(tmp,row);tmp.replace(path)
  finally:tmp.unlink(missing_ok=True)
 return 'Pinned public checkpoints ready; no dataset upload.'
