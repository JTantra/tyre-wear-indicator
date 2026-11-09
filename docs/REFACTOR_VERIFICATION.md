# Structural refactor verification

Baseline:38f5d37d14aafa494fb944a82f14c9ea2d1bf1d4. Local dedicated branch refactor/classifier-layout-t_e21de02f.
No push, cloud calls, production deployment, private-photo rescoring or training was performed.

## Real checks
- `python tools/run_offline_tests.py`:85 cases, zero failures/errors,8 preserved excluded-private-evidence skips.
  This retains all69 baseline cases and adds16 migration/privacy/CLI/dashboard behaviors.
- All14 train.py/test.py --help commands ran from repository root and arbitrary CWD.
  The test actively rejects ML/cloud package imports during --help; no implicit model download.
- All6 `python classifiers/<method>/test.py --benchmark` commands score the frozen rows.
  Shared9 correct4/4/7/8/3/9 and false-good1/1/2/0/3/0 are unchanged.
  Eight original anonymous result/partition/provenance files remain byte-identical.
- `python tools/check_publication.py` checks file allowlist/digests, numeric/cost truth, Python syntax,
  Markdown links and negative secret/image/provider/binary fixtures.
  `python tools/check_publication.py --staged` additionally reads exact Git index blobs, not status text.
- Real documented `python -m dashboard.backend.server --bind 127.0.0.1 --port <free-loopback-port> --read-only`
  started and served HTML/JS/CSS, readiness,7-method benchmark and128-row API, ephemeral HttpOnly session.
  Unauthenticated owned-record endpoints returned404; read-only inference POST returned403. No cloud.

## Real local3-model smoke
`python tools/smoke_local_models.py --trusted-original-root /private/trusted/original`
uses a generated striped320x240 image, existing hash-verified public backbones and the trusted original final heads.
It compares original predictors with the new numeric inference and the actual CLI from arbitrary CWD.
This is engineering parity, NOT a benchmark/newscore or private-photo inference.

- resnet18: original/new value 0.37516684017771545/0.37516684017771545; absolute error 0.0; same diagnostic class; real CLI equality.
- mobilenet: original/new value 0.6055737374811311/0.6055737374811311; absolute error 0.0; same diagnostic class; real CLI equality.
- clip: original/new value -1.2175884182526573/-1.2175884182526573; absolute error 0.0; same diagnostic class; real CLI equality.

The numeric exporter retains scaler/coefficients, not samples/labels/paths or pickle metadata.
Trusted original Pipeline and scaler/logistic attributes were inspected. Each of the3 final heads fit22.
Original joblib digests/byte sizes and exact safe numeric exports are in classifiers/common/owned-heads.json.
No arbitrary joblib is accepted by runtime. The numeric calculation retains archived sklearn1.9 float32
operand casts, verified by a regression test and zero-error real-image engineering parity.

## Provenance and unavailable capabilities
69034 previously snapshotted original operational files checked, zero changed. The full private path list is not exported.
Production Azure was not changed or re-read; this is local source preservation, not an invented live receipt.
Native azure.ai.ml and mlflow are not installed in the exercised local interpreter. AutoML payload/partition
contracts run offline, but native submission/scoring requires those dependencies plus private inputs,
selection receipt and fresh scoped approval; historical GPU-quota blockage remains unrun, score=null.
Luna and GPT fresh API inference were deliberately not executed: fresh operator approval, credentials,
ledger and genuinely configured deployment are required. GPT actual13-input preparation is real source,
not an automatic paid upload or a fabricated hosted checkpoint. Large public acquisition is pinned but
no download was needed for this verification. All original8 private-evidence skips remain explicit.

Historical broad model comparison code is co-located as method experiment.py, not train.py's default.
The split/head hyperparameters and benchmark rows are unchanged. Path-rewritten source hashes differ;
the manifest records baseline old-to-new hashes and treatment, never falsely claims unchanged original code.

Next: fresh independent Ops review and authorized private repository publication; no production release.
