"""Offline source contracts, not paid/private-photo/model inference."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import importlib.util,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'classifiers/common'),str(ROOT/'classifiers/common')]
os.environ['TYRE_PROJECT_ROOT']=str(ROOT)
os.chdir(ROOT) # Child ledger processes must import the same curated source tree.
(ROOT/'.cache/tmp').mkdir(parents=True,exist_ok=True)
FILES=['tests/test_benchmark_contract.py','tests/test_cloud_cost_bounds.py','tests/test_cost_ledger.py','dashboard/backend/test_feedback.py','dashboard/backend/test_upload_contract.py','tests/test_refinement_v3.py','tests/test_publication.py','tests/test_layout.py','tests/test_foundation_next.py']
if __name__=='__main__':
 suite=unittest.TestSuite()
 for i,rel in enumerate(FILES):
  spec=importlib.util.spec_from_file_location('offline_source_'+str(i),ROOT/rel);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),model_inference=False,cloud_calls=False)))
 raise SystemExit(0 if result.wasSuccessful() else 1)
