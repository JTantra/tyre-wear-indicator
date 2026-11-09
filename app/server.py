"""Loopback by default; explicit fail-closed public HTTPS + private durable stores."""
import argparse,hashlib,io,json,mimetypes,os,re,secrets,socket,tempfile,threading,time,warnings
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image,ImageOps,UnidentifiedImageError
from app.providers import Registry
from app import benchmark
from app.feedback import create_store as feedback_factory,owner_key,now,FeedbackError,CONSENT_VERSION,NORMALIZATION_VERSION,RUBRIC_VERSION
from app.session_security import SessionSecurity,OriginPolicy,recovery_capability,recovery_parts
from app.job_store import create_store as job_factory,StoreError,ACTIVE,TERMINAL,provider_context
ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=5*1024*1024; MAX_CANONICAL_BYTES=MAX_BYTES; MAX_BODY=MAX_BYTES+64*1024; MAX_PIXELS=16_000_000
Image.MAX_IMAGE_PIXELS=MAX_PIXELS
# No directories, factories, provider adapters or background workers at import time.
FEEDBACK=None; JOB_STORE=None; REGISTRY=None; SECURITY=None; POLICY=None; RUNTIME=None
PUBLIC=False; DECODERS=threading.BoundedSemaphore(2); STOP=threading.Event(); WORKER_THREAD=None
ISSUANCE_LOCK=threading.Lock(); ISSUANCE={}; ALLOWED_HOSTS=set()

READ_SECONDS=15; DECODE_SECONDS=15
class ImageTooLarge(ValueError): pass
class CappedBuffer(io.BytesIO):
 def write(self,data):
  if self.tell()+len(data)>MAX_CANONICAL_BYTES: raise ImageTooLarge('Normalized image exceeds 5 MB; use a smaller image')
  return super().write(data)
def validate_image(data):
 deadline=time.monotonic()+DECODE_SECONDS
 def check_deadline():
  if time.monotonic()>deadline: raise TimeoutError('Image decoding deadline exceeded')
 if not data or len(data)>MAX_BYTES: raise ImageTooLarge('Image must be between 1 byte and 5 MB')
 try:
  with warnings.catch_warnings():
   warnings.simplefilter('error',Image.DecompressionBombWarning)
   with Image.open(io.BytesIO(data)) as im:
    if im.format not in {'JPEG','PNG','WEBP'}: raise ValueError('Use JPEG, PNG or WebP')
    if im.width*im.height>MAX_PIXELS: raise ValueError('Image exceeds 16 megapixels')
    if getattr(im,'n_frames',1)>1: raise ValueError('Animated images are not supported')
    im.verify(); check_deadline()
   with Image.open(io.BytesIO(data)) as im:
    im.load(); check_deadline(); out=CappedBuffer(); ImageOps.exif_transpose(im).convert('RGB').save(out,format='PNG'); check_deadline()
  return out.getvalue()
 except TimeoutError: raise
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc: raise ValueError('Image cannot be safely decoded') from exc

def configure(port=8765,bind='127.0.0.1',feedback=None,jobs=None,registry=None,security=None,runtime=None,start_worker=True):
 global FEEDBACK,JOB_STORE,REGISTRY,SECURITY,POLICY,RUNTIME,PUBLIC,WORKER_THREAD
 PUBLIC=bind not in {'127.0.0.1','localhost','::1'}
 origins=os.environ.get('TYRE_PUBLIC_ORIGINS','').split()
 POLICY=OriginPolicy(PUBLIC,origins,port,os.environ.get('TYRE_ACA_HTTPS_INGRESS')=='1')
 SECURITY=security or SessionSecurity.from_env(PUBLIC)
 if SECURITY.public!=PUBLIC: raise RuntimeError('Cookie mode disagrees with listener')
 # Validate all public configuration before any fallback store side effects.
 if PUBLIC and (not os.environ.get('TYRE_FEEDBACK_FACTORY') or not os.environ.get('TYRE_JOB_FACTORY')): raise RuntimeError('Public mode requires explicit durable feedback and job factories')
 if PUBLIC: os.environ['TYRE_REQUIRE_DURABLE_FEEDBACK']='1'
 FEEDBACK=feedback or feedback_factory(); JOB_STORE=jobs or job_factory(PUBLIC)
 if PUBLIC and (getattr(FEEDBACK,'durable',False) is not True or getattr(JOB_STORE,'durable',False) is not True): raise RuntimeError('Public stores must be private durable adapters')
 # Full feedback factory validates its private schema/lease; read-only health projection too.
 FEEDBACK.list_owned('__readiness__'); JOB_STORE.health(); JOB_STORE.reconcile()
 REGISTRY=registry or Registry()
 if PUBLIC and any(m.get('paid') and m.get('status')=='available' for m in REGISTRY.methods()):
  if getattr(getattr(REGISTRY,'remote',None),'durable_job_checkpoint_contract',None)!='public-server-v4/1':
   raise RuntimeError('Public paid adapter must implement durable job_checkpoint + shared-ledger contract')
 # Per-process ephemeral directory. Never remove another server's uploads.
 RUNTIME=Path(runtime) if runtime else Path(tempfile.mkdtemp(prefix='tyre-upload-',dir=os.environ.get('TYRE_UPLOAD_SCRATCH','/dev/shm')))
 RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(RUNTIME,0o700)
 ALLOWED_HOSTS.clear(); ALLOWED_HOSTS.update(POLICY.authorities)
 STOP.clear()
 if start_worker:
  WORKER_THREAD=threading.Thread(target=worker_loop,daemon=True); WORKER_THREAD.start()

