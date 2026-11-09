"""Generate the actual13 supervised training-input contract offline, privately."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse,base64,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())];sys.path.insert(0,str(ROOT/'classifiers/common'))
from preprocessing import canonical_image
FACTS=json.loads((ROOT/'classifiers/common/results/gpt-training.json').read_text())
def prepare(out,root=ROOT):
 root=Path(root)
 if not __debug__:raise RuntimeError('Assertions must be enabled')
 out=Path(out)
 if out.exists():raise FileExistsError('Existing training output; never overwrite blindly')
 manifest=json.loads((root/'artifacts/manifest.json').read_text());by={r['index']:r for r in manifest}
 ids=FACTS['actual_training_indices'];ev=set(FACTS['evaluation_indices']);assert len(ids)==13 and not set(ids)&ev
 split=json.loads((root/'artifacts/classifier/splits.json').read_text());groups={r['index']:r['group'] for r in split['rows']};groups.update({i:'review-'+str(i) for i in split['review_indices']});assert not {groups[i] for i in ids}&{groups[i] for i in ev}
 records=[];counts={}
 for i in ids:
  r=by[i];raw=(root/'data/extracted'/r['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256']
  data,_=canonical_image(raw);counts[r['label']]=counts.get(r['label'],0)+1
  records.append(dict(messages=[dict(role='system',content=FACTS['prompt']),dict(role='user',content=[dict(type='image_url',image_url=dict(url='data:image/jpeg;base64,'+base64.b64encode(data).decode(),detail='high'))]),dict(role='assistant',content=json.dumps(dict(visual_condition=r['label']),separators=(',',':')))]))
 assert counts==FACTS['actual_training_counts']
 out.mkdir(parents=True,mode=0o700);os.chmod(out,0o700)
 payload=('\n'.join(json.dumps(r,separators=(',',':')) for r in records)+'\n').encode();p=out/'training.jsonl';p.write_bytes(payload);os.chmod(p,0o600)
 receipt=dict(examples=13,counts=counts,sha256=hashlib.sha256(payload).hexdigest(),source_historical_payload_sha256=FACTS['training_payload_sha256'],qualification='Same source inputs/schema; JSON serialization may differ from historical payload; no upload/fine-tune')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=prepare(a.out);print('Prepared13private training examples; no network/training')
