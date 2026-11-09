"""Offline source contracts, not paid/private-photo/model inference."""
import importlib.util,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'infra'),str(ROOT/'scripts')]
os.environ['TYRE_PROJECT_ROOT']=str(ROOT)
os.chdir(ROOT) # Child ledger processes must import the same curated source tree.
(ROOT/'.cache/tmp').mkdir(parents=True,exist_ok=True)
FILES=['tests/test_benchmark_contract.py','tests/test_cloud_cost_bounds.py','tests/test_cost_ledger.py','app/test_feedback.py','app/test_upload_contract.py','infra/test-refinement-v3.py','tests/test_publication.py']
if __name__=='__main__':
 suite=unittest.TestSuite()
 for i,rel in enumerate(FILES):
  spec=importlib.util.spec_from_file_location('offline_source_'+str(i),ROOT/rel);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),model_inference=False,cloud_calls=False)))
 raise SystemExit(0 if result.wasSuccessful() else 1)