def retention_record(job):
 return {'annotation_id':job['job_id'],'job_id':job['job_id'],'owner':job['owner'],'source_sha256':job['source_sha256'],'image_sha256':job['image_sha256'],'consent_at':job['consent_at'],'consent_version':CONSENT_VERSION,'completed_at':now(),'normalization_version':NORMALIZATION_VERSION,'rubric_version':RUBRIC_VERSION,'method_provenance':job['method_provenance'],'predictions':job['results'],'source_population':'custom-upload-review-diagnostic-not-benchmark'}

def provider_checkpoint(job_id,owner,method,token,guard,*,reservation_id=None,provider_job_id=None):
 """Parent adapter callback: persist ledger reservation BEFORE HTTP; ID immediately on receipt.
 No ledger allocation/mutation is performed here. Callback failure must abort the adapter.
 """
 job=JOB_STORE.get(job_id,owner); intents=dict(job['submission_intents'])
 if method not in intents: raise StoreError('Submission intent missing')
 binding=dict(intents[method])
 if reservation_id is not None:
  if not isinstance(reservation_id,str) or not 1<=len(reservation_id)<=256 or any(ord(c)<32 for c in reservation_id): raise StoreError('Invalid reservation binding')
  binding['reservation']=reservation_id; binding['state']='reserved'
 changes={}
 if provider_job_id is not None:
  if not isinstance(provider_job_id,str) or not 1<=len(provider_job_id)<=1024 or any(ord(c)<32 for c in provider_job_id): raise StoreError('Invalid provider ID')
  binding['state']='submitted'; results=dict(job['results']); results[method]={'status':'pending','provider_job_id':provider_job_id}; changes['results']=results
 intents[method]=binding; changes['submission_intents']=intents
 JOB_STORE.update(job_id,token,guard,**changes)

