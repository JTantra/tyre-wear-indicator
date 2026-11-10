# Frozen next-encoder comparison — 2026-11-10

This append-only experiment does not change the original six-score graphic, original saved heads or frozen benchmark publications. Two representations actually ran: existing CLIP and new SigLIP2. DINOv3 was requested but unrun (HTTP401 gate), never substituted with DINOv2.

## Measured OOF evidence

| Candidate / procedure | Full22 correct | Balanced accuracy | False-good / bad13 | Common9 correct | Common balanced | Common false-good / bad5 |
|---|---:|---:|---:|---:|---:|---:|
| clip_224 | 18/22 (81.82%) | 81.20% | 2/13 | 7/9 (77.78%) | 80.00% | 2/5 |
| siglip2_224 | 15/22 (68.18%) | 61.11% | 0/13 | 5/9 (55.56%) | 50.00% | 0/5 |
| nested_architecture | 17/22 (77.27%) | 72.22% | 0/13 | 5/9 (55.56%) | 50.00% | 0/5 |
| DINOv3-S/16 | unrun | null | null | unrun | null | null |

Confusion labels are bad, good, review (rows truth, columns prediction); full matrices and class precision/recall/F1/coverage in [comparison.json](comparison.json). All forced-binary coverage is100%; no missing/error cells for executed methods. Operational clearance is0%; all predictions require expert review. Anonymous unique photo rows are in [per-image.json](per-image.json); no source/group/split identifiers. Two source-review photos have six separate outer-fold-head diagnostics per method (2 × 3), not binary scoring or abstention accuracy. Final all22 smoke is separate.

CLIP regenerated features match all24 original cached vectors bit-for-bit, checkpoint/canonical SHA256s match, and all22 OOF predicted labels match; original18/22 and7/9 reproduced exactly. SigLIP2 has fewer false-good errors here but misses7/9 good photos; it did not beat CLIP on overall/balanced accuracy. The joint selector chose SigLIP2 in some training folds and scores17/22; do not report the retrospectively best fixed score as the selector score.

## Frozen method and failure preservation

The 22 provisional binary labels are 13 bad / 9 good across 16 suspected similarity groups, only three good groups, not confirmed tyre IDs. Two source-review photos never enter binary fitting or selection. The original deduplicated three grouped outer folds (13/9, 15/7, 16/6 train/test) are unchanged. Each binary photo gets exactly one OOF prediction. Six heads = balanced logistic or LinearSVC × C 0.01/0.1/1, train-only StandardScaler; grouped inner2 chooses balanced accuracy, first-grid ties. Final serving heads fit all22 separately and are not OOF evidence. Repeated archive exploration and retrospective fixed-model ranking are optimistic; no population/safety claim.

[Public-safe plan](plan.json) includes the private frozen-plan digest, pre-execution timestamp, exact code/version/checkpoint hashes, pooling, preprocessing and grid. First run stopped at the numeric serialization parity assertion: pinned sklearn casts scaler statistics to input dtype. Only serialization was corrected; initial plan/logs/results remain privately preserved, and all OOF predictions stayed identical. A new run-v2 was frozen before rerunning. Full reproduction regenerated both backbones from original photos and pinned local checkpoint bytes, all features bit-identically, all OOF margins/predictions/metrics/trials exactly, then refit/reloaded final numeric heads. Protected49818 original files remained unchanged. This broad snapshot includes original runtime dependency files as well as photos/artifacts; it is not a photo count.

DINO pooling was predeclared official CLS (no pooling search); SigLIP2 uses the official attention-pooled image features, no extra L2 normalization. Model-specific official normalization/resample, aspect-preserving padding to224; common canonical JPEG pipeline unchanged. No manual crops, enhancement, holdout tuning or image uploads.

## Runtime and cost

Measured on Intel(R) Core(TM) Ultra 9 185H, WSL2 Linux, Python3.12.3, torch4 threads, batch4. Full environment versions in [requirements-lock.txt](requirements-lock.txt). Optional packages were installed in a new private venv; existing CPU torch/sklearn/Pillow were reused read-only. Original runtime/SDK locks were not modified. Fresh full reinstall not verified.

| Stage | CLIP | SigLIP2 |
|---|---:|---:|
| First local backbone load, seconds (not proven cold disk cache) | 2.295793 | 0.813697 |
| Cached backbone reload, seconds | 0.779329 | 0.790586 |
| Warm batch-amortized feature seconds/photo, median3 batches24 | 0.030515 | 0.114312 |
| Numeric head reload, seconds | 0.000859 | 0.000704 |
| Real one-image backbone median4, seconds | 0.054587 | 0.130411 |
| Canonical + adaptation median4, seconds | 0.053681 | 0.049258 |
| Head-only median4, seconds | 0.000185 | 0.000216 |

SigLIP2 public acquisition took29.033s including card/config checks; checkpoint transfer28.276s, 1500800904 bytes. CLIP used existing pinned local weights, no new download. DINO access preflight took0.274s, HTTP401 empty body; no inference timing. Shared canonical preprocessing24:1.498s; nested searches:0.205s; final full22 selection/fitting/export:0.118s. Successful run walltime45.920s excludes earlier downloads/install/failed run; full reproduction31.338s. Individual stage medians are not a measured end-to-end request. Separate raw timing arrays and sample counts are in comparison.json.

Per-image API fee: zero local calls. Compute/electricity/hosting economic cost: unknown, not free and no Azure tariff inferred. No GPU, paid service, production calls, deployment, LFS or external push performed.

## Exact command forms

```sh
python -m classifiers.common.foundation_next_experiment --data-root "$PRIVATE_DATA" --out "$OUTPUT" --weights "$WEIGHTS" --clip-weights "$CLIP_CACHE" --access-dir "$ACCESS"
python -m classifiers.common.foundation_next_experiment --data-root "$PRIVATE_DATA" --out "$OUTPUT" --weights "$WEIGHTS" --clip-weights "$CLIP_CACHE" --access-dir "$ACCESS" --reproduce
python classifiers/siglip2/test.py --benchmark
python classifiers/dinov3/test.py --benchmark
python classifiers/siglip2/test.py --image "$PHOTO" --weights "$WEIGHTS/siglip2"
python tools/run_offline_tests.py
python tools/check_publication.py --staged
```

Inputs are external operator-owned paths; never stage originals, review annotations, private crosswalks, features, raw logs, auth metadata or checkpoints. Per-method train defaults to that family only. Actual SigLIP2 method-specific training and real-image inference were also exercised; DINO training fails closed from saved blocked status without network. Original85 offline cases remain. Combined suite: 102 discovered, 94 passed, 8 explicit private/AutoML skips, zero failures/errors; all17 new tests passed. Tests separately exercise numeric SVC/logistic, privacy, new CLI help and anonymous arithmetic. See [verification](VERIFICATION.md).

## DINO next action

Owner independently reviews custom terms and requests approval at https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m, then authorizes use of an already approved existing HF login. No credentials in chat/repository and no automatic terms acceptance. After approval, create a newly versioned output and rerun the frozen three-candidate protocol; current comparison remains a two-candidate result.

## Limitations

Provisional source labels, only three good similarity groups and repeated archive exploration. Group identity and pretraining overlap unknown. Retrospective candidate ranking is selection-optimistic, and inner folds cannot make the reused tiny archive an independent prospective test. No population accuracy, calibrated margin, certified safe tyre or millimetre measurement claims.
