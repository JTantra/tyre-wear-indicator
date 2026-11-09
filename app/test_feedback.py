"""Isolated feedback tests; synthetic images are storage/security fixtures, never benchmarks."""
import hashlib, io, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app.feedback import SQLiteFeedbackStore, create_store, CONSENT_VERSION, FeedbackError

class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = SQLiteFeedbackStore(self.root / 'private')
        b = io.BytesIO(); Image.new('RGB', (8, 8)).save(b, 'PNG'); self.image = b.getvalue()
        self.record = {'annotation_id': 'a'*32, 'owner': 'owner1', 'image_sha256': hashlib.sha256(self.image).hexdigest(),
                       'source_sha256': 'f'*64, 'consent_at': '2026-01-01T00:00:00+00:00', 'consent_version': CONSENT_VERSION,
                       'predictions': {'fixture': {'status': 'complete'}}, 'normalization_version': 'test-fixture'}
    def tearDown(self):
        self.temp.cleanup()
    def retain(self, aid='a'*32, owner='owner1'):
        return self.store.retain(dict(self.record, annotation_id=aid, owner=owner), self.image)
    def test_no_consent(self):
        with self.assertRaises(FeedbackError): self.store.retain(dict(self.record, consent_at=None), self.image)
        self.assertFalse(list(self.store.objects.glob('*.png')))
    def test_ownership_and_revision(self):
        self.retain()
        with self.assertRaises(FeedbackError) as cm: self.store.label('a'*32, 'owner2', 'good', '', 0)
        self.assertEqual(cm.exception.status, 404)
        self.store.label('a'*32, 'owner1', 'bad', 'Independent assessment', 0)
        self.store.label('a'*32, 'owner1', 'good', 'Correction', 1)
        with self.assertRaises(FeedbackError) as cm: self.store.label('a'*32, 'owner1', 'bad', '', 1)
        self.assertEqual(cm.exception.status, 409)
        with self.store.connect() as c:
            rows = c.execute('SELECT document FROM revisions ORDER BY revision').fetchall()
        self.assertEqual([json.loads(r[0])['user_label'] for r in rows], ['bad', 'good'])
        self.assertEqual(self.store.get('a'*32, 'owner1')['review_status'], 'pending')
    def test_note_label_validation(self):
        self.retain()
        for label, note, rev in [('invalid', '', 0), ('good', 'x'*1001, 0), ('bad', '', True)]:
            with self.assertRaises(FeedbackError): self.store.label('a'*32, 'owner1', label, note, rev)
    def test_dedup_withdrawal_and_purge(self):
        self.retain(); self.retain('b'*32, 'owner2')
        self.assertEqual(len(list(self.store.objects.glob('*.png'))), 1)
        self.store.label('a'*32, 'owner1', 'bad', 'delete this private note', 0)
        self.store.revoke('a'*32, 'owner1')
        self.assertEqual(len(list(self.store.objects.glob('*.png'))), 1)
        with self.store.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM revisions').fetchone()[0], 0)
            self.assertNotIn('delete this private note', c.execute('SELECT document FROM annotations WHERE id=?', ('a'*32,)).fetchone()[0])
        with self.assertRaises(FeedbackError): self.store.label('a'*32, 'owner1', 'bad', '', 2)
        self.store.revoke('b'*32, 'owner2')
        self.assertFalse(list(self.store.objects.glob('*.png')))
        self.assertFalse(self.store.revoke('b'*32, 'owner2')['retained'])
    def test_approved_only_export_and_edit_resets(self):
        self.retain(); self.retain('b'*32, 'owner2')
        self.store.label('a'*32, 'owner1', 'bad', '', 0)
        self.store.label('b'*32, 'owner2', 'bad', '', 0)
        self.assertEqual(self.store.export(self.root/'empty', 'v0')['annotation_count'], 0)
        with self.assertRaises(FeedbackError): self.store.review('a'*32, 'owner', 'approved', 0)
        self.store.review('a'*32, 'named-owner', 'approved', 1)
        report = self.store.export(self.root/'v1', 'v1')
        self.assertEqual(report['annotation_count'], 1)
        for name, integrity in report['files'].items():
            self.assertEqual(hashlib.sha256((self.root/'v1'/name).read_bytes()).hexdigest(), integrity['sha256'])
        self.assertNotIn('"owner"', (self.root/'v1/labels.jsonl').read_text())
        with self.assertRaises(FileExistsError): self.store.export(self.root/'v1', 'v1')
        self.store.label('a'*32, 'owner1', 'good', '', 2)
        self.assertEqual(self.store.export(self.root/'v2', 'v2')['annotation_count'], 0)
    def test_conflicting_duplicate_groups_excluded(self):
        self.retain(); self.retain('b'*32, 'owner2')
        for aid, owner, label in [('a'*32, 'owner1', 'bad'), ('b'*32, 'owner2', 'good')]:
            self.store.label(aid, owner, label, '', 0); self.store.review(aid, 'named-owner', 'approved', 1)
        report = self.store.export(self.root/'conflict', 'v1')
        self.assertEqual(report['annotation_count'], 0)
        self.assertEqual(len(report['excluded_conflicting_groups']), 1)
    def test_review_cannot_be_binary_training(self):
        self.retain(); self.store.label('a'*32, 'owner1', 'review', '', 0)
        with self.assertRaises(FeedbackError): self.store.review('a'*32, 'named-owner', 'approved', 1)
    def test_reload_and_durable_fail_closed(self):
        self.retain()
        other = SQLiteFeedbackStore(self.root/'private')
        self.assertTrue(other.get('a'*32, 'owner1')['retained'])
        with patch.dict(os.environ, {'TYRE_REQUIRE_DURABLE_FEEDBACK':'1', 'TYRE_FEEDBACK_FACTORY':''}):
            with self.assertRaises(RuntimeError): create_store(self.root/'private')
    def test_owned_listing_and_owner_inspection(self):
        self.retain(); self.retain('b'*32, 'owner2')
        self.assertEqual([r['annotation_id'] for r in self.store.list_owned('owner1')], ['a'*32])
        self.assertNotIn('owner', self.store.inspect('a'*32))
        self.store.revoke('a'*32, 'owner1')
        self.assertEqual(self.store.list_owned('owner1'), [])
    def test_durable_factory_full_contract(self):
        import types, sys
        module = types.ModuleType('test_feedback_adapter')
        class VerifiedAdapter(SQLiteFeedbackStore):
            # Contract-only local adapter fixture, not an Azure durability claim.
            durable = True
        module.factory = lambda: VerifiedAdapter(self.root/'private')
        with patch.dict(sys.modules, {'test_feedback_adapter': module}), patch.dict(os.environ,
                {'TYRE_FEEDBACK_FACTORY':'test_feedback_adapter:factory', 'TYRE_REQUIRE_DURABLE_FEEDBACK':'1'}):
            adapter = create_store()
            self.assertTrue(adapter.durable)
            self.retain()
            self.assertEqual(adapter.list_owned('owner1')[0]['annotation_id'], 'a'*32)
        module.factory = lambda: types.SimpleNamespace(durable=True, retain=lambda *args: None)
        with patch.dict(sys.modules, {'test_feedback_adapter': module}), patch.dict(os.environ,
                {'TYRE_FEEDBACK_FACTORY':'test_feedback_adapter:factory', 'TYRE_REQUIRE_DURABLE_FEEDBACK':'1'}):
            with self.assertRaises(RuntimeError): create_store()
    def test_named_owner_deletion_after_session_loss(self):
        self.retain(); self.store.label('a'*32, 'owner1', 'bad', 'private note', 0)
        reloaded = SQLiteFeedbackStore(self.root/'private')
        with self.assertRaises(FeedbackError): reloaded.owner_revoke('a'*32, '')
        self.assertFalse(reloaded.owner_revoke('a'*32, 'server-owner')['retained'])
        self.assertFalse(list(reloaded.objects.glob('*.png')))
        self.assertEqual(reloaded.inspect('a'*32)['revoked'], True)
    def test_integrity(self):
        with self.assertRaises(FeedbackError): self.store.retain(dict(self.record, image_sha256='0'*64), self.image)
    def test_deletion_outbox_retry(self):
        self.retain()
        original = self.store.gc
        with patch.object(self.store, 'gc', side_effect=OSError('transient delete failure')):
            with self.assertRaises(OSError): self.store.revoke('a'*32, 'owner1')
        self.assertFalse(self.store.get('a'*32, 'owner1')['retained'])
        self.store.reconcile()
        self.assertFalse(list(self.store.objects.glob('*.png')))

if __name__ == '__main__': unittest.main(verbosity=2)
