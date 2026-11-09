#!/usr/bin/env python3
"""Bounded Azure zero-shot image benchmark, dry-run by default.

No cloud calls until --execute and exact deployment config are authorized.
JSONL journal is flushed/fsynced BEFORE each HTTP attempt so crashes cannot reset
call/token reservations. Interrupted attempts remain charged and are not replayed.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import math
import sys
import time
from urllib.parse import urlparse
import requests
from contextlib import nullcontext
try:
    from .project_ledger import ProjectLedger, retry_deadline, read_events, digest as ledger_digest
    from .cost_accounting import estimate, aggregate, validate_rate, valid_total
except ImportError:
    from project_ledger import ProjectLedger, retry_deadline, read_events, digest as ledger_digest
    from cost_accounting import estimate, aggregate, validate_rate, valid_total
from PIL import Image, ImageOps
import io
try:
    from .benchmark_contract import decisions_payload, vision_payload, normalise_decisions, normalise_vision, RUBRIC_VERSION
except ImportError:
    from benchmark_contract import decisions_payload, vision_payload, normalise_decisions, normalise_vision, RUBRIC_VERSION

try:
    from .preprocessing import canonical_image, PIPELINE_VERSION
except ImportError:
    from preprocessing import canonical_image, PIPELINE_VERSION
try:
    from .cost_bounds import bounds as retail_bounds
except ImportError:
    from cost_bounds import bounds as retail_bounds
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
# Conservative reservation, not a provider pricing/tokenization guarantee.
# Unknown usage or usage beyond reservation halts further requests immediately.
INPUT_RESERVATION=262144
MAX_IMAGE_SIDE=1024


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def append(path,event):
    with path.open('a',encoding='utf-8') as f:
        f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())


def journal(path):
    if not path.exists(): return []
    # Do NOT ignore a partial final line: operator must inspect/recover first.
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sanitise(value,secrets=()):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if k.lower() in ('api-key','authorization','api_key','input','image_url') else sanitise(v,secrets)) for k,v in value.items()}
    if isinstance(value,list): return [sanitise(v,secrets) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,str):
        value=re.sub(r'data:image/[^\s"\']+', '[IMAGE REDACTED]', value)
        for secret in secrets:
            if secret: value=value.replace(secret,'[REDACTED]')
        return value[:64000]
    return value


def prepared_image(path):
    # Builders invoke the shared canonical pipeline once, on these source bytes.
    return path.read_bytes()


def endpoint_url(endpoint,api,allow_local=False):
    p=urlparse(endpoint)
    azure=p.hostname and (p.hostname.endswith('.openai.azure.com') or p.hostname.endswith('.services.ai.azure.com'))
    local=allow_local and p.hostname in ('127.0.0.1','localhost')
    if (not azure and not local) or (p.scheme!='https' and not local) or p.username or p.password or p.query or p.fragment:
        raise ValueError('Require HTTPS Azure endpoint (or explicit loopback test)')
    path=p.path.rstrip('/')
    if path not in ('','/openai/v1'): raise ValueError('Endpoint must be resource root or /openai/v1/')
    return endpoint.rstrip('/')+('/' if path else '/openai/v1/')+api


def parse_response(api,body,multi):
    if not isinstance(body,dict): return {'prediction':'review','reason':'invalid_response'}
    if body.get('error'): return {'prediction':'review','reason':'provider_error'}
    if api=='decisions':
        result=normalise_decisions(body.get('answers'),.65,.8 if multi else None)
        # Multi-question concerns are independent; implement gating CLIENT-SIDE.
        if multi and result['prediction']=='good':
            damage=[a for a in body.get('answers',[]) if isinstance(a,dict) and a.get('name')=='clear_damage']
            if len(damage)!=1 or damage[0].get('type')!='predicate' or type(damage[0].get('probability')) not in (int,float) or not 0<=damage[0]['probability']<.5:
                return {'prediction':'review','reason':'damage_or_malformed_gate'}
        return result
    if body.get('status')!='completed': return {'prediction':'review','reason':'incomplete_or_refused'}
    texts=[]
    output=body.get('output')
    if not isinstance(output,list): return {'prediction':'review','reason':'invalid_output'}
    for item in output:
        if not isinstance(item,dict): return {'prediction':'review','reason':'invalid_item'}
        # Reasoning-capable Responses models return reasoning items alongside the
        # assistant message. They are NOT output_text and must not invalidate it.
        if item.get('type') not in (None,'message'): continue
        if not isinstance(item.get('content'),list):
            return {'prediction':'review','reason':'invalid_content'}
        for content in item['content']:
            if not isinstance(content,dict): return {'prediction':'review','reason':'invalid_content'}
            if content.get('type')=='refusal': return {'prediction':'review','reason':'refusal'}
            if content.get('type')=='output_text':
                if not isinstance(content.get('text'),str): return {'prediction':'review','reason':'invalid_text'}
                texts.append(content['text'])
    try: return normalise_vision(json.loads(''.join(texts)))
    except (ValueError,TypeError): return {'prediction':'review','reason':'invalid_json'}


def run(config,out,execute=False,selection='all',max_calls=100,max_tokens=30000000,retries=1,timeout=60,allow_local=False,clock=time,project_max_calls=200):
    if not 1<=max_calls<=1000 or not 1<=max_tokens<=100000000 or not 0<=retries<=2 or not 1<=timeout<=120:
        raise ValueError('Invalid bounds')
    out.mkdir(parents=True,exist_ok=True)
    # Exclusive lock, fail closed. Stale lock removal requires inspecting journal.
    lock=out/'run.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        os.close(fd)
        with ProjectLedger(ROOT, project_max_calls, clock) if execute else nullcontext(None) as ledger:
            return _run(config,out,execute,selection,max_calls,max_tokens,retries,timeout,allow_local,clock,ledger)
    finally: lock.unlink()


def _run(config,out,execute,selection,max_calls,max_tokens,retries,timeout,allow_local,clock,ledger):
    manifest=json.loads((ROOT/'artifacts/manifest.json').read_text())
    split=json.loads((ROOT/'artifacts/classifier/splits.json').read_text())
    if selection not in ('all','shared-fold0'): raise ValueError('Invalid selection')
    selected={r['index'] for r in split['rows'] if r['outer_fold']==0}
    cases=[r for r in manifest if selection=='all' or r['index'] in selected]
    if 'selected_case_indices' in config:
        indices=config['selected_case_indices']
        if not isinstance(indices,list) or not indices or len(set(indices))!=len(indices) or any(type(i) is not int or i not in {c['index'] for c in cases} for i in indices):
            raise ValueError('Invalid explicit case selection')
        cases=[c for c in cases if c['index'] in indices]
    variants=config['variants']
    if not variants or len({v['name'] for v in variants})!=len(variants): raise ValueError('Empty/duplicate variants')
    for v in variants:
        if v['api'] not in ('decisions','responses') or type(v['multi_question']) is not bool: raise ValueError('Invalid variant')
        endpoint_url(v['endpoint'],v['api'],allow_local)
        if not isinstance(v['deployment'],str) or not v['deployment']: raise ValueError('Missing deployment')
        if execute and ('YOUR-' in v['endpoint'] or v['deployment'].startswith('EXACT-')): raise ValueError('Placeholder config cannot execute')
        if bool(v.get('api_key_env'))==bool(v.get('bearer_token_env')): raise ValueError('Choose exactly one auth env')
        if not 128<=v.get('max_output_tokens',1024)<=4096: raise ValueError('Invalid output cap')
    # Read and bind actual source bytes, not just manifest claims. No network first.
    source_hashes={}
    for case in cases:
        data=prepared_image(ROOT/'data/extracted'/case['file'])
        actual=hashlib.sha256(data).hexdigest()
        if actual != case['sha256']: raise ValueError('Source bytes sha256 mismatch: '+str(case['index']))
        source_hashes[str(case['index'])]=actual
    for v in variants: validate_rate(v.get('rate_card'),v)
    identity=canonical_hash({'source_hashes':source_hashes,'config':config,'manifest':manifest,'split':split,'rubric':RUBRIC_VERSION,'selection':selection,
         'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'ledger_code_sha256':hashlib.sha256(Path(sys.modules[ProjectLedger.__module__].__file__).read_bytes()).hexdigest(),
         'cost_code_sha256':hashlib.sha256(Path(sys.modules[estimate.__module__].__file__).read_bytes()).hexdigest(),
         'cost_bounds_code_sha256':hashlib.sha256(Path(sys.modules[retail_bounds.__module__].__file__).read_bytes()).hexdigest(),
         'contract_sha256':hashlib.sha256((ROOT/'classifiers/common/benchmark_contract.py').read_bytes()).hexdigest(),
         'image_side':MAX_IMAGE_SIDE,'pipeline':PIPELINE_VERSION,
         'preprocessing_code_sha256':hashlib.sha256(Path(canonical_image.__code__.co_filename).read_bytes()).hexdigest(),'reservation':INPUT_RESERVATION,'policy':'good=.65; visibility=.8; clear_damage<.5'})
    path=out/'events.jsonl'; events=journal(path)
    if events and any(e['run_identity']!=identity for e in events): raise ValueError('Resume configuration/data/code mismatch')
    if not events: append(path,{'event':'init','run_identity':identity,'selection':selection,'variants':sanitise(variants),'created':time.time()})
    calls=sum(e['event']=='attempt' for e in events)
    reserved=sum(e.get('reserved_tokens',0) for e in events if e['event']=='attempt')
    finished={e['case_key'] for e in events if e['event']=='result'}
    started_keys={e['case_key'] for e in events if e['event']=='attempt'}
    interrupted=started_keys-finished
    for key in interrupted:
        attempt=next(e for e in reversed(events) if e['event']=='attempt' and e['case_key']==key)
        case=next(r for r in cases if r['index']==attempt['index'])
        append(path,{'event':'result','run_identity':identity,'case_key':key,'variant':attempt['variant'],
              'index':case['index'],'sha256':case['sha256'],'truth':case['label'],'prediction':'review',
              'reason':'interrupted_attempt_not_replayed','error':'interrupted','latency_seconds':None,'usage':None})
        finished.add(key)
    halted=any(e['event']=='halt' for e in events) or bool(interrupted) or bool(ledger and ledger.blocked)
    if ledger and any(e['event']=='attempt' and not e.get('project_attempt_id') for e in events):
        # Legacy/unreconciled attempts cannot bypass the project-wide limit.
        halted=True
    if ledger and interrupted and not ledger.blocked:
        ledger.add({'event':'halt','reason':'unreconciled_local_attempt'})
    plan=[]; stop='interrupted_or_project_halt' if halted else None
    for v in variants:
        for case in cases:
            key=canonical_hash([v['name'],case['sha256'],case['index']])
            if key in finished or key in started_keys: continue
            plan.append({'variant':v['name'],'index':case['index'],'case_key':key})
            if not execute or halted: continue
            auth_name=v.get('api_key_env') or v.get('bearer_token_env'); secret=os.environ.get(auth_name)
            if not secret: raise ValueError('Missing auth environment variable '+auth_name)
            data=prepared_image(ROOT/'data/extracted'/case['file'])
            if hashlib.sha256(data).hexdigest()!=case['sha256']:
                raise ValueError('Source bytes sha256 mismatch before request')
            _,preprocessing_record=canonical_image(data)
            builder=decisions_payload if v['api']=='decisions' else vision_payload
            payload=builder(data,v['deployment'],v['multi_question'])
            if v['api']=='responses':
                payload['max_output_tokens']=v.get('max_output_tokens',1024); payload['store']=False
                if v.get('disable_prompt_cache'):
                    payload['prompt_cache_options']={'mode':'explicit','ttl':'30m'}
            headers={'Content-Type':'application/json'}
            key_header=v.get('api_key_header','api-key')
            if key_header not in ('api-key','Authorization'): raise ValueError('Unsupported API-key header')
            headers[key_header if v.get('api_key_env') else 'Authorization']=secret if v.get('api_key_env') and key_header=='api-key' else 'Bearer '+secret
            result={'prediction':'review','reason':'request_failed'}; body=None; error=None; status=None; latency=0
            attempted=False
            for attempt in range(retries+1):
                reservation=INPUT_RESERVATION+(v.get('max_output_tokens',1024) if v['api']=='responses' else 0)
                if calls>=max_calls or reserved+reservation>max_tokens:
                    stop='call_or_reserved_token_cap'; halted=True; break
                deployment_key=canonical_hash([endpoint_url(v['endpoint'],'responses',allow_local),v['deployment']])
                # USD 5 public-retail planning guard, not an Azure billing hard cap.
                # Historical/unknown requests retain a conservative planning reserve;
                # this is not substituted for missing measured usage in cost reports.
                project_replies={e['id']:e for e in ledger.rows if e['event']=='response'}
                planning_high=len(ledger.seed['attempts'])*(INPUT_RESERVATION+1500)*.825/1000000
                for e in ledger.rows:
                    if e['event']!='attempt': continue
                    bound=project_replies.get(e['id'],{}).get('cost_bounds',{}).get('usd_high')
                    planning_high += bound if bound is not None else e.get('reserved_tokens',INPUT_RESERVATION+1500)*.825/1000000
                if planning_high+reservation*.825/1000000 > 5:
                    stop='retail_planning_budget_cap'; halted=True
                    ledger.add({'event':'halt','reason':stop,'usd_planning_high':planning_high,'not_a_billing_cap':True})
                    break
                project_id=ledger.reserve({'run_identity':identity,'case_key':key,'variant':v['name'],
                     'index':case['index'],'reserved_tokens':reservation},deployment_key,
                     min(v.get('deployment_requests_per_minute',1),v.get('requests_per_minute',1)),min(v.get('deployment_tokens_per_minute',1000),v.get('tokens_per_minute',1000)))
                if project_id is None:
                    stop='project_call_cap'; halted=True; break
                calls+=1; reserved+=reservation; attempted=True
                append(path,{'event':'attempt','run_identity':identity,'case_key':key,'variant':v['name'],
                     'project_attempt_id':project_id,'index':case['index'],'attempt':attempt,'reserved_tokens':reservation,'time':time.time(),
                     'preprocessing':preprocessing_record})
                # Reset each retry: never attribute stale status/usage to a new attempt.
                body=None; status=None; error=None; response_headers={}; retry=False
                start=time.perf_counter()
                try:
                    with requests.post(endpoint_url(v['endpoint'],v['api'],allow_local),json=payload,headers=headers,
                        timeout=(10,timeout),allow_redirects=False,stream=True) as response:
                        status=response.status_code; response_headers=dict(response.headers)
                        chunks=[]; received=0
                        for chunk in response.iter_content(chunk_size=65536):
                            received+=len(chunk)
                            if received>2000000: raise ValueError('Response too large')
                            chunks.append(chunk)
                            if time.perf_counter()-start>timeout: raise ValueError('Response elapsed limit')
                        try: body=json.loads(b''.join(chunks))
                        except (ValueError,UnicodeDecodeError): body=None
                    error=None if 200<=status<300 else 'HTTP_'+str(status)
                    if error is None:
                        result=parse_response(v['api'],body,v['multi_question'])
                    latency+=time.perf_counter()-start
                    usage=body.get('usage',{}) if isinstance(body,dict) else {}
                    total=valid_total(usage)
                    # Service errors can still consume tokens; reservations are never refunded.
                    if total is None or total>reservation:
                        stop='missing_invalid_or_excess_usage'; halted=True
                    if status in (401,403):
                        stop='authentication_or_authorization'; halted=True
                    retry=status in (408,429,500,502,503,504)
                except (requests.RequestException,ValueError,TypeError) as exc:
                    latency+=time.perf_counter()-start
                    error=type(exc).__name__; body=None; retry=False
                    stop='uncertain_transport_or_response'; halted=True
                attempt_latency=time.perf_counter()-start
                actual_usage=body.get('usage') if isinstance(body,dict) else None
                try:
                    cost=estimate(actual_usage,v.get('rate_card'),v)
                    retry_at=retry_deadline(response_headers,clock.time()) if status==429 else clock.time()
                except (ValueError,TypeError,KeyError) as exc:
                    cost={'estimated_cost':None,'known_subtotal':0.0,'unknown':True,'error':str(exc)}
                    stop='cost_tier_or_retry_header_mismatch'; halted=True; retry_at=clock.time()
                ledger.response(project_id,status=status,error=error,halt_reason=stop if halted else None,prediction=result['prediction'] if error is None else 'review',usage=sanitise(actual_usage),
                    actual_tokens=valid_total(actual_usage),cost=cost,cost_bounds=retail_bounds(actual_usage),retry_not_before=retry_at)
                if halted: ledger.add({'event':'halt','reason':stop})
                append(path,{'event':'attempt_response','run_identity':identity,'case_key':key,'project_attempt_id':project_id,'variant':v['name'],'attempt':attempt,'cost':cost,
                       'status':status,'error':error,'raw_response':sanitise(body,[secret]),'response_request_ids':{k:v for k,v in response_headers.items() if k.lower() in ('apim-request-id','x-request-id','x-ms-request-id','request-id','date')},'cost_bounds':retail_bounds(actual_usage),'latency_seconds':attempt_latency})
                if halted or not retry or attempt==retries: break
                clock.sleep(min(2**attempt,4))  # project pacing also enforces Retry-After
            if stop in ('call_or_reserved_token_cap','project_call_cap') and not attempted:
                append(path,{'event':'halt','run_identity':identity,'reason':stop}); break
            row={'event':'result','run_identity':identity,'case_key':key,'variant':v['name'],'index':case['index'],
                 'sha256':case['sha256'],'truth':case['label'],'prediction':result['prediction'],
                 'reason':result['reason'],'error':error,'latency_seconds':latency,
                 'usage':sanitise(body.get('usage') if isinstance(body,dict) else None)}
            append(path,row); finished.add(key)
            if ledger:
                ledger.add({'event':'case_result','run_identity':identity,'case_key':key,'variant':v['name'],
                    'index':case['index'],'prediction':row['prediction'],'error':row['error']})
            if halted:
                append(path,{'event':'halt','run_identity':identity,'reason':stop}); break
        if halted: break
    records=journal(path); results=[e for e in records if e['event']=='result']
    summaries={}
    for v in variants:
        # Exact duplicate 14 is only a repeatability check, never scoring weight.
        rs=[r for r in results if r['variant']==v['name'] and r['index']!=14]
        binary=[r for r in rs if r['truth']!='review']; accepted=[r for r in binary if r['prediction']!='review']
        bad=[r for r in binary if r['truth']=='bad']; review_cases=[r for r in rs if r['truth']=='review']
        per_class={}
        for label in ('bad','good'):
            tp=sum(r['truth']==label and r['prediction']==label for r in binary)
            support=sum(r['truth']==label for r in binary); predicted=sum(r['prediction']==label for r in binary)
            precision=tp/predicted if predicted else 0.; recall=tp/support if support else None
            per_class[label]={'support':support,'precision':precision,'recall':recall,
               'f1':2*tp/(support+predicted) if support+predicted else 0.,
               'coverage':sum(r['truth']==label and r['prediction']!='review' for r in rs)/support if support else None}
        summaries[v['name']]={'completed_unique':len(rs),'binary_n':len(binary),
              'per_class':per_class,
              'macro_f1':sum(x['f1'] for x in per_class.values())/2 if binary else None,
              'balanced_accuracy':sum(x['recall'] for x in per_class.values())/2 if all(x['recall'] is not None for x in per_class.values()) else None,
              'unsafe_clearance_rate':sum(r['prediction']=='good' for r in bad)/len(bad) if bad else None,
              'review_rejection_rate':sum(r['prediction']=='review' for r in review_cases)/len(review_cases) if review_cases else None,
              'confusion':{t:{p:sum(r['truth']==t and r['prediction']==p for r in rs) for p in ('bad','good','review')} for t in ('bad','good','review')},
              'coverage':len(accepted)/len(binary) if binary else None,
              'accepted_accuracy':sum(r['truth']==r['prediction'] for r in accepted)/len(accepted) if accepted else None,
              'correct_auto_fraction':sum(r['truth']==r['prediction'] for r in binary)/len(binary) if binary else None,
              'errors':sum(bool(r['error']) for r in rs),
              'review_rejected':sum(r['truth']=='review' and r['prediction']=='review' for r in rs)}
    recorded_attempts={e['case_key'] for e in records if e['event']=='attempt'}
    completed_keys={e['case_key'] for e in results}
    pending=sum(canonical_hash([v['name'],c['sha256'],c['index']]) not in (recorded_attempts|completed_keys) for v in variants for c in cases)
    attempt_events=[e for e in records if e['event']=='attempt']
    responses={e.get('project_attempt_id'):e for e in records if e['event']=='attempt_response'}
    costs={}
    for v in variants:
        ats=[e for e in attempt_events if e['variant']==v['name']]
        cs=[responses.get(e.get('project_attempt_id'),{}).get('cost',{'estimated_cost':None,'known_subtotal':0.0}) for e in ats]
        vr=[e for e in results if e['variant']==v['name']]
        costs[v['name']]=aggregate(cs,len({e['case_key'] for e in ats}),sum(not e['error'] and e['prediction']!='review' for e in vr))
        expected=len(cases)
        summaries[v['name']].update(planned=expected,attempted=len({e['case_key'] for e in ats}),
            physical_requests=len(ats),complete=len(vr)==expected and all(not e['error'] for e in vr),
            success=sum(not e['error'] for e in vr),error=sum(bool(e['error']) for e in vr),
            missing=expected-len(vr),metrics_final=len(vr)==expected and all(not e['error'] for e in vr),
            scoring_population='unique binary photos only; 22 for all; fold0 development only, not final test',
            source_review_metrics={'n':sum(e['truth']=='review' for e in vr),
                 'rejected':sum(e['truth']=='review' and e['prediction']=='review' for e in vr)})
    case_costs=[]
    for key in sorted({e['case_key'] for e in attempt_events}):
        ats=[e for e in attempt_events if e['case_key']==key]
        final=next((e for e in results if e['case_key']==key),None)
        cs=[responses.get(e.get('project_attempt_id'),{}).get('cost',{'estimated_cost':None,'known_subtotal':0.0}) for e in ats]
        case_costs.append(dict(aggregate(cs,1,int(bool(final and not final['error'] and final['prediction']!='review'))),
            case_key=key,variant=ats[0]['variant'],index=ats[0]['index']))
    project_cost=None
    snapshot=ledger
    if snapshot is None:
        from types import SimpleNamespace
        receipt=ROOT/'infra/experiment-request-ledger.json'
        seed=json.loads(receipt.read_text()) if receipt.exists() else {'limit':200,'attempts':[]}
        project_events=read_events(ROOT/'infra/benchmark-attempts.jsonl')
        if project_events and project_events[0].get('receipt_hash')!=ledger_digest(seed):
            raise ValueError('Historical receipt changed; reconcile explicitly')
        snapshot=SimpleNamespace(seed=seed,rows=project_events,
            count=len(seed['attempts'])+sum(e['event']=='attempt' for e in project_events))
    if snapshot:
        historical=[{'estimated_cost':None,'known_subtotal':0.0} for _ in snapshot.seed['attempts']]
        project_responses={e['id']:e for e in snapshot.rows if e['event']=='response'}
        project_attempts=[e for e in snapshot.rows if e['event']=='attempt']
        project_logical=len(historical)+len({(e['run_identity'],e['case_key']) for e in project_attempts})
        project_accepted=len({(e['run_identity'],e['case_key']) for e in snapshot.rows
            if e['event']=='case_result' and e.get('prediction') in ('good','bad') and not e.get('error')})
        project_cost=aggregate(historical+[project_responses.get(e['id'],{}).get('cost',{'estimated_cost':None,'known_subtotal':0.0}) for e in project_attempts],project_logical,project_accepted)
        project_cost['currency_groups']={currency:aggregate([e['cost'] for e in project_responses.values() if e.get('cost',{}).get('currency')==currency],0,0)
            for currency in {e.get('cost',{}).get('currency') for e in project_responses.values()} if currency is not None}
        if len(project_cost['currency_groups'])>1:
            project_cost.update(known_subtotal=None,estimated_cost=None,known_subtotal_per_submitted_image=None,
                estimated_cost_per_submitted_image=None,effective_cost_per_accepted_classification=None,mixed_currencies=True)
    result={'run_identity':identity,'dry_run':not execute,'planned_remaining':pending,'selection':selection,
         'costs':costs,'case_costs':case_costs,'cost_population':'all submitted logical images, including duplicate/review checks; all physical retries; separate from binary scoring',
         'project_cost_including_historical_probes':project_cost,
         'project_attempt_count':snapshot.count,
         'complete':len(results)==len(cases)*len(variants) and all(not e['error'] for e in results),
         'planned':len(cases)*len(variants),'attempted':len(recorded_attempts),
         'success':sum(not e['error'] for e in results),'error':sum(bool(e['error']) for e in results),
         'missing':len(cases)*len(variants)-len(results),
         'metrics_final':len(results)==len(cases)*len(variants) and all(not e['error'] for e in results),
         'expected_case_variants':len(cases)*len(variants),'completed_case_variants':len(results),
         'calls_reserved':sum(e['event']=='attempt' for e in records),
         'tokens_reserved':sum(e.get('reserved_tokens',0) for e in records if e['event']=='attempt'),
         'interrupted_cases_not_replayed':len(interrupted),'halt':stop or ('previous_halt' if halted else None),
         'metrics':summaries,'unit':'exploratory photo; same suspected group split as classifier, not proven independent tyre',
         'budget_caveat':'Calls/reservations hard-limited; Azure Decisions documents no per-request token limit. Reservation is conservative, not guaranteed provider billing cap. Unknown/excess usage stops all further calls.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--execute',action='store_true'); ap.add_argument('--selection',choices=['all','shared-fold0'],default='all')
    ap.add_argument('--max-calls',type=int,default=100); ap.add_argument('--max-tokens',type=int,default=30000000)
    ap.add_argument('--retries',type=int,default=1); ap.add_argument('--timeout',type=int,default=60)
    ap.add_argument('--project-max-calls',type=int,default=200,help='Lower project-wide lifetime attempt cap; never above 200')
    a=ap.parse_args(); print(json.dumps(run(json.loads(a.config.read_text()),a.out,a.execute,a.selection,a.max_calls,a.max_tokens,a.retries,a.timeout,project_max_calls=a.project_max_calls),indent=2))

if __name__=='__main__': main()
