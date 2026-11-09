"""All prices and usage here are clearly synthetic, not Azure evidence."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from classifiers.common.cost_accounting import estimate, aggregate, local_economics, usage_components
from classifiers.common.project_ledger import ProjectLedger, read_events, retry_deadline
from clock_fixture import Clock


def fixture():
    v=dict(model='SYNTHETIC',model_version='fixture-v1',sku='fixture',geography='fixture',currency='USD',api='decisions',context_tier='short')
    rate=dict(v,schema_version=1,verified=True,source_url='https://example.invalid/synthetic-rates',
        semantics_source_url='https://example.invalid/synthetic-semantics',retrieved_at='2026-11-07T00:00:00Z',effective_at='2026-11-07T00:00:00Z',
        write_semantics='input_inclusive_surcharge',output_includes_reasoning=True,context_min_tokens=0,context_max_tokens=1000,
        per_million=dict(input=1,output=5,cache_write=2,cache_hit=.1))
    usage=dict(input_tokens=100,output_tokens=50,total_tokens=150,
        input_tokens_details=dict(cached_tokens=20,cache_write_tokens=10),output_tokens_details=dict(reasoning_tokens=30))
    return v,rate,usage


class CostTests(unittest.TestCase):
    def test_every_component_and_reasoning_no_doublecount(self):
        v,r,u=fixture(); c=estimate(u,r,v)
        self.assertAlmostEqual(c['estimated_cost'],.000352)
        self.assertEqual(c['billable_quantities'],dict(input=80,output=50,cache_hit=20,cache_write=10))
        r['write_semantics']='partitioned_replacement'
        self.assertAlmostEqual(estimate(u,r,v)['estimated_cost'],.000342)

    def test_tier_and_identity_mismatch_fail_closed(self):
        v,r,u=fixture()
        for k in ('model','model_version','sku','geography','currency','api','context_tier'):
            with self.subTest(k=k):
                bad=dict(v); bad[k]='mismatch'
                with self.assertRaisesRegex(ValueError,'mismatch'):estimate(u,r,bad)
        r['context_max_tokens']=99
        with self.assertRaisesRegex(ValueError,'tier mismatch'):estimate(u,r,v)

    def test_unverified_rates_and_missing_cache_usage_unknown(self):
        v,r,u=fixture(); r['verified']=False
        self.assertIsNone(estimate(u,r,v)['estimated_cost'])
        r['verified']=True; u.pop('input_tokens_details')
        self.assertIsNone(estimate(u,r,v)['estimated_cost'])
        self.assertIsNone(estimate(None,r,v)['estimated_cost'])

    def test_retry_unknown_keeps_known_subtotal_not_zero_cost(self):
        v,r,u=fixture(); known=estimate(u,r,v); unknown=estimate(None,r,v)
        a=aggregate([known,known,unknown],2,1)
        self.assertEqual(a['physical_requests'],3); self.assertEqual(a['unknown_cost_attempts'],1)
        self.assertIsNone(a['estimated_cost']); self.assertIsNone(a['estimated_cost_per_submitted_image'])
        self.assertAlmostEqual(a['known_subtotal'],.000704)
        a=aggregate([known,known],1,1)
        self.assertAlmostEqual(a['estimated_cost_per_submitted_image'],.000704)
        self.assertAlmostEqual(a['effective_cost_per_accepted_classification'],.000704)

    def test_malformed_usage_rejected(self):
        v,r,u=fixture()
        for change in (dict(total_tokens=151),dict(input_tokens=-1),dict(output_tokens=True),
                       dict(input_tokens_details={'cached_tokens':101,'cache_write_tokens':0}),
                       dict(output_tokens_details={'reasoning_tokens':51})):
            self.assertIsNone(usage_components(dict(u,**change)))

    def test_missing_verification_evidence_fails_closed(self):
        v,r,u=fixture()
        for change in (dict(source_url=''),dict(retrieved_at='2026-11-07'),dict(write_semantics='guess'),dict(output_includes_reasoning=False)):
            with self.assertRaises(ValueError):estimate(u,dict(r,**change),v)

    def test_local_amortization_scenario(self):
        self.assertIsNone(local_economics(.2,360)['economic_cost_per_image'])
        self.assertEqual(local_economics(.2,360)['api_fee'],0)
        c=local_economics(.2,360,3.6,100)
        self.assertAlmostEqual(c['economic_cost_per_image'],.0038)
        with self.assertRaises(ValueError):local_economics(.2,360,3.6,0)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
        self.temp=tempfile.TemporaryDirectory(dir=root/'.cache/tmp'); self.root=Path(self.temp.name); self.clock=Clock()
    def tearDown(self):self.temp.cleanup()

    def test_historical_two_probes_count_once_immutable(self):
        infra=self.root/'infra'; infra.mkdir(); receipt=infra/'experiment-request-ledger.json'
        original=json.dumps({'limit':200,'attempts':[{'sequence':1},{'sequence':2}]}).encode(); receipt.write_bytes(original)
        with ProjectLedger(self.root,3,self.clock) as ledger:
            self.assertEqual(ledger.count,2)
            ident=ledger.reserve({},'deployment'); ledger.response(ident,actual_tokens=0)
            self.assertEqual(ledger.count,3); self.assertIsNone(ledger.reserve({},'deployment'))
        with ProjectLedger(self.root,3,self.clock) as ledger:self.assertEqual(ledger.count,3)
        self.assertEqual(receipt.read_bytes(),original)

    def test_hard200_and_lower_limit_cannot_be_reset(self):
        with ProjectLedger(self.root,1,self.clock) as ledger:
            ident=ledger.reserve({},'deployment'); ledger.response(ident,actual_tokens=0)
        with ProjectLedger(self.root,200,self.clock) as ledger:
            self.assertEqual(ledger.limit,1); self.assertIsNone(ledger.reserve({},'deployment'))
        other=self.root/'other'; (other/'infra').mkdir(parents=True)
        (other/'infra/experiment-request-ledger.json').write_text(json.dumps({'limit':200,'attempts':[{}]*199}))
        with ProjectLedger(other,1000,self.clock) as ledger:
            ident=ledger.reserve({},'deployment'); ledger.response(ident,actual_tokens=0)
            self.assertEqual(ledger.count,200); self.assertIsNone(ledger.reserve({},'deployment'))

    def test_atomic_response_halt_survives_without_halt_event(self):
        with ProjectLedger(self.root,200,self.clock) as ledger:
            ident=ledger.reserve({},'deployment')
            ledger.response(ident,actual_tokens=None,halt_reason='unknown_usage',status=500)
        with ProjectLedger(self.root,200,self.clock) as ledger:
            self.assertTrue(ledger.blocked)
            with self.assertRaises(ValueError):ledger.reserve({},'deployment')

    def test_unresolved_reservation_and_corrupt_tail_fail_closed(self):
        with ProjectLedger(self.root,200,self.clock) as ledger:ledger.reserve({},'deployment')
        with ProjectLedger(self.root,200,self.clock) as ledger:
            self.assertTrue(ledger.blocked)
            with self.assertRaisesRegex(ValueError,'unresolved'):ledger.reserve({},'deployment')
        path=self.root/'infra/benchmark-attempts.jsonl'
        with path.open('a') as f:f.write('{partial')
        with self.assertRaises(ValueError):
            with ProjectLedger(self.root): pass

    def test_concurrent_process_project_lease(self):
        # Real independent interpreter, deterministic handshake: no sleep polling.
        code="from classifiers.common.project_ledger import ProjectLedger; from pathlib import Path; import sys; l=ProjectLedger(Path(sys.argv[1])); l.__enter__(); print('locked',flush=True); sys.stdin.readline(); l.__exit__()"
        child=subprocess.Popen([sys.executable,'-c',code,str(self.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            with self.assertRaises(FileExistsError):
                with ProjectLedger(self.root):pass
            child.communicate('\n',timeout=10); self.assertEqual(child.returncode,0)
        finally:
            if child.poll() is None:child.kill(); child.wait()

    def test_stale_lock_fails_closed(self):
        (self.root/'infra').mkdir(); (self.root/'infra/benchmark-project.lock').write_text('abandoned')
        with self.assertRaises(FileExistsError):
            with ProjectLedger(self.root):pass

    def test_token_pacing_retry_after_and_shared_deployment(self):
        with ProjectLedger(self.root,200,self.clock) as ledger:
            t=self.clock.time(); ident=ledger.reserve({},'shared',rpm=1,tpm=1000)
            ledger.response(ident,actual_tokens=2500,retry_not_before=t+180)
            ledger.reserve({},'shared',rpm=1,tpm=1000)
            self.assertGreaterEqual(self.clock.time()-t,180)
        self.assertEqual(retry_deadline({'Retry-After':'120'},100),220)
        self.assertEqual(retry_deadline({'Retry-After':'Wed, 21 Oct 2015 07:28:00 GMT'},0),1445412480)
        with self.assertRaises(ValueError):retry_deadline({'Retry-After':'invalid'},100)

if __name__=='__main__':unittest.main()
