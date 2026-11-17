"""Real saved-prediction cohort/usage projections; no new model calls."""
import json, unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from dashboard.backend import benchmark as b
ROOT=Path(__file__).resolve().parents[1]
class CohortTests(unittest.TestCase):
 def test_exact_core_six_shared_nine(self):
  d=b.summary();self.assertEqual(d['default_cohort'],'shared9');self.assertEqual(d['method_count'],6)
  self.assertEqual(b.SHARED9,frozenset((1,2,8,10,11,18,20,22,25)))
  for m,correct,unsafe,accepted,reviews in zip(d['methods'],[4,4,7,8,3,9],[1,1,2,0,3,0],[9,9,9,8,8,9],[0,0,0,1,1,0]):
   with self.subTest(method=m['method']):
    self.assertEqual((m['binary_n'],m['bad_n'],m['correct_binary'],m['unsafe_good_of_bad'],m['accepted_n'],m['review_outputs']),(9,5,correct,unsafe,accepted,reviews))
    self.assertEqual(m['accuracy_binary'],correct/9);self.assertEqual(m['accepted_accuracy'],correct/accepted);self.assertEqual(m['binary_coverage'],accepted/9)
 def test_full22_no_partial_gpt_and_no_mixed_denominators(self):
  c=b.summary()['cohorts']['full22'];self.assertEqual((c['n'],c['bad'],c['good']),(22,13,9))
  for m,correct,unsafe in zip(c['methods'],[12,14,18,19,11,None],[2,3,2,1,6,None]):
   self.assertEqual((m['binary_n'],m['bad_n'],m['correct_binary'],m['unsafe_good_of_bad']),(22,13,correct,unsafe))
  g=c['methods'][-1];self.assertFalse(g['evaluated'])
  for k in ['accuracy_binary','accepted_accuracy','binary_coverage','latency_seconds','usd_per_submitted_image_low']:self.assertIsNone(g[k])
  self.assertEqual(g['latency_label'],'Not evaluated')
 def test_cloud_costs_and_latency_recomputed_from_exact_cohort(self):
  from statistics import median
  cases=json.loads((ROOT/'classifiers/common/results/cloud-rounds-per-case.json').read_text())
  for key,c in b.summary()['cohorts'].items():
   for m,variant in zip(c['methods'][3:5],['vision-rubric-v2','decisions-rubric-v2']):
    rows=[r for r in cases if r['variant']==variant and r['population']=='unique_binary_scoring' and (key=='full22' or r['index'] in b.SHARED9)]
    self.assertEqual(m['latency_seconds'],median(r['latency_seconds_success'] for r in rows));self.assertEqual(m['latency_n'],c['n'])
    for suffix in ['low','high']:
     expected=float(sum(Decimal(str(r['usd_'+suffix])) for r in rows)/len(rows))
     self.assertEqual(m['usd_per_submitted_image_'+suffix],expected)
     inp,out=(Decimal('.11'),Decimal('.55')) if suffix=='low' else (Decimal('.22'),Decimal('.825'))
     token_mean=float(sum(Decimal(r['usage_success']['input_tokens'])*inp+Decimal(r['usage_success']['output_tokens'])*out for r in rows)/1000000/len(rows))
     self.assertEqual(m['usd_per_submitted_image_'+suffix],token_mean)
  r,d=b.summary()['methods'][3:5];self.assertAlmostEqual(r['usd_per_submitted_image_low'],.0002700377777777778);self.assertAlmostEqual(d['usd_per_submitted_image_high'],.0003342533333333333)
 def test_ft_actual_fee_fixed_cost_and_median(self):
  m=b.summary()['methods'][-1]
  self.assertEqual(m['usd_per_submitted_image_low'],.002464);self.assertEqual(m['hosting_usd_hour'],1.7)
  self.assertEqual(m['training_one_off_usd'],31.9792);self.assertEqual(m['latency_n'],9);self.assertAlmostEqual(m['latency_seconds'],3.4450626373291016)
 def test_local_smoke_is_not_cohort_latency(self):
  for m,seconds,cost in zip(b.summary()['methods'],[8.619960414000161,8.643395066000267,11.430406352999853],[.0005171976248400097,.000518603703960016,.0006858243811799911]):
   self.assertIsNone(m['latency_seconds']);self.assertEqual(m['latency_label'],'Not measured');self.assertEqual(m['latency_n'],0)
   self.assertEqual(m['smoke_n'],1);self.assertEqual(m['smoke_seconds'],seconds);self.assertEqual(m['usd_per_submitted_image_low'],cost)
   self.assertIn('Not a cohort cost mean',m['cost_note'])
 def test_two_review_photos_only_secondary_diagnostic(self):
  rows=b.summary()['methods'];self.assertTrue(all('source-review' in m['review_diagnostic'] for m in rows))
  self.assertTrue(rows[3]['review_diagnostic'].startswith('2/2'));self.assertTrue(rows[4]['review_diagnostic'].startswith('2/2'))
  self.assertTrue(rows[-1]['review_diagnostic'].startswith('Not evaluated'))
 def test_explicit_dto_allowlist_and_no_private_data(self):
  expected={'method','label','family','provider_id','evaluated','binary_n','bad_n','correct_binary','accuracy_binary','accepted_accuracy','binary_coverage','unsafe_good_of_bad','accepted_n','review_outputs','errors','source','evaluation','latency_seconds','latency_n','latency_label','latency_scope','usd_per_submitted_image_low','usd_per_submitted_image_high','cost_label','cost_note','review_diagnostic','cost_source','cost_snapshot','latency_source','hosting_usd_hour','training_one_off_usd','smoke_seconds','smoke_n'}
  for c in b.summary()['cohorts'].values():
   for m in c['methods']:self.assertEqual(set(m),expected)
  blob=json.dumps(b.summary()).lower()
  for text in ['siglip','dinov3','automl','/home/','c:/users/','request_ids','raw_response','original_reason','data:image','source_sha256','prompt_tokens','http_seconds']:
   self.assertNotIn(text,blob)
  self.assertTrue((ROOT/'classifiers/siglip2/results/per-image.json').is_file());self.assertTrue((ROOT/'classifiers/dinov3/results/summary.json').is_file());self.assertTrue((ROOT/'classifiers/azure-automl/results/summary.json').is_file())
  class Registry:
   def methods(self):
    return [dict(id='remote-luna',label='Luna',family='luna',status='unavailable',reason='Adapter absent',paid=True,private_path='private-sentinel',request_ids=['private-sentinel']),dict(id='remote-aml',label='Omitted',family='azure-ml',status='unavailable')]
  metadata=b.method_metadata(Registry());self.assertEqual(len(metadata),1)
  self.assertEqual(set(metadata[0]),{'id','label','family','status','reason','paid'})
  self.assertNotIn('private-sentinel',json.dumps(metadata))
 def test_ui_explorer_fully_removed_upload_results_preserved(self):
  html=(ROOT/'dashboard/frontend/index.html').read_text();js=(ROOT/'dashboard/frontend/dashboard.js').read_text()
  for text in ['#explorer','id="explorer"','image-method','image-index','image-rows','record-count','Per-image evidence']:self.assertNotIn(text,html)
  for text in ['/api/per-images','function images()','records=','image-method','image-index','image-rows']:self.assertNotIn(text,js)
  for text in ['id="results"','id="label-form"','id="paid-consent"','id="retention-consent"']:self.assertIn(text,html)
  self.assertNotIn('Review / 2',html);self.assertIn('id="cohort"',html);self.assertIn('cohort-caption',js)
 def test_budget_not_replaced_with_historical_counts(self):
  with patch.object(b.importlib.util,'spec_from_file_location',side_effect=ImportError):
   value=b.budget();self.assertFalse(value['live_snapshot']);self.assertIsNone(value['used']);self.assertIsNone(value['remaining']);self.assertTrue(value['ledger_blocked'])
 def test_review_error_incorrect_and_missing_cohort_unscored(self):
  rows=[dict(truth='bad',prediction='review'),dict(truth='good',prediction='error')]
  m=b._metrics(rows,2,1);self.assertEqual(m['correct_binary'],0);self.assertEqual(m['errors'],1);self.assertEqual(m['review_outputs'],1);self.assertEqual(m['binary_coverage'],0)
  self.assertFalse(b._metrics(rows,9,5)['evaluated'])

 def test_no_private_row_fields_leak_even_when_sources_contain_them(self):
  original=b.read
  def poisoned(path,default=None):
   value=original(path,default)
   if str(path).endswith('per-image.json'):
    return [dict(row,private_path='private-sentinel',request_ids=['private-sentinel'],raw_response={'sentinel':'private-sentinel'},prompt='private-sentinel') for row in value]
   return value
  with patch.object(b,'read',side_effect=poisoned):
   self.assertNotIn('private-sentinel',json.dumps(b.summary()))
 def test_incomplete_or_duplicate_cohort_is_not_scored_as_full(self):
  original=b.read
  def duplicated(path,default=None):
   value=original(path,default)
   if str(path).endswith('resnet18/results/per-image.json'):
    return [dict(r,image_index=1) for r in value]
   return value
  with patch.object(b,'read',side_effect=duplicated):
   with self.assertRaises(AssertionError):b.summary()
