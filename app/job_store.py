"""Private Blob job/recovery consistency boundary; local fixture is NOT cloud durable.

A lease + ETag catalogue is authoritative, including complete job documents. Validated
jobs/<id>.json projections are conditionally written before catalogue publication.
Unknown provider submission is never retried. No image bytes are persisted here.
"""
import copy, hashlib, importlib, json, os, re, secrets, threading, time
from contextlib import contextmanager
from contextvars import ContextVar

_PROVIDER_CONTEXT=ContextVar('tyre_provider_job_context',default=None)
@contextmanager
def provider_context(value):
    token=_PROVIDER_CONTEXT.set(value)
    try: yield
    finally: _PROVIDER_CONTEXT.reset(token)
def current_provider_context():
    """Parent infer/poll adapters may read the current synchronous checkpoint/deadline context."""
    value=_PROVIDER_CONTEXT.get()
    if value is None: raise StoreError('No active fenced provider context')
    return dict(value)

FORMAT='tyre-private-blob-jobs/1'
ACTIVE={'queued','running'}
TERMINAL={'complete','partial','error','interrupted'}
MAX_METADATA=16*1024*1024

def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def empty_state(): return {'format':FORMAT,'generation':0,'jobs':{},'recovery':{},'attempts':{},'outbox':[]}
def envelope(state):
    raw=encode(state)
    if len(raw)>MAX_METADATA: raise StoreError('Private job metadata capacity exceeded')
    return encode({'sha256':hashlib.sha256(raw).hexdigest(),'state':state})
def decode(raw):
    if not raw or len(raw)>MAX_METADATA+256: raise StoreError('Private job metadata unavailable')
    p=json.loads(raw); s=p['state']
    if s['format']!=FORMAT or p['sha256']!=hashlib.sha256(encode(s)).hexdigest(): raise StoreError('Private job metadata integrity mismatch')
    if not isinstance(s['jobs'],dict) or any(not re.fullmatch('[a-f0-9]{32}',k) or j['job_id']!=k or j['status'] not in ACTIVE|TERMINAL for k,j in s['jobs'].items()): raise StoreError('Invalid job schema')
    return s

class StoreError(RuntimeError):
    def __init__(self,message='Private job storage unavailable',status=503): super().__init__(message); self.status=status

class LeaseGuard:
    def __init__(self,lease):
        self.lease=lease; self.failed=False; self.deadline=time.monotonic()+45
        self.lock=threading.Lock(); self.stop=threading.Event()
        self.thread=threading.Thread(target=self.renew,daemon=True); self.thread.start()
    def renew(self):
        while not self.stop.wait(15):
            try: self.check(renew=True)
            except Exception: self.failed=True; return
    def check(self,renew=False):
        with self.lock:
            if self.failed or time.monotonic()>=self.deadline: raise StoreError('Job lease lost; needs owner reconciliation')
            if renew:
                try: self.lease.renew(timeout=10); self.deadline=time.monotonic()+45
                except Exception: self.failed=True; raise StoreError('Job lease lost; needs owner reconciliation') from None
    def close(self):
        self.stop.set(); self.thread.join(12)
        try: self.lease.release(timeout=10)
        except Exception: pass

class AzureTransport:
    def __init__(self,account,container,client_id):
        from azure.identity import ManagedIdentityCredential
        from azure.storage.blob import ContainerClient
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceNotFoundError,ResourceExistsError
        from azure.core.pipeline.transport import RequestsTransport
        if not re.fullmatch(r'https://[a-z0-9]{3,24}\.blob\.core\.windows\.net',account) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]',container) or not client_id: raise RuntimeError('Explicit private Blob account/container/MI required')
        self.match=MatchConditions.IfNotModified; self.missing=ResourceNotFoundError; self.exists=ResourceExistsError
        self.client=ContainerClient(account,container,credential=ManagedIdentityCredential(client_id=client_id),retry_total=0,transport=RequestsTransport(connection_timeout=5,read_timeout=10))
        if self.client.get_container_properties(timeout=10).get('public_access'): raise RuntimeError('Job container must be private')
    def read(self,name):
        try:
            s=self.client.get_blob_client(name).download_blob(max_concurrency=1,timeout=10)
            return s.readall(),s.properties.etag
        except self.missing: return None,None
    def create(self,name,data):
        try: self.client.get_blob_client(name).upload_blob(data,overwrite=False,timeout=10)
        except self.exists: pass
        raw,etag=self.read(name)
        if raw!=data: raise StoreError('Private object collision')
        return etag
    def replace(self,name,data,etag,lease):
        self.client.get_blob_client(name).upload_blob(data,overwrite=True,etag=etag,match_condition=self.match,lease=lease,timeout=10)
        raw,fresh=self.read(name)
        if raw!=data: raise StoreError('Private job write readback mismatch')
        return fresh
    def names(self,prefix): return [b.name for b in self.client.list_blobs(name_starts_with=prefix,timeout=10)]
    def acquire(self,name): return self.client.get_blob_client(name).acquire_lease(lease_duration=60,timeout=10)
    def delete(self,name,lease):
        raw,etag=self.read(name)
        if raw is not None: self.client.get_blob_client(name).delete_blob(etag=etag,match_condition=self.match,lease=lease,timeout=10)
        if self.read(name)[0] is not None: raise StoreError('Private job deletion readback mismatch')

