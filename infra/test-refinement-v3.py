import sys,json,unittest,copy,hashlib,csv
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'infra'),str(R/'scripts')]
import refinement_v3 as v
class RefinementTests(unittest.TestCase):
 @unittest.skip("Private raw provider/dataset/production evidence deliberately excluded")
 def test_actual_csv_counts(self):
  for name,n in [('decisions-offline-probabilities',50),('decisions-oof-routing',44),('decisions-offline-methods',10)]:
   rows=json.loads((v.O/(name+'.json')).read_text());csvrows=list(csv.DictReader((v.O/(name+'.csv')).read_text().splitlines()));self.assertEqual(len(rows),n);self.assertEqual(len(csvrows),n)
 @unittest.skip("Private raw provider/dataset/production evidence deliberately excluded")
 def test_fold_isolation(self):
  rows=json.loads((v.O/'decisions-offline-probabilities.json').read_text())
  for name in ('decisions-single-v1','decisions-multi-v1'):
   rs=[r for r in rows if r['variant']==name];_,a=v.grouped_oof(rs)
   for fold in a:
    self.assertFalse(set(fold['train_groups'])&set(fold['heldout_groups']))
    altered=copy.deepcopy(rs)
    for r in altered:
     if r['outer_fold']==fold['heldout_fold']:r['truth']='bad' if r['truth']=='good' else 'good'
    _,b=v.grouped_oof(altered);other=next(x for x in b if x['heldout_fold']==fold['heldout_fold']);self.assertEqual(fold['parameters'],other['parameters'])
 def test_reviews_preserved(self):
  row={'returned_choice':'review','prob_good':.99,'tread_visible':1,'clear_damage':0}
  self.assertEqual(v.route(row,0,0,1),'review')
 def test_clear_bad_partial_visibility(self):
  r={'visual_condition':'bad','visibility':'inadequate','groove_relief':'flattened_or_shallow','visible_damage':'no','evidence':'Visible bald area','needs_review':False,'tread_depth_mm':None,'twi_verified':None}
  body={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(r)}]}]}
  self.assertEqual(v.parse_v2('responses',body,True)['prediction'],'bad')
 @unittest.skip("Private raw provider/dataset/production evidence deliberately excluded")
 def test_no_truth_key_filename_or_unsupported_fields(self):
  m=json.loads((R/'artifacts/manifest.json').read_text())[0];data=(R/'data/extracted'/m['file']).read_bytes()
  for fn in (v.decisions_payload,v.vision_payload):
   p=fn(data,'tyre-luna',True);serialized=json.dumps(p)
   self.assertNotIn(m['file'],serialized);self.assertNotIn(m['reason'],serialized);self.assertNotIn(m['sha256'],serialized);self.assertNotIn('api_key',serialized);self.assertNotIn('Authorization',serialized);self.assertNotIn('max_output_tokens',serialized)
   image=p['input'][0]['content'][1];self.assertEqual(set(image),{'type','image_url'})
 @unittest.skip("Private raw provider/dataset/production evidence deliberately excluded")
 def test_plan_configs_immutable(self):
  plan=json.loads((v.O/'plan.json').read_text())
  for p,h in plan['config_sha256'].items():self.assertEqual(hashlib.sha256((R/p).read_bytes()).hexdigest(),h)
  for p,h in plan['immutable_files'].items():self.assertEqual(hashlib.sha256((R/p).read_bytes()).hexdigest(),h)
 @unittest.skip("Private raw provider/dataset/production evidence deliberately excluded")
 def test_final_actual_counts_and_cost_denominators(self):
  final=json.loads((R/'FINAL_BENCHMARK.json').read_text());self.assertEqual(final['new_successful'],50);self.assertEqual(final['lifetime_requests'],157);self.assertEqual(final['remaining_requests'],43)
  rs=json.loads((v.O/'per-image.json').read_text());self.assertEqual(len(rs),150);self.assertEqual(len(list(csv.DictReader((v.O/'per-image.csv').read_text().splitlines()))),150)
  for name in ('vision-rubric-v2','decisions-rubric-v2'):
   m=next(m for m in final['methods'] if m['method']==name);self.assertEqual(m['binary_n'],22);self.assertEqual(m['bad_n'],13);self.assertEqual(m['source_review_n'],2)
   self.assertAlmostEqual(m['usd_per_submitted_image_low']*25,m['retail_total_usd_low']);self.assertAlmostEqual(m['usd_per_accepted_classification_low']*m['cost_accepted_all_n'],m['retail_total_usd_low']);self.assertAlmostEqual(m['unsafe_rate_all_bad']*13,m['unsafe_good_of_bad'])
  audit=json.loads((v.O/'decisions-v2-calibration-fold-audit.json').read_text())
  dr=json.loads((v.O/'decisions-v2-offline-evidence.json').read_text())
  for f in audit['folds']:
   self.assertFalse(set(f['train_groups'])&set(f['heldout_groups']))
   altered=copy.deepcopy(dr)
   for r in altered:
    if r['outer_fold']==f['heldout_fold']:r['truth']='bad' if r['truth']=='good' else 'good'
   _,other=v.grouped_oof(altered);self.assertEqual(f['parameters'],next(x['parameters'] for x in other if x['heldout_fold']==f['heldout_fold']))
 def test_parse_fail_closed(self):
  self.assertEqual(v.parse_v2('decisions',{},True)['prediction'],'review');self.assertEqual(v.parse_v2('responses',{},True)['prediction'],'review')
if __name__=='__main__':unittest.main()
