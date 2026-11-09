"""Saved full-data engineering inference, never replay historical CV predictions."""
import io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
def main():
 import torch,joblib
 from PIL import Image
 import custom_refinement_v2 as v2
 torch.set_num_threads(4)
 out=ROOT/'artifacts/custom-v2';config=json.loads((out/'deployment_config.json').read_text())
 name,size=config['candidate'].split('_')
 summary=json.loads((out/'summary.json').read_text())
 if v2.digest(out/'head.joblib')!=summary['head_sha256']:raise ValueError('Saved head integrity failed')
 for filename,record in summary['provenance'][name]['files'].items():
  if v2.digest(out/'weights'/name/filename)!=record['sha256']:raise ValueError('Saved model integrity failed')
 model=v2.backbone(out,name);head=joblib.load(out/'head.joblib')
 data,_=v2.canonical_image(Path(sys.argv[1]).read_bytes())
 with Image.open(io.BytesIO(data)) as im:x=v2.extract(model,[v2.tensors_for(im.convert('RGB'),name,int(size))],name)
 pred=int(head.predict(x)[0]);margin=float(head.decision_function(x)[0])
 print(json.dumps({'diagnostic_binary_prediction':'good' if pred else 'bad','decision_margin':margin,'candidate':config['candidate']}))
if __name__=='__main__':main()
