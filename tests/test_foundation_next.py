"""Synthetic unit contracts + real anonymous result arithmetic; no private-photo inference."""
import copy,hashlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FoundationNextTests(unittest.TestCase):
 def test_exact_pins_and_fixed_pooling(self):
  from classifiers.common.foundation_next import SPECS
  self.assertEqual(SPECS['dinov3']['repo'],'facebook/dinov3-vits16-pretrain-lvd1689m')
  self.assertEqual(SPECS['siglip2']['revision'],'75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2')
  for v in SPECS.values():self.assertRegex(v['revision'],r'^[0-9a-f]{40}$')
  self.assertIn('official CLS',SPECS['dinov3']['pooling']);self.assertIn('attention pooled',SPECS['siglip2']['pooling'])
 def test_new_help_root_and_arbitrary_cwd_no_ml_imports(self):
  blocker="import builtins,runpy,sys; original=builtins.__import__; denied={'torch','torchvision','numpy','PIL','sklearn','transformers','huggingface_hub','safetensors'}; builtins.__import__=lambda name,*a,**k: (_ for _ in ()).throw(RuntimeError('heavy import on help: '+name)) if name.split('.')[0] in denied else original(name,*a,**k); sys.argv=[sys.argv[1],'--help']; runpy.run_path(sys.argv[0],run_name='__main__')"
  for name in ['dinov3','siglip2']:
   for cli in ['train.py','test.py','weights/fetch.py']:
    for cwd in [ROOT,ROOT/'.cache']:
     p=subprocess.run([sys.executable,'-c',blocker,str(ROOT/'classifiers'/name/cli)],cwd=cwd,capture_output=True,text=True)
     self.assertEqual(p.returncode,0,p.stderr);self.assertIn('usage:',p.stdout)
 def test_benchmark_clis_real_or_nullable(self):
  for name in ['siglip2','dinov3']:
   p=subprocess.run([sys.executable,str(ROOT/'classifiers'/name/'test.py'),'--benchmark'],cwd=ROOT/'.cache',capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);v=json.loads(p.stdout)
   if name=='siglip2':self.assertEqual((v['all22']['correct'],v['all22']['n'],v['common9']['correct']),(15,22,5))
   else:self.assertEqual(v['status'],'access_blocked');self.assertIsNone(v['all22']);self.assertIsNone(v['head_sha256'])
  for name in ['siglip2','dinov3']:
   p=subprocess.run([sys.executable,str(ROOT/'classifiers'/name/'test.py'),'--benchmark','--image','missing.png'],capture_output=True,text=True)
   self.assertEqual(p.returncode,2);self.assertIn('not allowed with argument',p.stderr)
 def test_no_silent_remote_code_or_unsafe_pickle_loading(self):
  s=(ROOT/'classifiers/common/foundation_next.py').read_text()
  self.assertNotIn('from_pretrained(',s);self.assertNotIn('trust_remote_code=True',s);self.assertIn('weights_only=True',s);self.assertIn('strict=True',s)
 def test_numeric_logistic_and_svc_genuine_fit_reload_parity(self):
  import numpy as np
  from classifiers.common.head_selection import fit_head
  from classifiers.common.numeric_linear_head import export,load,decision
  rng=np.random.default_rng(42);x=rng.normal(size=(22,7)).astype('float32');y=np.array([0]*13+[1]*9)
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as td:
   for kind in ['logistic','linear_svm']:
    model=fit_head(x,y,dict(head=kind,C=.1));p=Path(td)/'head.json';export(model,p);v=load(p,7)
    self.assertEqual(v['head'],kind)
    np.testing.assert_array_equal(decision(v,x),model.decision_function(x));np.testing.assert_array_equal(decision(v,x)>0,model.predict(x))
 def test_numeric_exact_schema_rejects_metadata_and_pickle(self):
  from classifiers.common.numeric_linear_head import validate
  v=dict(format='twi-numeric-linear-v1',head='linear_svm',mean=[0.],scale=[1.],coef=[2.],intercept=0.)
  validate(v)
  for key in ['features','labels','samples','paths','group','annotation','raw_reply']:
   with self.assertRaises(ValueError):validate(dict(v,**{key:[]}))
  for key,value in [('format','pickle'),('head','rbf'),('scale',[0.]),('mean',[float('nan')]),('coef',[True]),('intercept',float('inf'))]:
   with self.assertRaises(ValueError):validate(dict(v,**{key:value}))
  with self.assertRaises(ValueError):validate(v,2)
 def test_trainonly_standardization_and_no_review_fit_contract(self):
  s=(ROOT/'classifiers/common/foundation_next_experiment.py').read_text()
  self.assertIn('trials_for(features,y,rows',s);self.assertIn('inner_n=2',s);self.assertIn('features[chosen[',s)
  self.assertIn('[:22],y,chosen)',s);self.assertNotIn('fit_head(features,review',s)
 def test_canonical_is_full_frame_metadata_free_synthetic(self):
  from PIL import Image
  from classifiers.common.foundation_next import canonical
  im=Image.new('RGB',(1400,700),(20,90,160));b=io.BytesIO();im.save(b,format='PNG');source=b.getvalue()
  image,record=canonical(source);self.assertEqual(image.size,(1024,512));self.assertEqual(image.mode,'RGB');self.assertEqual(image.getexif(),{})
  self.assertEqual(hashlib.sha256(source).hexdigest(),record['source_sha256']);self.assertEqual(record['enhancements'],[])
 def test_aspect_preserving_pad_no_crop_official_normalization(self):
  import numpy as np
  from PIL import Image
  from classifiers.common.foundation_next import adapt
  folder=ROOT/'classifiers/siglip2/weights/upstream/siglip2'
  x=adapt(Image.new('RGB',(224,112),(255,0,0)),folder).numpy()
  self.assertEqual(x.shape,(3,224,224));np.testing.assert_allclose(x[:,0,0],np.full(3,(128/255-.5)/.5),atol=1e-6)
  np.testing.assert_array_equal(x[:,100,100],[1.,-1.,-1.])
 def test_actual_owned_head_privacy_binding(self):
  from tools.check_publication import content_rules
  p=ROOT/'classifiers/siglip2/weights/head.json';data=p.read_bytes();self.assertEqual(content_rules(str(p.relative_to(ROOT)),data),[])
  self.assertIn('unapproved_owned_head_content',content_rules(str(p.relative_to(ROOT)),data+b' '))
  self.assertIn('unapproved_weights_path',content_rules('classifiers/dinov3/weights/head.json',data))
 def test_new_privacy_negative_hf_token_and_features(self):
  from tools.check_publication import content_rules
  self.assertIn('known_token_format',content_rules('bad.txt',('hf'+'_'+('x'*36)).encode()))
  self.assertIn('private_or_large_artifact_path',content_rules('classifiers/siglip2/weights/features.npz',b'fixture'))
 def test_actual_anonymous_arithmetic_and_no_source_ids(self):
  from tools.check_publication import next_numeric_checks
  value=next_numeric_checks(ROOT);self.assertEqual(value['appended_oof_rows'],66)
  p=json.loads((ROOT/'docs/foundation-next-2026-11-10/per-image.json').read_text())
  self.assertEqual(set(p),{'clip_224','siglip2_224','nested_architecture'})
  for rows in p.values():
   for r in rows:self.assertEqual(set(r),{'case','truth','prediction','decision_margin'})
 def test_frozen_plan_protocol_not_retrospective_pooling(self):
  p=json.loads((ROOT/'docs/foundation-next-2026-11-10/plan.json').read_text())
  self.assertEqual(p['fold_train_test'],[[13,9],[15,7],[16,6]]);self.assertEqual(len(p['head_grid']),6)
  self.assertFalse(p['selection_protocol_changed_after_results']);self.assertEqual(p['freeze_receipt']['stage'],'before first backbone execution')
  self.assertIn('No pooling/resolution search',p['pooling_rationale'])
 def test_dino_remains_unrun_not_old_dinov2(self):
  p=json.loads((ROOT/'classifiers/dinov3/results/summary.json').read_text())
  self.assertTrue(p['not_dinov2']);self.assertIsNone(p['checkpoint_sha256']);self.assertFalse((ROOT/'classifiers/dinov3/weights/head.json').exists())
 def test_acquisition_is_explicit_and_never_accepts_terms(self):
  s=(ROOT/'classifiers/common/foundation_next_acquisition.py').read_text();self.assertIn('--execute',s);self.assertIn("revision=spec['revision']",s)
  self.assertNotIn('accept_access',s);self.assertNotIn('agree',s);self.assertNotIn('while ',s)
 def test_all22_head_is_not_an_oof_claim(self):
  p=json.loads((ROOT/'classifiers/siglip2/results/summary.json').read_text())
  self.assertTrue(p['final_fit']['not_oof_accuracy']);self.assertEqual(p['final_fit']['fit_population'],22);self.assertEqual(p['operational_automation_coverage'],0.)

 def test_inference_missing_or_unapproved_checkpoint_fails_closed(self):
  from classifiers.common.foundation_next_integrity import verify
  with self.assertRaises(RuntimeError):verify('dinov3',ROOT/'.cache')
  with self.assertRaises(ValueError):verify('siglip2',ROOT/'.cache')
