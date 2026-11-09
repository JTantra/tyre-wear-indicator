"""Synthetic contracts + actual anonymous artifact arithmetic, no model inference."""
import copy, importlib.util, io, json, sys, tempfile, threading, unittest, urllib.request
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import check_publication as gate
class PublicationTests(unittest.TestCase):
 def test_real_projection_counts_and_costs(self):gate.numeric_checks(ROOT)
 def test_fail_closed_manifest_and_links(self):
  errors,counts=gate.check(ROOT);self.assertEqual(errors,[]);self.assertEqual(counts['documented_methods'],7)
 def test_negative_token_fixture(self):
  value='gh'+'p_'+('x'*40);self.assertIn('known_token_format',gate.content_rules('bad.txt',value.encode()))
 def test_negative_image_payload_fixture(self):
  value='data:image/jpeg;'+'base64,'+('a'*80);self.assertIn('image_base64_payload',gate.content_rules('bad.json',value.encode()))
 def test_negative_identity_fixture(self):
  value='12345678'+'-1234-1234-1234-'+'123456789abc';self.assertIn('uuid_identity_or_private_filename',gate.content_rules('bad.json',value.encode()))
 def test_negative_secret_fixture(self):
  value='password'+': '+chr(34)+('x'*24)+chr(34);self.assertIn('literal_secret_assignment',gate.content_rules('bad.txt',value.encode()))
 def test_negative_raw_provider_fixture(self):
  value=json.dumps({'raw'+'_response':{'mock':True}});self.assertIn('production_readback_payload',gate.content_rules('bad.json',value.encode()))
 def test_negative_binary_fixture(self):self.assertIn('unapproved_binary',gate.content_rules('model.bin',bytes([255,0,1])))
 def test_negative_svg_image_fixture(self):self.assertIn('embedded_image_svg',gate.content_rules('bad.svg',b'<svg><image href="photo.png"/></svg>'))
 def test_ledger_historical_reconciliation_is_disabled(self):
  from scripts.project_ledger import ProjectLedger
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as td:
   with ProjectLedger(Path(td)) as ledger:
    with self.assertRaises(ValueError):ledger.reconcile_auth('anything','anything')
 def test_cloud_guard_requires_fresh_approval(self):
  from unittest.mock import patch
  import cloud_policy_v2
  with patch.dict('os.environ',{},clear=True):
   with self.assertRaises(PermissionError):cloud_policy_v2.guard(None,1)
 def test_gpt_actual_parse_and_tariff(self):
  spec=importlib.util.spec_from_file_location('publication_gpt',ROOT/'infra/vision-finetune/adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  reply=dict(usage=dict(prompt_tokens=100,completion_tokens=5,total_tokens=105,prompt_tokens_details=dict(cached_tokens=0)),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(dict(visual_condition='bad'))))])
  pred,usage=m.parse(reply);self.assertEqual(pred,'bad');self.assertAlmostEqual(m.retail_cost(usage)['exact_retail_estimate_usd'],.000264)
  reply['usage']['total_tokens']=106
  with self.assertRaises(AssertionError):m.parse(reply)
 def test_gpt_payload_has_image_not_truth(self):
  spec=importlib.util.spec_from_file_location('publication_gpt2',ROOT/'infra/vision-finetune/adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  payload=m.payload(b'SYNTHETIC IMAGE CONTRACT ONLY','FIXTURE_DEPLOYMENT');self.assertEqual(payload['max_completion_tokens'],64);self.assertEqual(payload['seed'],105);self.assertFalse(payload['store']);self.assertNotIn('truth',payload)
 def test_automl_pure_job_and_output_contract(self):
  path=ROOT/'infra/automl-pilot-v1/preparation';sys.path.insert(0,str(path))
  import prepare,evaluate,download_best
  job=dict(type='automl',task='image_classification',primary_metric='accuracy',target_column_name='label',limits=dict(max_trials=5,max_concurrent_trials=1,timeout_minutes=90),training_data=dict(type='mltable',mode='direct',path='./upload/train'),validation_data=dict(type='mltable',mode='direct',path='./upload/validation'))
  prepare.validate_job(job)
  for field in ['test_data','search_space','validation_data_size']:
   with self.assertRaises(AssertionError):prepare.validate_job(dict(job,**{field:{}}))
  self.assertEqual(evaluate.parse_prediction([dict(labels=['bad','good'],probs=[.5,.5])])[0],'review')
  with self.assertRaises(ValueError):evaluate.parse_prediction([dict(labels=['bad','bad'],probs=[.3,.7])])
  self.assertEqual(download_best.choose_child(dict(automl_best_child_run_id='FIXTURE_CHILD')),'FIXTURE_CHILD')
  with self.assertRaises(ValueError):download_best.choose_child(dict(test_accuracy=1))
 def test_automl_frozen_rows_contract(self):
  path=ROOT/'infra/automl-pilot-v1/preparation';sys.path.insert(0,str(path));import prepare
  part=json.loads((ROOT/'results/partitions.json').read_text());by={r['image_index']:r for r in part['rows']};rows=[]
  for i in range(1,26):
   r=by.get(i,{});partition='train' if i in prepare.TRAIN else 'validation' if i in prepare.VAL else 'evaluation' if i in prepare.TEST else 'excluded'
   rows.append(dict(index=i,label=r.get('label','review'),group=r.get('group','excluded-'+str(i)),source_sha256='fixture-'+str(i),canonical_sha256='canonical-fixture-'+str(i),partition=partition))
  prepare.validate_rows(rows);bad=copy.deepcopy(rows);bad[4]['group']=bad[0]['group']
  with self.assertRaises(AssertionError):prepare.validate_rows(bad)
 def test_automl_metrics_count_errors_reviews(self):
  sys.path.insert(0,str(ROOT/'infra/automl-pilot-v1/preparation'));import evaluate,prepare
  truth=[dict(index=r['image_index'],label=r['label']) for r in json.loads((ROOT/'results/partitions.json').read_text())['rows'] if r['outer_fold']==0]
  predicted=[dict(index=r['index'],prediction='error' if n==0 else 'review' if n==1 else r['label']) for n,r in enumerate(truth)]
  result=evaluate.metrics(truth,predicted);self.assertEqual(result['denominator'],9);self.assertEqual(result['correct'],7);self.assertEqual(result['errors'],1);self.assertEqual(result['abstentions'],1)
 def test_real_loopback_app_readonly(self):
  from app import server
  from app.feedback import SQLiteFeedbackStore
  from app.job_store import MemoryJobStore
  from http.server import ThreadingHTTPServer
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as td:
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);port=http.server_address[1]
   server.configure(port=port,bind='127.0.0.1',feedback=SQLiteFeedbackStore(Path(td)/'feedback'),jobs=MemoryJobStore(),runtime=Path(td)/'uploads',start_worker=False)
   thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   try:
    with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/methods') as r:
     data=json.load(r);self.assertEqual(r.status,200);self.assertFalse(any(m['status']=='available' for m in data['methods']))
    with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/benchmarks') as r:
     data=json.load(r);self.assertEqual(data['method_count'],7)
   finally:http.shutdown();http.server_close();thread.join(5)
 @unittest.skip('Original private image archive/weights intentionally excluded; no model inference or fake result')
 def test_private_models_retrain_and_infer(self):pass
 @unittest.skip('AutoML private bundle and native selected model absent because GPU quota blocked; no AutoML score')
 def test_native_automl_training_inference(self):pass
