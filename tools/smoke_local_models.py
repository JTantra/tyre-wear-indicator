"""Real synthetic-image3-model parity against trusted originals, no photo rescoring."""
import argparse,hashlib,json,math,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def run(original):
 from PIL import Image,ImageDraw
 from classifiers.common.paths import method_module
 out=ROOT/'.cache';out.mkdir(exist_ok=True);image=out/'synthetic-model-smoke.png'
 im=Image.new('RGB',(320,240),(95,95,95));draw=ImageDraw.Draw(im)
 for x in range(0,320,20):draw.line((x,0,x,240),fill=(30,30,30),width=6)
 im.save(image)
 old=Path(original);cache=Path.home()/'.cache/torch/hub/checkpoints'
 paths={'resnet18':cache/'resnet18-f37072fd.pth','mobilenet':cache/'mobilenet_v3_large-5c1a4163.pth','clip':old/'artifacts/custom-v2/weights/clip'}
 scripts={'resnet18':'scripts/predict_classifier.py','mobilenet':'scripts/predict_custom.py','clip':'app/local_worker.py'}
 results={};env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 for method in paths:
  before=json.loads(subprocess.check_output([sys.executable,str(old/scripts[method]),str(image)],cwd=old,env=env,text=True))
  after=method_module(method,'inference').predict(image,backbone=paths[method])
  bp=before.get('diagnostic_binary_prediction',before.get('binary_prediction'))
  assert bp==after['diagnostic_binary_prediction'],method+' binary differs'
  key='p_good' if method=='resnet18' else 'decision_margin'
  assert math.isclose(before[key],after[key],rel_tol=1e-12,abs_tol=1e-12),method+' numeric differs'
  # Exercise actual new CLI too, from arbitrary CWD.
  cli=json.loads(subprocess.check_output([sys.executable,str(ROOT/'classifiers'/method/'test.py'),'--image',str(image),'--backbone',str(paths[method])],cwd=out,env=env,text=True))
  assert cli==after
  results[method]=dict(before=before[key],after=after[key],diagnostic_binary_prediction=bp,absolute_error=abs(before[key]-after[key]),cli_arbitrary_cwd_equal=True)
 receipt=dict(qualification='Synthetic generated image, genuine3backbones and trusted final heads; engineering parity, NOT benchmark/newscore/private-photo inference',image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),models=results,cloud_calls=False,training=False)
 (out/'local-smoke.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--trusted-original-root',type=Path,required=True,help='Read-only authorized original local heads/backbones; no downloads');a=p.parse_args();print(json.dumps(run(a.trusted_original_root),indent=2))