def run_job(job_id,path=None,selected=None,consent=None):
 with JOB_STORE.worker(job_id) as claim:
  if claim is None: return
  token,guard=claim
  # Job heartbeat independent of synchronous adapter latency; guard renews/fences globally.
  halt=threading.Event()
  def heartbeat():
   while not halt.wait(10):
    try: JOB_STORE.update(job_id,token,guard)
    except Exception:
     if hasattr(guard,'failed'): guard.failed=True
     return
  beat=threading.Thread(target=heartbeat,daemon=True); beat.start()
  try:
   job=next(j for j in JOB_STORE.candidates() if j['job_id']==job_id)
   selected=job['selected']; path=path or RUNTIME/(job_id+'.png')
   for method in selected:
    job=JOB_STORE.get(job_id,job['owner']); previous=job['results'].get(method,{})
    if previous.get('status') not in {None,'pending'}: continue
    deadline=job['deadlines'].get(method)
    checkpoint=lambda _owner=job['owner'],_method=method,**kw: provider_checkpoint(job_id,_owner,_method,token,guard,**kw)
    try:
     if previous.get('status')=='pending' and previous.get('provider_job_id'):
      value=previous
     else:
      # Durable submit intent BEFORE I/O. Unknown prior submission is never replayed.
      if method in job['submission_intents'] or not path.exists(): raise RuntimeError('Upload/submission interrupted; needs owner reconciliation')
      deadline=time.time()+1800
      intents=dict(job['submission_intents']); intents[method]={'at':time.time(),'paid':bool(job['paid_methods'].get(method)),'state':'submitting','reservation':'parent-adapter-shared-ledger-required'}
      deadlines=dict(job['deadlines']); deadlines[method]=deadline
      statuses=dict(job['method_statuses']); statuses[method]='running'
      JOB_STORE.update(job_id,token,guard,submission_intents=intents,deadlines=deadlines,method_statuses=statuses)
      guard.check()
      context={'paid_consent':job['paid_consent'],'job_id':job_id,'worker_fence':token,'provider_deadline':deadline,'submission_intent_persisted':True,'job_checkpoint':checkpoint}
      with provider_context(context): value=REGISTRY.infer(method,path,context)
      job=JOB_STORE.get(job_id,job['owner'])
     while value.get('status')=='pending':
      if not isinstance(value.get('provider_job_id'),str) or not value['provider_job_id'] or len(value['provider_job_id'])>1024: raise RuntimeError('Pending provider ID missing')
      results=dict(job['results']); results[method]=value; statuses=dict(job['method_statuses']); statuses[method]='pending'
      JOB_STORE.update(job_id,token,guard,results=results,method_statuses=statuses)
      job=JOB_STORE.get(job_id,job['owner'])
      if time.time()>=deadline: raise TimeoutError('Persisted provider deadline exceeded')
      if STOP.wait(min(2,max(0,deadline-time.time()))): return
      guard.check()
      context={'paid_consent':job['paid_consent'],'job_id':job_id,'worker_fence':token,'provider_deadline':deadline,'submission_intent_persisted':True,'job_checkpoint':checkpoint,'provider_job_id':value['provider_job_id']}
      with provider_context(context): value=REGISTRY.poll(value['provider_job_id'])
      job=JOB_STORE.get(job_id,job['owner'])
     if not isinstance(value,dict): raise ValueError('Invalid provider result')
     results=dict(job['results']); results[method]=value; statuses=dict(job['method_statuses']); statuses[method]=value.get('status','error')
     JOB_STORE.update(job_id,token,guard,results=results,method_statuses=statuses)
    except StoreError: raise
    except Exception:
     job=JOB_STORE.get(job_id,job['owner']); results=dict(job['results']); prior=results.get(method,{})
     # Keep known IDs and deadlines on timeout/failure for operator reconciliation, never fake complete.
     results[method]={'status':'error','error':'Provider failed/interrupted; inspect owner diagnostics. No automatic resubmission.',**({'provider_job_id':prior['provider_job_id']} if prior.get('provider_job_id') else {})}
     statuses=dict(job['method_statuses']); statuses[method]='error'
     JOB_STORE.update(job_id,token,guard,results=results,method_statuses=statuses,needs_owner_reconcile=bool(job.get('needs_owner_reconcile') or job['paid_methods'].get(method)))
   job=JOB_STORE.get(job_id,job['owner']); states=list(job['method_statuses'].values()); changes={}
   if job['retention_consent'] and any(s=='complete' for s in states):
    try:
     # Idempotent read-before-retain; existing withdrawn state wins. No Python job mutex.
     try: result=FEEDBACK.get(job_id,job['owner'])
     except FeedbackError as exc:
      if exc.status!=404: raise
      if not path.exists(): raise RuntimeError('Ephemeral consented upload lost before retention')
      guard.check(); result=FEEDBACK.retain(retention_record(job),path.read_bytes())
     changes['feedback']=FEEDBACK.get(job_id,job['owner'])
    except Exception: changes['feedback_error']='Private retention incomplete; contact owner. No label may be saved until verified.'
   changes['status']='interrupted' if job.get('needs_owner_reconcile') else 'complete' if all(s=='complete' for s in states) else 'partial' if any(s=='complete' for s in states) else 'error'
   JOB_STORE.update(job_id,token,guard,**changes)
  finally:
   halt.set(); beat.join(12)
   if path: path.unlink(missing_ok=True)

def worker_loop():
 # Queued ephemeral uploads need a heartbeat even while the single worker is busy.
 def keep_uploads():
  while not STOP.wait(10):
   try: JOB_STORE.touch_uploads([p.stem for p in RUNTIME.glob('*.png')])
   except Exception: pass
 keeper=threading.Thread(target=keep_uploads,daemon=True); keeper.start()
 try:
  while not STOP.is_set():
   try:
    JOB_STORE.reconcile()
    for j in JOB_STORE.candidates():
     path=RUNTIME/(j['job_id']+'.png')
     pending=any(v.get('status')=='pending' and v.get('provider_job_id') for v in j['results'].values())
     if path.exists() or (pending and not j.get('worker_token')): run_job(j['job_id'],path)
   except Exception: pass # Store/worker failure never authorizes uncertain resubmission.
   STOP.wait(.2)
 finally: keeper.join(12)

