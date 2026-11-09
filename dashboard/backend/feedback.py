"""Private feedback repository. No HTTP admin or public image listing.

External stores implement FeedbackStore as one consistency boundary, not merely
an object upload callback. In production TYRE_REQUIRE_DURABLE_FEEDBACK=1 fails
closed unless an explicitly configured adapter declares durable=True.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import argparse, csv, hashlib, importlib, io, json, os, re, secrets, shutil, sqlite3, threading
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

SCHEMA_VERSION = 'tyre-feedback/1'
RUBRIC_VERSION = 'visual-good-bad-review/1'
CONSENT_VERSION = 'private-training-review/1'
NORMALIZATION_VERSION = 'exif-rgb-metadata-free-png/1'
MAX_NOTE = 1000
LABELS = {'good', 'bad', 'review'}

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def owner_key(session_id):
    return digest(session_id.encode())

class FeedbackError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

@runtime_checkable
class FeedbackStore(Protocol):
    durable: bool
    def inspect(self, annotation_id: str) -> dict: ...
    def list_owned(self, owner: str) -> list[dict]: ...
    def retain(self, record: dict, image: bytes) -> dict: ...
    def get(self, annotation_id: str, owner: str) -> dict: ...
    def label(self, annotation_id: str, owner: str, label: str, note: str, expected_revision: int) -> dict: ...
    def revoke(self, annotation_id: str, owner: str) -> dict: ...
    def owner_revoke(self, annotation_id: str, actor: str) -> dict: ...
    def review(self, annotation_id: str, reviewer: str, decision: str, expected_revision: int, note: str = '') -> dict: ...
    def export(self, destination: Path, version: str) -> dict: ...

def validate_label(label, note, revision):
    if not isinstance(label, str) or label not in LABELS:
        raise FeedbackError('Label must be good, bad or review')
    if not isinstance(note, str) or len(note) > MAX_NOTE:
        raise FeedbackError('Note must be at most 1000 characters')
    if type(revision) is not int or revision < 0:
        raise FeedbackError('expected_revision must be a nonnegative integer')

class SQLiteFeedbackStore:
    """Local private single-volume implementation; never cloud-durable by default.

