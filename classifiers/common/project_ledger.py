"""Project-wide append-only attempt ledger; historical two-probe receipt stays intact.

One exclusive project lease spans a runner invocation, including waits. Reservations
are fsynced before HTTP; unresolved reservations or a stale lease fail closed. Never
remove a stale lease without auditing both journals. Atomic append is protected by
this lease, and each event is chained to the preceding event to detect edits.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from email.utils import parsedate_to_datetime


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_events(path):
    if not path.exists(): return []
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    previous = None
    for row in rows:
        body = {k:v for k,v in row.items() if k != 'hash'}
        if row.get('previous') != previous or row.get('hash') != digest(body):
            raise ValueError('Project ledger chain corrupted')
        previous = row['hash']
    return rows


def durable_append(path, row):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, allow_nan=False)+'\n'); f.flush(); os.fsync(f.fileno())
    # Persist a newly created journal's directory entry on the Linux workspace.
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)


class ProjectLedger:
    def __init__(self, root, limit=200, clock=time):
        self.root, self.limit, self.clock = Path(root), min(200, limit), clock
        if not 1 <= self.limit <= 200: raise ValueError('Invalid project request limit')
        self.dir = self.root/'infra'; self.path = self.dir/'benchmark-attempts.jsonl'
        self.lock = self.dir/'benchmark-project.lock'

    def __enter__(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            receipt = self.dir/'experiment-request-ledger.json'
            self.seed = json.loads(receipt.read_text()) if receipt.exists() else {'limit':200, 'attempts':[]}
            if not isinstance(self.seed.get('attempts'), list): raise ValueError('Invalid historical receipt')
            # Missing production receipt is never silently treated as a fresh budget.
            if not receipt.exists() and (self.root/'infra/benchmark-endpoints.json').exists():
                raise ValueError('Missing historical project receipt')
            self.limit = min(self.limit, self.seed.get('limit', 200))
            seed_hash = digest(self.seed)
            self.rows = read_events(self.path)
            if not self.rows: self.add({'event':'seed', 'receipt_hash':seed_hash, 'historical_attempts':len(self.seed['attempts']), 'limit':self.limit})
            elif self.rows[0].get('receipt_hash') != seed_hash: raise ValueError('Historical receipt changed; reconcile explicitly')
            previous_limit=min((r['limit'] for r in self.rows if 'limit' in r),default=200)
            if self.limit<previous_limit: self.add({'event':'budget_limit','limit':self.limit})
            self.limit=min(self.limit,previous_limit)
            return self
        except BaseException:
            self.lock.unlink(); raise

    def __exit__(self, *exc): self.lock.unlink()

    def add(self, event):
        row = dict(event, previous=self.rows[-1]['hash'] if self.rows else None)
        row['hash'] = digest(row); durable_append(self.path, row); self.rows.append(row)

    @property
    def count(self): return len(self.seed['attempts']) + sum(r['event']=='attempt' for r in self.rows)

    @property
    def blocked(self):
        attempts = {r['id'] for r in self.rows if r['event']=='attempt'}
        answered = {r['id'] for r in self.rows if r['event']=='response'}
        reconciled={h for r in self.rows if r['event']=='owner_authorized_reconciliation' for h in r['halt_hashes']}
        return bool(attempts-answered) or any((r['event']=='halt' or r.get('halt_reason') or r.get('status') in (401,403)) and r['hash'] not in reconciled for r in self.rows)

    def reconcile_auth(self, approval_messages, reason):
        raise ValueError('Historical authorization reconciliation is unavailable in the curated export; fresh owner review is required')

    def reserve(self, event, deployment, rpm=1, tpm=1000):
        if self.blocked: raise ValueError('Project unresolved attempt or global halt; no silent resume')
        if self.count >= self.limit: return None
        if rpm <= 0 or tpm <= 0: raise ValueError('Invalid deployment pacing')
        now = self.clock.time(); ready = now
        for row in self.rows:
            if row.get('deployment_key') != deployment: continue
            if row['event']=='attempt':
                ready = max(ready, row['time']+max(60.0/rpm, 60.0*(row.get('actual_tokens') or 0)/tpm))
            if row['event']=='response':
                ready = max(ready, row.get('retry_not_before', 0))
                # Actual usage (not token reservation) determines throughput pacing.
                ready = max(ready, row['request_time'] + 60.0*(row.get('actual_tokens') or 0)/tpm)
        if ready > now: self.clock.sleep(ready-now)
        attempt_id = uuid.uuid4().hex
        self.add(dict(event, event='attempt', id=attempt_id, deployment_key=deployment, time=self.clock.time()))
        return attempt_id

    def response(self, attempt_id, **event):
        if any(r['event']=='response' and r['id']==attempt_id for r in self.rows):
            raise ValueError('Duplicate project response')
        request = next(r for r in self.rows if r['event']=='attempt' and r['id']==attempt_id)
        self.add(dict(event, event='response', id=attempt_id, deployment_key=request['deployment_key'], request_time=request['time']))


def retry_deadline(headers, now):
    value = headers.get('Retry-After')
    if value is None: return now
    try: seconds = float(value)
    except (ValueError, TypeError):
        try: return max(now, parsedate_to_datetime(value).timestamp())
        except (ValueError, TypeError, OverflowError): raise ValueError('Invalid Retry-After; fail closed')
    if not 0 <= seconds < float('inf'): raise ValueError('Invalid Retry-After')
    return now+seconds
