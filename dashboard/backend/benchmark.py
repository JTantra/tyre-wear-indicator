"""Read-only dashboard projection of real benchmark and derived routing evidence."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import json,os,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
def read(path,default=None):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return default

# Deliberate display allowlist, independent of the preserved research archive.
METHODS = (
 ('resnet18', 'ResNet18', 'custom-local', 'local-resnet18-final'),
 ('mobilenet', 'MobileNet', 'custom-local', 'local-mobilenet-final'),
 ('clip', 'CLIP', 'custom-local', 'local-clip-final'),
 ('luna-responses', 'Luna Responses', 'luna', 'remote-luna'),
 ('luna-decisions', 'Luna Decisions', 'luna', 'remote-luna'),
 ('gpt41-finetuned', 'GPT-4.1 fine-tuned', 'gpt', 'remote-gpt41-finetuned'),
)
SHARED9 = frozenset((1, 2, 8, 10, 11, 18, 20, 22, 25))
LIMITATIONS = [
 'Same evaluation photos does not mean identical training protocols. Local shared-nine scores use outer fold 0: heads trained on 13 binary photos. GPT used 13 different training examples (6 bad, 5 good, 2 review), with screened exclusions. Luna is prompted, with no trained head.',
 'Repeatedly explored development archive, not an independent held-out or prospective test. Local full-22 scores combine grouped out-of-fold predictions, not current full-data upload heads.',
 'Labels are provisional; source label 11 is flagged. Exact duplicate 14 is excluded. No tread-depth measurement, TWI assertion or roadworthiness certification.',
 'Latency and cost are historical evidence, not live capability checks. Startup smoke compute estimates are not cohort latency or measured throughput. Shared ACA hosting is one allocation, not three hosts; do not add active compute twice. Retail estimates exclude grants, storage, network, logging, taxes and other unallocated infrastructure; they are not invoices.',
]

def _metrics(rows, n, bad_n):
 # Fail closed on incomplete cohorts rather than score a convenient subset.
 if len(rows) != n:
  return dict(evaluated=False, binary_n=n, bad_n=bad_n, correct_binary=None,
   accuracy_binary=None, accepted_accuracy=None, binary_coverage=None,
   unsafe_good_of_bad=None, accepted_n=None, review_outputs=None, errors=None)
 accepted=sum(r['prediction'] in ('bad','good') for r in rows)
 correct=sum(r['truth']==r['prediction'] for r in rows)
 return dict(evaluated=True, binary_n=n, bad_n=bad_n, correct_binary=correct,
  accuracy_binary=correct/n, accepted_accuracy=correct/accepted if accepted else None,
  binary_coverage=accepted/n, unsafe_good_of_bad=sum(r['truth']=='bad' and r['prediction']=='good' for r in rows),
  accepted_n=accepted, review_outputs=sum(r['prediction']=='review' for r in rows),
  errors=sum(r['prediction'] not in ('bad','good','review') for r in rows))

def _method(mid, label, family, provider, cohort, costs, cloud):
 from statistics import median
 rows=read(ROOT/'classifiers'/mid/'results/per-image.json',[])
 rows=[r for r in rows if r['truth'] in ('bad','good') and (cohort=='full22' or r['image_index'] in SHARED9)]
 n,bad_n=(9,5) if cohort=='shared9' else (22,13)
 if len(rows)==n:
  assert len({r['image_index'] for r in rows})==n and sum(r['truth']=='bad' for r in rows)==bad_n
  assert cohort!='shared9' or {r['image_index'] for r in rows}==SHARED9
 m=dict(method=mid,label=label,family=family,provider_id=provider,**_metrics(rows,n,bad_n))
 m.update(source='classifiers/'+mid+'/results/per-image.json',
  evaluation='Shared nine photos / fold 0' if cohort=='shared9' else ('Full 22 binary development photos / grouped OOF' if family=='custom-local' else 'Full 22 binary development photos / prompted API'),
  latency_seconds=None,latency_n=0,latency_label='Not measured',
  latency_scope='No cohort request timings recorded for local CV predictions.',
  usd_per_submitted_image_low=None,usd_per_submitted_image_high=None,
  cost_label='Not evaluated',cost_note='No full-22 evaluation or usage exists for this method.',
  review_diagnostic='Not evaluated: no recorded two-photo source-review diagnostic.',
  cost_source='docs/assets/verified-azure-costs.json',cost_snapshot=costs['generated_utc'],
  latency_source=None,hosting_usd_hour=None,training_one_off_usd=None,
  smoke_seconds=None,smoke_n=0)
 if not m['evaluated']:
  m.update(evaluation='Not evaluated on the full 22; only the shared nine were scored.',latency_label='Not evaluated',latency_scope='No full-22 request timings: this method was evaluated on nine photos only.')
  return m
 c=next(c for c in costs['methods'] if c['method']=={'luna-responses':'Luna Responses v2','luna-decisions':'Luna Decisions v2','gpt41-finetuned':'GPT-4.1 vision fine-tuned'}.get(mid,label))
 if family=='custom-local':
  m.update(usd_per_submitted_image_low=float(c['rough_active_compute_per_image_usd']),
   usd_per_submitted_image_high=float(c['rough_active_compute_per_image_usd']),cost_label='~ active compute',
   cost_note=c['timing_scope']+'. API fee $0. '+c['hosting']+'. Not a cohort cost mean; grants/idle hosting/other infrastructure excluded. No measured local training cost.',
   smoke_seconds=float(c['observed_seconds']),smoke_n=c['timing_n'])
 elif family=='luna':
  variant='vision-rubric-v2' if mid=='luna-responses' else 'decisions-rubric-v2'
  cases=[r for r in cloud if r['variant']==variant]
  chosen=[r for r in cases if r['population']=='unique_binary_scoring' and (cohort=='full22' or r['index'] in SHARED9)]
  # Match exact scored predictions before associating usage and timings.
  assert len(chosen)==n and {(r['index'],r['prediction']) for r in chosen}=={(r['image_index'],r['prediction']) for r in rows}
  assert all(r['physical_attempts']==1 and r['unknown_cost_attempts']==0 for r in chosen)
  from decimal import Decimal
  meters=costs['first_party_tariffs']['luna']['selected_meters']
  def tariff(name):
   meter=next(x for x in meters if x['meterName']==name)
   assert meter['unitOfMeasure']=='1M'
   return Decimal(str(meter['retailPrice']))/1000000
  def usage_mean(tier):
   inp=tariff('6-luna '+tier+' Inp Std DZ 1M Tokens')
   out=tariff('6-luna '+tier+' Opt Std DZ 1M Tokens')
   fees=[]
   for r in chosen:
    usage=r['usage_success'];cache=usage['input_tokens_details']
    assert cache['cached_tokens']==0 and cache['cache_write_tokens']==0
    fee=Decimal(usage['input_tokens'])*inp+Decimal(usage['output_tokens'])*out
    assert fee==Decimal(str(r['usd_low' if tier=='ShortCo' else 'usd_high']))
    fees.append(fee)
   return float(sum(fees)/n)
  low,high=usage_mean('ShortCo'),usage_mean('LongCo')
  times=[r['latency_seconds_success'] for r in chosen]
  review=[r for r in cases if r['population']=='review_rejection_only']
  m.update(latency_seconds=median(times),latency_n=len(times),latency_label='median API request',
   latency_scope='Archived successful request elapsed seconds for the selected cohort; excludes dashboard upload/queue. Not a current SLA.',
   latency_source='classifiers/common/results/cloud-rounds-per-case.json',
   usd_per_submitted_image_low=low,usd_per_submitted_image_high=high,cost_label='API retail range',
   cost_source='classifiers/common/results/cloud-rounds-per-case.json + docs/assets/verified-azure-costs.json',
   cost_note=str(n)+' selected-cohort submissions, actual saved usage/retail bounds (short vs long context), one attempt each. '+c['billing_uncertainty']+'. No new calls.',
   review_diagnostic=str(sum(r['prediction']=='review' for r in review))+'/'+str(len(review))+' source-review photos rejected (separate diagnostic, not part of either binary cohort).')
 else:
  times=[r['http_seconds'] for r in rows]
  from decimal import Decimal
  fee=float(sum(Decimal(r['usage']['prompt_tokens'])*Decimal('0.0022')/1000+Decimal(r['usage']['completion_tokens'])*Decimal('0.0088')/1000 for r in rows)/n)
  m.update(latency_seconds=median(times),latency_n=len(times),latency_label='median HTTP request',
   latency_scope='Archived HTTP elapsed seconds on nine evaluation requests; excludes dashboard upload/queue. Not a current SLA.',latency_source=m['source'],
   usd_per_submitted_image_low=fee,usd_per_submitted_image_high=fee,cost_label='API + fixed hosting',
   hosting_usd_hour=float(c['hosting_usd_hour']),training_one_off_usd=float(c['training_one_off_usd']),
   cost_note='Nine actual evaluation requests at fine-tuned regional tariffs (not baseline GPT pricing). API fee excludes $1.70/hour while deployed, even idle, plus $31.98 one-off training. Retail estimate, not invoice.')
 return m

def summary():
 costs=read(ROOT/'docs/assets/verified-azure-costs.json')
 cloud=read(ROOT/'classifiers/common/results/cloud-rounds-per-case.json',[])
 cohorts={}
 for key,n,bad,good in [('shared9',9,5,4),('full22',22,13,9)]:
  methods=[_method(*method,key,costs,cloud) for method in METHODS]
  cohorts[key]=dict(id=key,n=n,bad=bad,good=good,methods=methods,
   caption='Shared nine evaluation photos' if key=='shared9' else 'Full 22 binary development photos')
 return dict(source='Saved predictions / cohort projection v2',default_cohort='shared9',
  methods=cohorts['shared9']['methods'],method_count=len(METHODS),cohorts=cohorts,
  limitations=LIMITATIONS,warning=LIMITATIONS[1],
  provenance=dict(projection_version=2,archive_baseline='63c074f7fe97f17196f3421e7e0001e3d0221086',
   cost_snapshot=costs['generated_utc'],archive_unchanged=True))

def method_metadata(registry):
 # Display-only DTO: provider internals must never leak to the browser.
 allowed={entry[3] for entry in METHODS}
 result=[]
 for row in registry.methods():
  if row['id'] not in allowed:continue
  entry={key:row.get(key) for key in ('id','label','family','status','reason','paid')}
  if entry['status']=='unavailable' and entry['family']=='custom-local':
   entry['reason']='Required numeric head or pinned backbone not installed. Historical CV scores do not make a saved-head upload runtime available.'
  result.append(entry)
 return result

def budget():
 # No lock acquisition or mutation: readers validate a snapshot, and each
 # provider separately obtains the exclusive lease before a paid request.
 path=ROOT/'dashboard/backend/private_live_providers.py'
 try:
  spec=importlib.util.spec_from_file_location('dashboard_budget_view',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.budget_snapshot()
 except (OSError,ValueError,AttributeError,ImportError):return {'lifetime_cap':200,'used':None,'remaining':None,'read_only':True,'snapshot_not_authorization':True,'live_snapshot':False,'additional_approved_usd':None,'monetary_limit_removed':True,'exact_invoice_usd':None,'ledger_blocked':True,'note':'Current ledger unavailable. Providers fail closed; display never authorizes spending.'}

def per_images():
 rows=read(ROOT/'classifiers/common/results/per-image.json',[])
 return [dict(variant=r['method'],index=r['image_index'],truth=r['truth'],prediction=r['prediction'],fold=r['fold'],population='frozen-development-archive',status='historical',reason='Archived benchmark evidence, NOT fresh image inference') for r in rows]
