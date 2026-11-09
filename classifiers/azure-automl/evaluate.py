"""Score actual selected MLflow model locally, once. No endpoint or Azure calls."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse, base64, json, math, os, time
from pathlib import Path
from importlib import import_module
_prepare=import_module('classifiers.azure-automl.prepare')
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare import dump, read_json, sha, TEST

def tree_hash(path):
    files={str(p.relative_to(path)):sha(p.read_bytes()) for p in sorted(Path(path).rglob('*')) if p.is_file()}
    if not files: raise ValueError('empty model')
    return sha(json.dumps(files,sort_keys=True).encode()),files

def parse_prediction(output):
    if isinstance(output,str): output=json.loads(output)
    if hasattr(output,'to_dict'): output=output.to_dict(orient='records')
    if not isinstance(output,list) or len(output)!=1 or not isinstance(output[0],dict): raise ValueError('output shape')
    d=output[0]; labels=d.get('labels'); probs=d.get('probs')
    if not isinstance(labels,list) or len(labels)!=2 or set(labels)!={'bad','good'}: raise ValueError('label enum')
    if not isinstance(probs,list) or len(probs)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in probs): raise ValueError('probabilities')
    if abs(sum(probs)-1)>0.02: raise ValueError('probability sum')
    if probs[0]==probs[1]: return 'review',d
    return labels[probs.index(max(probs))],d

def metrics(truth,predictions):
    assert [r['index'] for r in truth]==TEST
    assert [r['index'] for r in predictions]==TEST
    columns=['bad','good','review','error']; confusion={y:{p:0 for p in columns} for y in ['bad','good']}
    for t,p in zip(truth,predictions):
        assert t['label'] in confusion and p['prediction'] in columns
        confusion[t['label']][p['prediction']]+=1
    correct=confusion['bad']['bad']+confusion['good']['good']
    classified=sum(p['prediction'] in ['bad','good'] for p in predictions)
    return dict(denominator=9,correct=correct,accuracy=correct/9,
        balanced_accuracy=(confusion['bad']['bad']/5+confusion['good']['good']/4)/2,
        class_recall={'bad':confusion['bad']['bad']/5,'good':confusion['good']['good']/4},
        bad_to_good_count=confusion['bad']['good'],bad_to_good_denominator=5,bad_to_good_rate=confusion['bad']['good']/5,
        confusion=confusion,confusion_rows=['bad','good'],confusion_columns=columns,
        classified=classified,coverage=classified/9,abstentions=sum(p['prediction']=='review' for p in predictions),
        errors=sum(p['prediction']=='error' for p in predictions))

def validate_selection(selection,model_dir):
    assert selection['job_status']=='Completed' and selection['child_status']=='FINISHED'
    assert selection['selection_metric']=='validation_accuracy' and selection['selection_source']=='automl_best_child_run_id'
    assert selection['best_child_run_id'] and selection['parent_job_id']
    assert math.isfinite(selection['validation_accuracy']) and 0<=selection['validation_accuracy']<=1
    assert tree_hash(model_dir)[0]==selection['model_tree_sha256'], 'model drift'

def evaluate(bundle,selection_path,model_dir,out,loader=None):
    bundle=Path(bundle);model_dir=Path(model_dir);out=Path(out)
    selection=read_json(selection_path);validate_selection(selection,model_dir)
    assert selection['bundle_checksums_sha256']==sha((bundle/'checksums.json').read_bytes()), 'selection/bundle mismatch'
    checksums=read_json(bundle/'checksums.json')
    for f,h in checksums.items(): assert sha((bundle/f).read_bytes())==h, 'bundle drift'
    truth=read_json(bundle/'evaluation/truth.json'); assert [r['index'] for r in truth]==TEST
    inputs=[]
    for r in truth:
        data=(bundle/'evaluation/images'/r['canonical_name']).read_bytes()
        assert sha(data)==r['canonical_sha256'];inputs.append((r['index'],data,sha(data)))
    import pandas as pd  # dependency preflight before the once-only reservation
    # A durable reservation before loading/scoring stops accidental second evaluation.
    out.mkdir(parents=True,exist_ok=True)
    with (out/'evaluation-started.json').open('x') as f:
        json.dump(dict(selection_sha256=sha(Path(selection_path).read_bytes()),model_tree_sha256=selection['model_tree_sha256'],
            input_hashes=[h for _,_,h in inputs],started_unix=time.time()),f);f.flush();os.fsync(f.fileno())
    start=time.perf_counter();predictions=[];load_error=None
    try:
        if loader is None:
            import mlflow.pyfunc
            loader=mlflow.pyfunc.load_model
        model=loader(str(model_dir))
    except Exception as exc: load_error=type(exc).__name__;model=None
    load_seconds=time.perf_counter()-start
    import pandas as pd
    for index,data,h in inputs:
        t=time.perf_counter();row=dict(index=index,canonical_sha256=h,prediction='error')
        try:
            if model is None: raise RuntimeError('model load failed')
            # Official input dataframe: only image base64. No label, reason, ID or source path.
            response=model.predict(pd.DataFrame({'image':[base64.encodebytes(data).decode('ascii')]}))
            pred,raw=parse_prediction(response);row.update(prediction=pred,raw=raw)
        except Exception as exc:row['error_type']=load_error or type(exc).__name__
        row['wall_seconds']=time.perf_counter()-t;predictions.append(row)
        dump(out/'predictions.json',predictions)
    report=metrics(truth,predictions)
    report.update(status='completed_with_errors' if report['errors'] else 'completed',
        parent_job_id=selection['parent_job_id'],best_child_run_id=selection['best_child_run_id'],
        selection_validation_accuracy=selection['validation_accuracy'],heldout_used_for_selection=False,
        model_tree_sha256=selection['model_tree_sha256'],selection_sha256=sha(Path(selection_path).read_bytes()),
        model_load_seconds=load_seconds,evaluation_wall_seconds=time.perf_counter()-start,
        inference_seconds=sum(r['wall_seconds'] for r in predictions),
        inference_mean_seconds=sum(r['wall_seconds'] for r in predictions)/9,
        training_wall_seconds=selection.get('training_wall_seconds'),
        training_cost_usd=None,inference_cost_usd=None,cost_status='unknown; obtain actual SKU/runtime/meter estimates separately; not invoice',
        inference_transport='local MLflow pyfunc; zero per-image HTTP submissions, not LLM-token requests',
        qualification='Previously explored archive; nine photos not nine confirmed independent tyres; provisional labels; mandatory expert review',
        native_transforms='Selected model settings retained; AutoML may crop/augment/normalize internally; canonical input equality only')
    dump(out/'evaluation-report.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--selection',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(evaluate(a.bundle,a.selection,a.model,a.out),indent=2))
