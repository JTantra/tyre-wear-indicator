"""Published-method inference integrity wrapper; no downloads or code execution."""
import json
from pathlib import Path
def verify(name,folder):
 from classifiers.common.foundation_next import digest
 root=Path(__file__).resolve().parents[2];pins=json.loads((root/'classifiers'/name/'weights/pretrained.json').read_text())
 if any(p.get('sha256') is None for p in pins):raise RuntimeError('Model unrun/access-blocked: no approved checkpoint digest. Owner must independently obtain access and a new verified benchmark pin.')
 for pin in pins:
  p=Path(folder)/pin['file']
  if not p.is_file() or p.stat().st_size!=pin['bytes'] or digest(p)!=pin['sha256']:raise ValueError('Pinned public weight/config integrity mismatch')
 return True
