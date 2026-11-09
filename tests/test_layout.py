"""Migration behavior, unchanged evidence and privacy regressions; no cloud."""
import ast,hashlib,importlib,json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
METHODS=['resnet18','mobilenet','clip','luna-responses','luna-decisions','gpt41-finetuned','azure-automl']
class LayoutTests(unittest.TestCase):
 def test_all14_help_from_root_and_arbitrarycwd_without_heavy_imports(self):
  blocker="import builtins,runpy,sys; orig=builtins.__import__; denied={'torch','torchvision','numpy','PIL','sklearn','requests','transformers','azure','joblib'}; builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(RuntimeError('heavy import on help: '+name)) if name.split('.')[0] in denied else orig(name,*a,**k); sys.argv=[sys.argv[1],'--help']; runpy.run_path(sys.argv[0],run_name='__main__')"
  for method in METHODS:
   for name in ['train.py','test.py']:
    script=ROOT/'classifiers'/method/name
    for cwd in [ROOT,ROOT/'.cache']:
     with self.subTest(method=method,script=name,cwd=str(cwd)):
      p=subprocess.run([sys.executable,'-c',blocker,str(script)],cwd=cwd,capture_output=True,text=True)
      self.assertEqual(p.returncode,0,p.stderr);self.assertIn('usage:',p.stdout)
 def test_per_method_frozen_views_equal_shared_original_evidence(self):
  rows=json.loads((ROOT/'classifiers/common/results/per-image.json').read_text())
  for method in METHODS[:-1]:
   actual=json.loads((ROOT/'classifiers'/method/'results/per-image.json').read_text())
   self.assertEqual(actual,[r for r in rows if r['method']==method])
 def test_six_benchmark_commands_match_exact_counts(self):
  for method,correct,fg in zip(METHODS[:6],[4,4,7,8,3,9],[1,1,2,0,3,0]):
   p=subprocess.run([sys.executable,str(ROOT/'classifiers'/method/'test.py'),'--benchmark'],cwd=ROOT/'.cache',capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);value=json.loads(p.stdout)
   self.assertEqual(value['shared9']['n'],9);self.assertEqual(value['shared9']['correct'],correct);self.assertEqual(value['shared9']['bad_false_good'],fg)
 def test_numeric_head_schema_and_exact_hashes(self):
  from classifiers.common.numeric_head import load
  from tools.check_publication import content_rules
  owned=json.loads((ROOT/'classifiers/common/owned-heads.json').read_text())
  for method,row in owned.items():
   p=ROOT/row['published_path'];load(p)
   self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['published_sha256'])
   self.assertEqual(content_rules(row['published_path'],p.read_bytes()),[])
   changed=p.read_bytes()+b' ';self.assertIn('unapproved_owned_head_content',content_rules(row['published_path'],changed))
 def test_weights_policy_rejects_even_text_labels_and_nonwhitelisted_numeric_blob(self):
  from tools.check_publication import content_rules
  self.assertIn('unapproved_weights_path',content_rules('classifiers/clip/weights/samples.json',b'{"labels":[0,1]}'))
  self.assertIn('private_or_large_artifact_path',content_rules('classifiers/clip/weights/extra.joblib',b'not even binary'))
 def test_non_executable_head_rejects_metadata_and_raw_rows(self):
  from classifiers.common.numeric_head import validate
  head=dict(format='twi-numeric-logistic-v1',mean=[0.],scale=[1.],coef=[2.],intercept=0.)
  validate(head)
  for field in ['samples','labels','paths','features','provider_job_id']:
   with self.assertRaises(ValueError):validate(dict(head,**{field:[]}))
 def test_train_does_not_monkeypatch_or_call_run_all(self):
  for method in METHODS[:3]:
   s=(ROOT/'classifiers'/method/'train.py').read_text();self.assertNotIn('REPRESENTATIONS=',s);self.assertNotIn('experiment',s)
  s=(ROOT/'classifiers/common/training.py').read_text();self.assertNotIn('.run(',s);self.assertIn("method_module(method,'inference')",s)
 def test_luna_not_fake_training(self):
  for method in METHODS[3:5]:
   p=subprocess.run([sys.executable,str(ROOT/'classifiers'/method/'train.py')],cwd=ROOT/'.cache',capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);self.assertIn('Not trainable',p.stdout)
 def test_missing_cloud_capabilities_fail_before_network(self):
  for method in METHODS[3:6]:
   m=importlib.import_module('classifiers.'+method+'.inference')
   with self.assertRaises(PermissionError):m.predict(Path('missing.png'),execute=False)
 def test_automl_unrun_contract_no_fake_metric(self):
  from classifiers.common.paths import method_module
  value=method_module('azure-automl','contracts').validate();self.assertEqual([value['train'],value['validation'],value['evaluation']],[10,3,9]);self.assertIsNone(value['score'])
  with self.assertRaises(RuntimeError):method_module('azure-automl','inference').predict(Path('missing.png'))
 def test_local_head_default_and_training_output_ownership(self):
  s=(ROOT/'classifiers/common/test_cli.py').read_text();self.assertIn("ROOT/'classifiers'/method/'weights'",s)
  s=(ROOT/'classifiers/common/training.py').read_text();self.assertIn("out/'head.json'",s);self.assertIn('FileExistsError',s)
 def test_root_layout_does_not_retain_displaced_roots(self):
  for name in ['methods','app','scripts','results','third_party','config']:self.assertFalse((ROOT/name).exists(),name)
 def test_14_cli_presence_and_method_owned_logic(self):
  for method in METHODS:
   for name in ['train.py','test.py','inference.py','README.md','weights/README.md','results/summary.json']:self.assertTrue((ROOT/'classifiers'/method/name).is_file(),method+'/'+name)
 def test_publication_manifest_baseline_and_parameter_disclosures(self):
  m=json.loads((ROOT/'export-manifest.json').read_text());self.assertEqual(m['migration']['baseline_commit'],'38f5d37d14aafa494fb944a82f14c9ea2d1bf1d4');self.assertEqual(len(m['migration']['baseline_files']),91);self.assertEqual(m['migration']['head_hyperparameters_changed'],False)

 def test_numeric_head_float32_casts_match_archived_scaler(self):
  import numpy as np
  from sklearn.preprocessing import StandardScaler
  from classifiers.common.numeric_head import decision
  value=dict(format='twi-numeric-logistic-v1',mean=[.123456789,.987654321],scale=[.333333333,.777777777],coef=[1.23456789,-.3456789],intercept=.0123)
  scaler=StandardScaler();scaler.mean_=np.array(value['mean']);scaler.scale_=np.array(value['scale']);scaler.var_=scaler.scale_**2;scaler.n_features_in_=2;scaler.n_samples_seen_=22
  for dtype in [np.float32,np.float64]:
   x=np.array([[.27,1.123456789]],dtype=dtype)
   expected=scaler.transform(x)@np.array(value['coef'])+value['intercept'];np.testing.assert_array_equal(decision(value,x),expected)

 def test_documented_dashboard_subprocess_frontend_api_and_auth_readonly(self):
  import socket,time,urllib.request,urllib.error,tempfile
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as td:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
   env=dict(os.environ,TYRE_FEEDBACK_ROOT=td+'/feedback',TYRE_UPLOAD_SCRATCH=td,PYTHONDONTWRITEBYTECODE='1')
   proc=subprocess.Popen([sys.executable,'-m','dashboard.backend.server','--bind','127.0.0.1','--port',str(port),'--read-only'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   base='http://127.0.0.1:'+str(port)
   try:
    for _ in range(100):
     if proc.poll() is not None:self.fail('Dashboard failed startup: '+proc.communicate()[1])
     try:
      with urllib.request.urlopen(base+'/api/ready',timeout=1) as r:self.assertTrue(json.load(r)['ready'])
      break
     except (urllib.error.URLError,TimeoutError):time.sleep(.05)
    else:self.fail('Dashboard readiness timeout')
    for path,needle in [('/',b'<html'),('/dashboard.js',b'api/'),('/style.css',b'{')]:
     with urllib.request.urlopen(base+path,timeout=3) as r:self.assertEqual(r.status,200);self.assertIn(needle,r.read())
    with urllib.request.urlopen(base+'/api/benchmarks') as r:self.assertEqual(json.load(r)['method_count'],7)
    with urllib.request.urlopen(base+'/api/per-images') as r:self.assertEqual(len(json.load(r)['rows']),128)
    with urllib.request.urlopen(base+'/api/session') as r:self.assertEqual(len(json.load(r)['csrf_token']),43);self.assertIn('HttpOnly',r.headers['Set-Cookie'])
    for path in ['/api/feedback','/api/jobs/'+('a'*32)]:
     with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+path)
     self.assertEqual(e.exception.code,404)
    req=urllib.request.Request(base+'/api/infer',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
    self.assertEqual(e.exception.code,403);self.assertIn(b'Read-only',e.exception.read())
   finally:
    proc.terminate()
    try:proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.communicate()