def issuance_allowed(peer):
 t=time.monotonic()
 with ISSUANCE_LOCK:
  for k in list(ISSUANCE):
   if ISSUANCE[k]['until']<t: del ISSUANCE[k]
  if peer not in ISSUANCE and len(ISSUANCE)>=1000: return False
  for k,limit in [(peer,20),('__global__',120)]:
   a=ISSUANCE.setdefault(k,{'count':0,'until':t+60}); a['count']+=1
   if a['count']>limit: return False
 return True

class Handler(BaseHTTPRequestHandler):
 server_version='TyreResearch/4'
 def setup(self):
  self.request.settimeout(READ_SECONDS); super().setup()
 def log_message(self,*args): pass
 def send(self,status,value,content_type='application/json',extra=None):
  body=json.dumps(value,allow_nan=False).encode() if content_type=='application/json' else value
  self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body)))
  self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
  if PUBLIC: self.send_header('Strict-Transport-Security','max-age=31536000')
  for k,v in (extra or {}).items(): self.send_header(k,v)
  # Never leave rejected/unread bodies available for a subsequent request.
  self.close_connection=True; self.send_header('Connection','close'); self.end_headers(); self.wfile.write(body)
 def guard(self,write=False):
  if POLICY is None: self.send(503,{'error':'Server not initialized'}); return False
  if not POLICY.check(self.headers,write): self.send(403,{'error':'Allowed same HTTPS origin/ingress required' if PUBLIC else 'Allowed loopback same origin required'}); return False
  self.auth=SECURITY.from_headers(self.headers) # Immutable snapshot at handler entry.
  if write and (not self.auth or len(self.headers.get_all('X-CSRF-Token',[]))!=1 or not re.fullmatch(r'[A-Za-z0-9_-]{43}',self.headers['X-CSRF-Token']) or not secrets.compare_digest(self.headers['X-CSRF-Token'],self.auth.csrf)):
   self.send(403,{'error':'Session / CSRF token required'}); return False
  return True
 def session(self): return getattr(self,'auth',None)
 def do_GET(self):
  if not self.guard(): return
  path=urlsplit(self.path).path
  if path=='/api/session':
   if self.auth: return self.send(200,{'csrf_token':self.auth.csrf})
   if not issuance_allowed(self.client_address[0]): return self.send(429,{'error':'Session issuance rate limit'})
   value,auth=SECURITY.issue(); return self.send(200,{'csrf_token':auth.csrf},extra={'Set-Cookie':SECURITY.cookie(value)})
  if path=='/api/ready':
   try: JOB_STORE.health(); FEEDBACK.list_owned('__readiness__'); return self.send(200,{'ready':True,'public':PUBLIC})
   except Exception: return self.send(503,{'ready':False})
  if path=='/api/benchmarks': return self.send(200,benchmark.summary())
  if path=='/api/methods': return self.send(200,{'methods':REGISTRY.methods(),'budget':benchmark.budget()})
  if path=='/api/per-images': return self.send(200,{'rows':benchmark.per_images()})
  if path=='/api/feedback':
   if not self.auth: return self.send(404,{'error':'Session not found'})
   try: return self.send(200,{'annotations':FEEDBACK.list_owned(owner_key(self.auth.id))})
   except Exception: return self.send(503,{'error':'Private feedback storage unavailable'})
  match=re.fullmatch(r'/api/(feedback|jobs)/([a-f0-9]{32})',path)
  if match:
   kind,key=match.groups()
   if not self.auth: return self.send(404,{'error':'Record not found'})
   owner=owner_key(self.auth.id)
   try:
    if kind=='feedback': return self.send(200,FEEDBACK.get(key,owner))
    job=JOB_STORE.get(key,owner)
    # Re-read consent projection so withdrawal always wins over a stale job cache.
    if job.get('feedback'):
     job['feedback']=FEEDBACK.get(key,owner)
    return self.send(200,{k:v for k,v in job.items() if k not in {'owner','worker_token','submission_intents','outbox'}})
   except (FeedbackError,StoreError) as exc: return self.send(exc.status,{'error':str(exc)})
   except Exception: return self.send(503,{'error':'Private storage unavailable'})
  assets={'/':'index.html','/style.css':'style.css','/dashboard.js':'dashboard.js'}
  if path in assets:
   p=ROOT/'dashboard'/assets[path]; return self.send(200,p.read_bytes(),mimetypes.guess_type(str(p))[0] or 'text/plain')
  return self.send(404,{'error':'Not found'})
 def read_body(self,length):
  deadline=time.monotonic()+READ_SECONDS; chunks=[]; remaining=length
  while remaining:
   wait=deadline-time.monotonic()
   if wait<=0: raise TimeoutError('Body deadline exceeded')
   self.connection.settimeout(wait)
   chunk=self.rfile.read1(min(65536,remaining))
   if not chunk: raise ValueError('Incomplete body')
   chunks.append(chunk); remaining-=len(chunk)
  if time.monotonic()>deadline: raise TimeoutError('Body deadline exceeded')
  return b''.join(chunks)
 def json_body(self,cap=8192):
  if self.headers.get_all('Transfer-Encoding',[]): raise FeedbackError('Chunked bodies not supported')
  lengths=self.headers.get_all('Content-Length',[])
  if len(lengths)!=1 or not re.fullmatch('[0-9]+',lengths[0]): raise FeedbackError('One valid Content-Length required')
  length=int(lengths[0])
  if not 0<length<=cap: raise FeedbackError('Request body too large',413)
  if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise FeedbackError('application/json required')
  raw=self.read_body(length)
  if len(raw)!=length: raise FeedbackError('Incomplete body')
  data=json.loads(raw)
  if not isinstance(data,dict): raise FeedbackError('JSON object required')
  return data
 def do_POST(self):
  if not self.guard(True): return
  route=urlsplit(self.path).path
  match=re.fullmatch(r'/api/feedback/([a-f0-9]{32})/(label|revoke)',route)
  if match: return self.feedback_write(*match.groups())
  if route in {'/api/recovery','/api/recovery/rotate'}:
   try:
    data=self.json_body()
    if route=='/api/recovery/rotate':
     if data: raise FeedbackError('Recovery rotation body must be empty')
     owner=self.auth.id; replacement=recovery_capability(owner); _,fresh=recovery_parts(replacement)
     JOB_STORE.issue_recovery(owner_key(owner),fresh)
    else:
     if set(data)!={'recovery_token'}: raise FeedbackError('recovery_token required')
     owner,old=recovery_parts(data['recovery_token']); replacement=recovery_capability(owner); _,fresh=recovery_parts(replacement)
     JOB_STORE.recover(owner_key(owner),old,fresh,owner_key(self.auth.id))
    value,auth=SECURITY.issue(owner)
    return self.send(200,{'csrf_token':auth.csrf,'recovery_token':replacement,'save_recovery_token':True},extra={'Set-Cookie':SECURITY.cookie(value)})
   except (FeedbackError,StoreError) as exc: return self.send(exc.status,{'error':str(exc)})
   except (ValueError,TypeError): return self.send(400,{'error':'Invalid recovery request'})
   except Exception: return self.send(503,{'error':'Recovery storage unavailable; use server-owner assistance'})
  if route!='/api/infer': return self.send(404,{'error':'Not found'})
  if not DECODERS.acquire(False): return self.send(429,{'error':'Two uploads already decoding; retry later'})
  path=None; admitted=False
  try:
   if self.headers.get_all('Transfer-Encoding',[]): raise ValueError('Chunked uploads are not supported')
   lengths=self.headers.get_all('Content-Length',[])
   if len(lengths)!=1 or not re.fullmatch('[0-9]+',lengths[0]): raise ValueError('One valid Content-Length required')
   length=int(lengths[0])
   if not 0<length<=MAX_BODY: return self.send(413,{'error':'Request exceeds 5 MB image + 64 KB form limit'})
   content_type=self.headers.get('Content-Type','')
   if len(self.headers.get_all('Content-Type',[]))!=1 or not content_type.startswith('multipart/form-data;'): raise ValueError('multipart/form-data required')
   body=self.read_body(length)
   if len(body)!=length: raise ValueError('Incomplete request body')
   message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
   if not message.is_multipart(): raise ValueError('Invalid multipart request')
   fields={}; parts=list(message.iter_parts())
   if len(parts)>10: raise ValueError('Too many form fields')
   for part in parts:
    name=part.get_param('name',header='content-disposition')
    if name not in {'methods','paid_consent','retention_consent','image'} or name in fields: raise ValueError('Unknown or duplicate form field')
    fields[name]=part.get_payload(decode=True)
    # Uploaded filename is ignored entirely. Only generated random paths are used.
   selected=json.loads(fields.get('methods',b'[]'))
   if not isinstance(selected,list) or not selected or len(selected)>16 or any(not isinstance(m,str) for m in selected) or len(set(selected))!=len(selected): raise ValueError('Choose 1–16 unique methods')
   for name in ('paid_consent','retention_consent'):
    if fields.get(name,b'false') not in {b'true',b'false'}: raise ValueError(name+' must be true or false')
   consent=fields.get('paid_consent',b'false')==b'true'; retention=fields.get('retention_consent',b'false')==b'true'
   methods={m['id']:m for m in REGISTRY.methods()}
   for method in selected:
    if method not in methods or methods[method]['status']!='available': return self.send(409,{'error':'Method unavailable: '+method})
    if methods[method].get('paid') and not consent: return self.send(403,{'error':'Explicit paid consent required'})
   raw=fields.get('image',b''); canonical=validate_image(raw)
   key=secrets.token_hex(16); provenance={m:REGISTRY.provenance(m) for m in selected}
   path=RUNTIME/(key+'.png')
   with path.open('xb') as f: os.chmod(path,0o600); f.write(canonical)
   record={'job_id':key,'selected':selected,'paid_methods':{m:bool(methods[m].get('paid')) for m in selected},'paid_consent':consent,'method_statuses':{m:'queued' for m in selected},'results':{},'source_sha256':hashlib.sha256(raw).hexdigest(),'image_sha256':hashlib.sha256(canonical).hexdigest(),'retention_consent':retention,'consent_at':now() if retention else None,'feedback':None,'method_provenance':provenance,'restart_upload_policy':'Ephemeral bytes until completed private retention. Worker loss requires re-upload; known async IDs only may resume polling.'}
   capability=recovery_capability(self.auth.id) if retention else None
   issued=JOB_STORE.create_queued(owner_key(self.auth.id),record,recovery_parts(capability)[1] if capability else None); admitted=True
   response={'job_id':key,'status':'queued','restart_upload_policy':record['restart_upload_policy']}
   if issued: response.update(recovery_token=capability,save_recovery_token=True)
   return self.send(202,response)
  except ImageTooLarge as exc: return self.send(413,{'error':str(exc)})
  except (ValueError,TypeError,KeyError): return self.send(400,{'error':'Invalid upload; JPEG/PNG/WebP, 5 MB source and normalized, 16 MP maximum'})
  except StoreError as exc: return self.send(exc.status,{'error':str(exc)})
  except (TimeoutError,socket.timeout): return self.send(408,{'error':'Upload read deadline exceeded'})
  except Exception: return self.send(503,{'error':'Upload/storage unavailable; refresh known job before retrying'})
  finally:
   if path and not admitted: path.unlink(missing_ok=True)
   DECODERS.release()
 def feedback_write(self,key,action):
  try:
   data=self.json_body(); owner=owner_key(self.auth.id)
   if action=='label':
    if set(data)!={'label','note','expected_revision'}: raise FeedbackError('label, note and expected_revision required')
    result=FEEDBACK.label(key,owner,data['label'],data['note'],data['expected_revision'])
   else:
    if data: raise FeedbackError('Revoke body must be an empty object')
    result=FEEDBACK.revoke(key,owner)
   return self.send(200,result)
  except FeedbackError as exc: return self.send(exc.status,{'error':str(exc)})
  except (ValueError,TypeError,KeyError): return self.send(400,{'error':'Invalid feedback request'})
  except Exception: return self.send(503,{'error':'Private feedback storage unavailable; refresh exact annotation before retrying'})

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=int(os.environ.get('TYRE_PORT','8765'))); parser.add_argument('--bind',default=os.environ.get('TYRE_BIND','127.0.0.1')); args=parser.parse_args()
 configure(args.port,args.bind)
 server=ThreadingHTTPServer((args.bind,args.port),Handler); server.daemon_threads=True
 print('Tyre server initialized; '+('public HTTPS ingress required' if PUBLIC else 'loopback only'),flush=True)
 try: server.serve_forever()
 finally:
  STOP.set(); server.server_close()
  if WORKER_THREAD: WORKER_THREAD.join(15)
  # Process-private ephemeral scratch only, never shared storage.
  for p in RUNTIME.glob('*.png'): p.unlink(missing_ok=True)
  try: RUNTIME.rmdir()
  except OSError: pass
if __name__=='__main__': main()
