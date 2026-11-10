# SigLIP2 Base/16 224

## Status

Completed genuine local CPU benchmark, reproduced from original photos and reloaded pinned weights. Final head is numeric logistic C=0.01, fit on all22, not held-out accuracy.

## Model and checkpoint provenance

Model `google/siglip2-base-patch16-224` at `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`. Apache-2.0 official pinned model card. See [checkpoint pins](weights/pretrained.json) and the [official model portal](https://huggingface.co/google/siglip2-base-patch16-224). No remote model code. Large public weights are not in Git/LFS.

## Inputs and transforms

Shared EXIF transpose → RGB → aspect-preserving maximum-side1024 (no upscale) → metadata-stripped JPEG95 subsampling0 → decode. Full frame is aspect-preservingly padded to224 square with mean-channel color; no tread crops or enhancement. Pinned official SigLIP image_mean/std = 0.5/0.5 and BILINEAR resample. Official image features = vision attention pooled pooler_output; no extra normalization.

## Training, validation and test

The 22 provisional binary labels are 13 bad / 9 good across 16 suspected similarity groups, only three good groups, not confirmed tyre IDs. Two source-review photos never enter binary fitting or selection. The original deduplicated three grouped outer folds (13/9, 15/7, 16/6 train/test) are unchanged. Each binary photo gets exactly one OOF prediction. Six heads = balanced logistic or LinearSVC × C 0.01/0.1/1, train-only StandardScaler; grouped inner2 chooses balanced accuracy, first-grid ties. Final serving heads fit all22 separately and are not OOF evidence. Repeated archive exploration and retrospective fixed-model ranking are optimistic; no population/safety claim.


## Metrics and coverage

15/22 correct (68.18%), balanced accuracy 61.11%; confusion bad/good rows and columns [[13,0],[7,2]], false-good 0/13. Common9: 5/9 (55.56%), balanced 50%; [[5,0],[4,0]], false-good 0/5. Binary diagnostic coverage 22/22; operational clearance 0/22, all require review. Both review photos have three outer-head diagnostics, not scoring support.

[Machine-readable summary](results/summary.json), [anonymous predictions](results/per-image.json), and [append-only comparison](../../docs/foundation-next-2026-11-10/README.md).

## Prompt or questions

None. Frozen local image encoder plus small supervised linear head; no provider image requests.

## Cost and runtime

Local CPU: no API image fee or new cloud spend. Economic electricity/compute/hosting cost unknown, not zero. Measured download, first local load, cached reload, warm batch, single-image and head timings are separate in the comparison; first local load is not proven disk-cache-cold loading. DINO has no measured inference.

## Reproduce and expected artifacts

Python3.12.3, isolated environment; see [tested dependency snapshot](../../docs/foundation-next-2026-11-10/requirements-lock.txt). Help imports no heavy ML packages. Run from repository root; all data/checkpoint/output folders below are operator-supplied external private locations. Output must not exist.

```sh
python classifiers/siglip2/train.py --help
python classifiers/siglip2/test.py --benchmark
python classifiers/siglip2/weights/fetch.py --out "$WEIGHTS/siglip2"
# Explicit --execute is required for download. DINO: first independently obtain approved access/terms; this script never accepts them.
# Place acquired siglip2-access.json in "$ACCESS"; weights in "$WEIGHTS/siglip2".
python classifiers/siglip2/train.py --data-root "$PRIVATE_DATA" --out "$OUTPUT" --weights "$WEIGHTS" --access-dir "$ACCESS"
python classifiers/siglip2/test.py --image "$PHOTO" --weights "$WEIGHTS/siglip2"
```

The experiment requires the existing private manifest/splits/preprocessing-baseline schema (not distributed); it verifies source hashes and deduplication. Expected private outputs: frozen plan/hash receipt before execution, cached features, every nested trial/selection, OOF predictions, diagnostics, final numeric heads, timing, protected-source hashes and real reload smoke. `--reproduce` regenerates features and refits searches against the frozen identity. DINO without approved access writes `unrun.json` and fails rather than training a substitute.

## Limitations and rights

Provisional labels and tiny sample, repeated development, unknown pretraining overlap/background shortcuts. No validated visibility/OOD gate or calibrated clearance confidence. Human expert review mandatory; no millimetre measurement or roadworthiness certification. Model-card license is provenance, not legal clearance; DINO custom terms require the owner to independently review/request access. No photos, features, identifiers, private paths, raw logs or secrets belong in Git.