class BlobJobStore:
    durable=True
    def __init__(self,transport,prefix='public-server-v4/'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9/_-]{0,100}/',prefix) or '..' in prefix: raise RuntimeError('Invalid jobs namespace')
        self.transport=transport; self.prefix=prefix; self.catalogue=prefix+'catalogue.json'; self.worker_name=prefix+'worker.json'
        self.health()
    @classmethod
    def initialize(cls,transport,prefix='public-server-v4/'):
        # Owner provisioning only; server factory never creates missing namespace.
        if transport.read(prefix+'catalogue.json')[0] is None: transport.create(prefix+'catalogue.json',envelope(empty_state()))
        if transport.read(prefix+'worker.json')[0] is None: transport.create(prefix+'worker.json',encode({'format':FORMAT,'purpose':'global-worker-fence'}))
        return cls(transport,prefix)
    def health(self):
        with self.transaction() as s: decode(envelope(s))
        if self.transport.read(self.worker_name)[0]!=encode({'format':FORMAT,'purpose':'global-worker-fence'}): raise StoreError('Worker namespace unavailable')
        return True
    @contextmanager
    def transaction(self,validator=None):
        lease=None; end=time.monotonic()+5
        while lease is None:
            try: lease=self.transport.acquire(self.catalogue)
            except Exception as exc:
                if getattr(exc,'status_code',None)!=409 or time.monotonic()>end: raise StoreError() from None
                time.sleep(.02)
        guard=LeaseGuard(lease)
        try:
            raw,etag=self.transport.read(self.catalogue); state=decode(raw); before=copy.deepcopy(state)
            yield state
            guard.check(renew=True)
            if state!=before:
                state['generation']+=1
                # Conditional per-job projections, with object lease fencing late SDK writes.
                for k,j in state['jobs'].items():
                    if j==before['jobs'].get(k): continue
                    name=self.prefix+'jobs/'+k+'.json'; data=encode(j); old,oldetag=self.transport.read(name)
                    if old is None: self.transport.create(name,data)
                    else:
                        obj=self.transport.acquire(name)
                        try: guard.check(); self.transport.replace(name,data,oldetag,obj)
                        finally:
                            try: obj.release(timeout=10)
                            except Exception: pass
                guard.check(renew=True)
                if validator: validator()
                self.transport.replace(self.catalogue,envelope(state),etag,lease)
        except StoreError: raise
        except Exception: raise StoreError() from None
        finally: guard.close()
    def _sweep(self,s):
        t=time.time()
        for k,j in list(s['jobs'].items()):
            if j['status'] in ACTIVE and (j.get('heartbeat_until',j['submitted_at']+60)<t or j['expires_at']<t):
                # Known async job IDs may ONLY resume poll, never submit. All other work lost.
                pending=[m for m,v in j['results'].items() if j['expires_at']>t and v.get('status')=='pending' and v.get('provider_job_id') and j.get('deadlines',{}).get(m,0)>t]
                if not pending:
                    j.update(status='interrupted',error='Worker/upload lost; re-upload. Uncertain paid submission needs owner reconciliation.',needs_owner_reconcile=bool(j.get('submission_intents')),revision=j['revision']+1,worker_token=None,expires_at=t+3600)
                    j['method_statuses']={m:('interrupted' if v in {'queued','running','pending'} else v) for m,v in j['method_statuses'].items()}
                else: j['worker_token']=None
            if j['expires_at']<t and j['status'] not in ACTIVE:
                s['outbox'].append(self.prefix+'jobs/'+k+'.json'); del s['jobs'][k]
        s['recovery']={k:v for k,v in s['recovery'].items() if v['expires_at']>t}
        s['attempts']={k:v for k,v in s['attempts'].items() if v['until']>t}
    def reconcile(self):
        with self.transaction() as s:
            self._sweep(s)
            refs={self.prefix+'jobs/'+k+'.json' for k in s['jobs']}
            for name in self.transport.names(self.prefix+'jobs/'):
                if re.fullmatch(re.escape(self.prefix)+r'jobs/[a-f0-9]{32}\.json',name) and name not in refs and name not in s['outbox']:
                    s['outbox'].append(name)
        # Deletion outbox is durable before deletion, never image objects in this namespace.
        with self.transaction() as s:
            for name in list(s['outbox']):
                if name in {self.prefix+'jobs/'+k+'.json' for k in s['jobs']}:
                    s['outbox'].remove(name); continue
                if not re.fullmatch(re.escape(self.prefix)+r'jobs/[a-f0-9]{32}\.json',name): raise StoreError('Invalid deletion outbox')
                if self.transport.read(name)[0] is not None:
                    lease=self.transport.acquire(name)
                    try: self.transport.delete(name,lease)
                    finally:
                        try: lease.release(timeout=10)
                        except Exception: pass
                s['outbox'].remove(name)
    def create_queued(self,owner,record,recovery=None):
        if not re.fullmatch('[a-f0-9]{64}',owner): raise StoreError('Stable owner hash required',400)
        key=record['job_id']
        if not re.fullmatch('[a-f0-9]{32}',key): raise StoreError('Invalid job ID',400)
        with self.transaction() as s:
            self._sweep(s)
            if sum(j['status'] in ACTIVE for j in s['jobs'].values())>=4 or len(s['jobs'])>=100: raise StoreError('Deployment queue full; retry later',429)
            if key in s['jobs']: raise StoreError('Job ID collision',409)
            t=time.time(); j=copy.deepcopy(record)
            j.update(owner=owner,status='queued',revision=0,submitted_at=t,expires_at=t+24*3600,heartbeat_until=t+60,worker_token=None,deadlines={},submission_intents={},outbox=[])
            s['jobs'][key]=j
            issued=False
            if recovery and owner not in s['recovery']:
                if len(s['recovery'])>=10000: raise StoreError('Recovery capacity exceeded',429)
                s['recovery'][owner]={'hash':recovery,'expires_at':t+365*86400}; issued=True
        return issued
    def get(self,key,owner):
        if not re.fullmatch('[a-f0-9]{32}',key): raise StoreError('Job not found',404)
        with self.transaction() as s:
            j=s['jobs'].get(key)
            if not j or j['owner']!=owner or j['expires_at']<=time.time(): raise StoreError('Job not found',404)
            return copy.deepcopy(j)
    def touch_uploads(self,keys):
        keys={k for k in keys if re.fullmatch('[a-f0-9]{32}',k)}
        with self.transaction() as s:
            for k in keys:
                j=s['jobs'].get(k)
                if j and j['status']=='queued' and j['expires_at']>time.time():
                    j['heartbeat_until']=time.time()+45; j['revision']+=1
    def candidates(self):
        with self.transaction() as s: self._sweep(s); return [copy.deepcopy(j) for j in s['jobs'].values() if j['status'] in ACTIVE]
    @contextmanager
    def worker(self,key):
        try: lease=self.transport.acquire(self.worker_name)
        except Exception as exc:
            if getattr(exc,'status_code',None)==409: yield None; return
            raise StoreError() from None
        guard=LeaseGuard(lease); token=secrets.token_hex(32)
        try:
            with self.transaction(validator=lambda:guard.check(renew=True)) as s:
                self._sweep(s); j=s['jobs'].get(key)
                if not j or j['status'] not in ACTIVE: yield_none=True
                else:
                    j.update(worker_token=token,heartbeat_until=time.time()+45,status='running',revision=j['revision']+1); yield_none=False
            if yield_none: yield None
            else: yield (token,guard)
        finally: guard.close()
    def update(self,key,token,guard,**changes):
        guard.check()
        with self.transaction(validator=lambda:guard.check(renew=True)) as s:
            guard.check(renew=True); j=s['jobs'].get(key)
            if not j or j['worker_token']!=token: raise StoreError('Worker fence changed; needs owner reconciliation')
            j.update(copy.deepcopy(changes)); j['revision']+=1; j['heartbeat_until']=time.time()+45
            if j['status'] in TERMINAL: j['worker_token']=None; j['expires_at']=time.time()+3600
    def issue_recovery(self,owner,new_hash):
        # Authenticated stable owner can replace a lost capability; never annotation-ID proof.
        with self.transaction() as s:
            self._sweep(s)
            if owner not in s['recovery']: raise StoreError('No consented recovery identity; use owner assistance',404)
            a=s['attempts'].setdefault('issue-'+owner,{'count':0,'until':time.time()+60}); a['count']+=1
            if a['count']>5: raise StoreError('Recovery issuance rate limit',429)
            s['recovery'][owner]={'hash':new_hash,'expires_at':time.time()+365*86400}
    def recover(self,owner,old_hash,new_hash,bootstrap):
        # Persist attempt limits even on wrong token. At most 5 attempts/min/bootstrap and 60 globally.
        error=None
        with self.transaction() as s:
            self._sweep(s); t=time.time()
            for key,limit in [('global',60),(bootstrap,5)]:
                a=s['attempts'].setdefault(key,{'count':0,'until':t+60}); a['count']+=1
                if a['count']>limit: error=StoreError('Recovery rate limit',429)
            record=s['recovery'].get(owner)
            import hmac
            if not error and (not record or not hmac.compare_digest(record['hash'],old_hash)): error=StoreError('Recovery capability not valid',403)
            if not error: s['recovery'][owner]={'hash':new_hash,'expires_at':t+365*86400}
        if error: raise error