All cooperating processes serialize metadata/object mutations with BEGIN IMMEDIATE.
Images are content-addressed; no user filename or path is accepted. Atomic rename
precedes metadata commit. A crash can leave an unreferenced object (reconciled at
startup), never a committed reference to an unwritten object. Revocation uses a
persisted deletion outbox and retryable object GC before reporting success.
"""
    durable = False
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.objects = self.root / 'objects'
        self.objects.mkdir(exist_ok=True, mode=0o700)
        self.db = self.root / 'feedback.sqlite3'
        with closing(self.connect()) as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS annotations(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
              document TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS revisions(annotation_id TEXT NOT NULL, revision INTEGER NOT NULL,
              document TEXT NOT NULL, PRIMARY KEY(annotation_id, revision));
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, annotation_id TEXT,
              event TEXT NOT NULL, at TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deletions(hash TEXT PRIMARY KEY);
            ''')
        os.chmod(self.root, 0o700)
        os.chmod(self.objects, 0o700)
        os.chmod(self.db, 0o600)
        self.reconcile()

    def connect(self):
        c = sqlite3.connect(self.db, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA synchronous=FULL')
        c.execute('PRAGMA secure_delete=ON')
        return c

    @contextmanager
    def transaction(self):
        c = self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def event(self, c, aid, event, detail):
        c.execute('INSERT INTO audit(annotation_id,event,at,detail) VALUES(?,?,?,?)',
                  (aid, event, now(), json.dumps(detail, allow_nan=False)))

    def row(self, c, aid, owner=None):
        r = c.execute('SELECT * FROM annotations WHERE id=?', (aid,)).fetchone()
        if not r or (owner is not None and r['owner'] != owner):
            raise FeedbackError('Retained annotation not found', 404)
        return r

    def projection(self, r):
        if r['revoked']:
            return {'annotation_id': r['id'], 'retained': False, 'revoked': True,
                    'revision': r['revision'], 'review_status': 'withdrawn', 'training_eligible': False}
        d = json.loads(r['document'])
        return {'annotation_id': r['id'], 'retained': True, 'revoked': False,
                'revision': r['revision'], 'label': d.get('user_label'), 'note': d.get('user_note', ''),
                'review_status': d['review_status'], 'training_eligible': d['review_status'] == 'approved',
                'image_sha256': d['image_sha256'], 'consent_at': d['consent_at'], 'schema_version': SCHEMA_VERSION}

    def list_owned(self, owner):
        with closing(self.connect()) as c:
            rows = c.execute('SELECT * FROM annotations WHERE owner=? AND revoked=0 ORDER BY id', (owner,)).fetchall()
            return [self.projection(r) for r in rows]

    def inspect(self, annotation_id):
        """Owner-only full provenance view. Never called by public HTTP handlers."""
        with closing(self.connect()) as c:
            r = self.row(c, annotation_id)
            d = json.loads(r['document'])
            d.pop('owner', None)
            return dict(d, annotation_id=annotation_id, revoked=bool(r['revoked']), revision=r['revision'])

    def get(self, annotation_id, owner):
        with closing(self.connect()) as c:
            return self.projection(self.row(c, annotation_id, owner))

    def referenced(self, c, hash_):
        for r in c.execute('SELECT document FROM annotations WHERE revoked=0'):
            if json.loads(r['document'])['image_sha256'] == hash_:
                return True
        return False

    def gc(self, c):
        for r in c.execute('SELECT hash FROM deletions').fetchall():
            if not self.referenced(c, r['hash']):
                (self.objects / (r['hash'] + '.png')).unlink(missing_ok=True)
            c.execute('DELETE FROM deletions WHERE hash=?', (r['hash'],))

    def reconcile(self):
        with self.transaction() as c:
            self.gc(c)
            for p in self.objects.iterdir():
                if p.name.endswith('.tmp') or (re.fullmatch('[a-f0-9]{64}\\.png', p.name) and not self.referenced(c, p.stem)):
                    p.unlink(missing_ok=True)

    def retain(self, record, image):
        if not record.get('consent_at') or record.get('consent_version') != CONSENT_VERSION:
            raise FeedbackError('Explicit retention consent required', 403)
        if digest(image) != record.get('image_sha256'):
            raise FeedbackError('Retained image integrity mismatch')
        aid = record['annotation_id']
        if not re.fullmatch('[a-f0-9]{32}', aid):
            raise FeedbackError('Invalid annotation ID')
        d = dict(record, schema_version=SCHEMA_VERSION, review_status='pending', user_label=None,
                 label_provenance='anonymous-session-unverified', revision=0)
        with self.transaction() as c:
            target = self.objects / (d['image_sha256'] + '.png')
            if target.exists():
                if digest(target.read_bytes()) != d['image_sha256']:
                    raise FeedbackError('Stored object integrity mismatch', 503)
            else:
                temp = self.objects / (secrets.token_hex(16) + '.tmp')
                try:
                    with temp.open('xb') as f:
                        os.chmod(temp, 0o600)
                        f.write(image); f.flush(); os.fsync(f.fileno())
                    os.replace(temp, target)
                    if os.name == 'posix':
                        fd = os.open(self.objects, os.O_RDONLY | os.O_DIRECTORY)
                        try: os.fsync(fd)
                        finally: os.close(fd)
                finally:
                    temp.unlink(missing_ok=True)
            c.execute('INSERT INTO annotations(id,owner,document) VALUES(?,?,?)',
                      (aid, record['owner'], json.dumps(d, allow_nan=False)))
            self.event(c, aid, 'retained', {'image_sha256': d['image_sha256'], 'consent_version': CONSENT_VERSION})
        return self.get(aid, record['owner'])

    def label(self, annotation_id, owner, label, note, expected_revision):
        validate_label(label, note, expected_revision)
        with self.transaction() as c:
            r = self.row(c, annotation_id, owner)
            if r['revoked']:
                raise FeedbackError('Consent withdrawn; labeling is disabled', 403)
            if r['revision'] != expected_revision:
                raise FeedbackError('Revision conflict; refresh before editing', 409)
            d = json.loads(r['document'])
            rev = r['revision'] + 1
            d.update(user_label=label, user_note=note, label_at=now(), revision=rev,
                     review_status='pending', review=None, label_provenance='anonymous-session-unverified')
            serialized = json.dumps(d, allow_nan=False)
            c.execute('INSERT INTO revisions VALUES(?,?,?)', (annotation_id, rev, serialized))
            c.execute('UPDATE annotations SET document=?,revision=? WHERE id=?', (serialized, rev, annotation_id))
            self.event(c, annotation_id, 'label_revision', {'revision': rev})
        return self.get(annotation_id, owner)

    def revoke(self, annotation_id, owner):
        with self.transaction() as c:
            r = self.row(c, annotation_id, owner)
            if not r['revoked']:
                d = json.loads(r['document'])
                # Withdrawal erases all note/label/prediction revisions; minimal deletion audit survives.
                c.execute('DELETE FROM revisions WHERE annotation_id=?', (annotation_id,))
                c.execute('UPDATE annotations SET revoked=1,document=?,revision=revision+1 WHERE id=?',
                          (json.dumps({'withdrawn_at': now()}), annotation_id))
                c.execute('INSERT OR IGNORE INTO deletions VALUES(?)', (d['image_sha256'],))
                self.event(c, annotation_id, 'withdrawn', {'purged_revisions': True})
        # Separate committed outbox: failed deletion can be retried safely on restart or revoke.
        with self.transaction() as c:
            self.gc(c)
        return self.get(annotation_id, owner)

    def owner_revoke(self, annotation_id, actor):
        """Protected owner CLI deletion when the anonymous session has expired."""
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 100:
            raise FeedbackError('Named server-owner actor required')
        with self.transaction() as c:
            r = self.row(c, annotation_id)
            owner = r['owner']
            self.event(c, annotation_id, 'owner_withdrawal_requested', {'actor': actor})
        return self.revoke(annotation_id, owner)

    def review(self, annotation_id, reviewer, decision, expected_revision, note=''):
        if decision not in {'approved', 'rejected'} or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
            raise FeedbackError('Named reviewer and approved/rejected decision required')
        validate_label('review', note, expected_revision)
        with self.transaction() as c:
            r = self.row(c, annotation_id)
            d = json.loads(r['document'])
            if r['revoked'] or not d.get('user_label'):
                raise FeedbackError('Active consent and independent user label required', 403)
            if r['revision'] != expected_revision:
                raise FeedbackError('Revision conflict; inspect current annotation', 409)
            if decision == 'approved' and d['user_label'] not in {'good', 'bad'}:
                raise FeedbackError('Review-only labels cannot enter binary training')
            rev = r['revision'] + 1
            d.update(review_status=decision, revision=rev,
                     review={'reviewer': reviewer, 'decision': decision, 'note': note, 'at': now(),
                             'reviewed_label_revision': expected_revision})
            text = json.dumps(d, allow_nan=False)
            c.execute('INSERT INTO revisions VALUES(?,?,?)', (annotation_id, rev, text))
            c.execute('UPDATE annotations SET document=?,revision=? WHERE id=?', (text, rev, annotation_id))
            self.event(c, annotation_id, 'owner_review', {'reviewer': reviewer, 'decision': decision, 'revision': rev})
        return self.get(annotation_id, r['owner'])

    def export(self, destination, version):
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version):
            raise FeedbackError('Use an explicit safe dataset version')
        destination = Path(destination).resolve()
        if destination == self.root or self.root in destination.parents:
            raise FeedbackError('Export must be outside feedback storage')
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive directory creation prevents overwriting an immutable previous export.
        destination.mkdir(mode=0o700)
        try:
            with self.transaction() as c:
                docs = [json.loads(r['document']) for r in c.execute('SELECT document FROM annotations WHERE revoked=0 ORDER BY id')]
                docs = [d for d in docs if d['review_status'] == 'approved' and d.get('user_label') in {'good', 'bad'}]
                groups = {}
                for d in docs:
                    groups.setdefault(d['image_sha256'], set()).add(d['user_label'])
                conflicts = {h for h, labels in groups.items() if len(labels) != 1}
                docs = [d for d in docs if d['image_sha256'] not in conflicts]
                (destination / 'images').mkdir(mode=0o700)
                hashes = {}
                for d in docs:
                    h = d['image_sha256']
                    data = (self.objects / (h + '.png')).read_bytes()
                    if digest(data) != h:
                        raise FeedbackError('Export image integrity mismatch', 503)
                    (destination / 'images' / (h + '.png')).write_bytes(data)
                    d.pop('owner', None)
                    d.update(dataset_version=version, split='unassigned', duplicate_group=h,
                             image='images/' + h + '.png')
                jsonl = ''.join(json.dumps(d, allow_nan=False, sort_keys=True) + '\n' for d in docs)
                (destination / 'labels.jsonl').write_text(jsonl, encoding='utf-8')
                with (destination / 'labels.csv').open('w', newline='', encoding='utf-8') as f:
                    fields = ['annotation_id', 'image_sha256', 'source_sha256', 'user_label', 'revision', 'duplicate_group', 'image', 'dataset_version', 'split']
                    writer = csv.DictWriter(f, fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(docs)
                for p in sorted(destination.rglob('*')):
                    if p.is_file():
                        os.chmod(p, 0o600)
                        hashes[str(p.relative_to(destination))] = {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
                manifest = {'schema_version': SCHEMA_VERSION, 'dataset_version': version, 'created_at': now(),
                            'annotation_count': len(docs), 'unique_images': len({d['image_sha256'] for d in docs}),
                            'excluded_conflicting_groups': sorted(conflicts), 'files': hashes,
                            'qualification': 'Reviewed volunteer labels, not certified truth. Group related views before splitting; never modify benchmark holdout.',
                            'withdrawal': 'Point-in-time private snapshot. Operator must remove withdrawn annotations from prior exports/training inputs.'}
                (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
                os.chmod(destination / 'manifest.json', 0o600)
                self.event(c, None, 'approved_export', {'version': version, 'annotation_ids': [d['annotation_id'] for d in docs]})
            return manifest
        except BaseException:
            shutil.rmtree(destination)
            raise

def create_store(root=None):
    factory = os.environ.get('TYRE_FEEDBACK_FACTORY', '')
    if factory:
        module, separator, attr = factory.partition(':')
        if not separator or not module or not attr:
            raise RuntimeError('TYRE_FEEDBACK_FACTORY must be module:callable')
        store = getattr(importlib.import_module(module), attr)()
        if not isinstance(store, FeedbackStore):
            raise RuntimeError('Feedback adapter does not implement the complete storage contract')
    else:
        store = SQLiteFeedbackStore(root or os.environ.get('TYRE_FEEDBACK_ROOT', str(Path(__file__).resolve().parent / 'runtime_feedback')))
    if os.environ.get('TYRE_REQUIRE_DURABLE_FEEDBACK') == '1' and store.durable is not True:
        raise RuntimeError('Production retention requires a verified durable feedback adapter; local filesystem is not cloud durability')
    return store

def main():
    p = argparse.ArgumentParser(description='Server-owner private feedback review/export; never exposed through HTTP')
    sub = p.add_subparsers(dest='action', required=True)
    inspect = sub.add_parser('inspect'); inspect.add_argument('annotation_id')
    delete = sub.add_parser('delete'); delete.add_argument('annotation_id'); delete.add_argument('--actor', required=True)
    review = sub.add_parser('review'); review.add_argument('annotation_id'); review.add_argument('--reviewer', required=True)
    review.add_argument('--decision', choices=['approved', 'rejected'], required=True)
    review.add_argument('--expected-revision', type=int, required=True); review.add_argument('--note', default='')
    export = sub.add_parser('export'); export.add_argument('--destination', type=Path, required=True); export.add_argument('--version', required=True)
    args = p.parse_args(); store = create_store()
    if args.action == 'inspect':
        result = store.inspect(args.annotation_id)
    elif args.action == 'delete':
        result = store.owner_revoke(args.annotation_id, args.actor)
    elif args.action == 'review':
        result = store.review(args.annotation_id, args.reviewer, args.decision, args.expected_revision, args.note)
    else:
        result = store.export(args.destination, args.version)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
