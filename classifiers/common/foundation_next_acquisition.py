"""Explicit pinned public-weight acquisition; never accepts gated terms or retries."""
import argparse,json,hashlib,time
from pathlib import Path
def main(name):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 from classifiers.common.foundation_next import SPECS
 spec=SPECS[name]
 if not a.execute:print(json.dumps(dict(model=spec,action='dry-run; --execute downloads pinned public weights only'),indent=2));return
 from huggingface_hub import hf_hub_download
 from classifiers.common.foundation_next import digest
 # Caller deliberately chooses an external private/cache folder; never overwrite receipts.
 a.out.mkdir(parents=True,exist_ok=False);records={};started=time.perf_counter()
 try:
  # DINO gate encountered once on weights before any other gated file.
  files=[spec['checkpoint'],'config.json','preprocessor_config.json','README.md'] if name=='dinov3' else ['README.md','config.json','preprocessor_config.json',spec['checkpoint']]
  for filename in files:
   t=time.perf_counter();source=Path(hf_hub_download(spec['repo'],filename,revision=spec['revision'],cache_dir=a.out/'.hf-cache'))
   (a.out/filename).symlink_to(source.resolve())
   records[filename]=dict(sha256=digest(source),bytes=source.stat().st_size,seconds=time.perf_counter()-t)
   if name=='siglip2' and filename=='README.md' and 'license: apache-2.0' not in source.read_text():raise ValueError('Pinned card license mismatch')
  status=dict(status='available',repo=spec['repo'],revision=spec['revision'],files=records,seconds=time.perf_counter()-started)
 except Exception as e:
  response=getattr(e,'response',None)
  status=dict(status='access_blocked' if name=='dinov3' else 'download_failed',exception=type(e).__name__,http_status=getattr(response,'status_code',None),response_text=response.text if response is not None else '',repo=spec['repo'],revision=spec['revision'],files=records)
  (a.out/(name+'-access.json')).write_text(json.dumps(status,indent=2)+'\n')
  print(json.dumps(status,indent=2));raise SystemExit(2)
 (a.out/(name+'-access.json')).write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status,indent=2))