class MemoryJobStore(BlobJobStore):
    """Loopback-only isolated state, explicitly not restart/cloud durable."""
    durable=False
    def __init__(self):
        self.state=empty_state(); self.lock=threading.RLock(); self.worker_lock=threading.Lock()
    @contextmanager
    def transaction(self,validator=None):
        with self.lock:
            state=copy.deepcopy(self.state)
            yield state
            if validator: validator()
            self.state=state
    def health(self): return True
    def reconcile(self):
        with self.transaction() as s: self._sweep(s); s['outbox']=[]
    @contextmanager
    def worker(self,key):
        if not self.worker_lock.acquire(False): yield None; return
        class LocalGuard:
            def check(self,renew=False): pass
        token=secrets.token_hex(32)
        try:
            with self.transaction() as s:
                j=s['jobs'].get(key)
                if not j or j['status'] not in ACTIVE: token=None
                else: j.update(worker_token=token,status='running',heartbeat_until=time.time()+45)
            yield (token,LocalGuard()) if token else None
        finally: self.worker_lock.release()

def create_store(public=False):
    factory=os.environ.get('TYRE_JOB_FACTORY','')
    if not factory:
        if public or os.environ.get('TYRE_REQUIRE_DURABLE_JOBS')=='1': raise RuntimeError('Explicit durable JobStore factory required')
        return MemoryJobStore()
    try:
        module,name=factory.split(':'); store=getattr(importlib.import_module(module),name)()
        for method in ('health','reconcile','create_queued','get','touch_uploads','candidates','worker','update','recover','issue_recovery'):
            if not callable(getattr(store,method,None)): raise RuntimeError('Incomplete JobStore factory')
        if (public or os.environ.get('TYRE_REQUIRE_DURABLE_JOBS')=='1') and getattr(store,'durable',False) is not True: raise RuntimeError('Durable JobStore required')
        store.health(); return store
    except RuntimeError: raise
    except Exception: raise RuntimeError('Private JobStore configuration unavailable') from None

def create_azure_store():
    return BlobJobStore(AzureTransport(os.environ['TYRE_JOB_ACCOUNT_URL'],os.environ['TYRE_JOB_CONTAINER'],os.environ['TYRE_JOB_CLIENT_ID']),os.environ.get('TYRE_JOB_PREFIX','public-server-v4/'))
