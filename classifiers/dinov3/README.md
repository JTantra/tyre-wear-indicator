# DINOv3-S/16 224

## Status

UNRUN / access blocked. Standard Hugging Face existing-auth request returned GatedRepoError HTTP 401 (empty response body). No approved local checkpoint was available; no custom terms accepted, account created or gate bypass attempted. This is DINOv3, not the historical DINOv2 result. Inference cannot be exercised without approved weights.

## Model and checkpoint provenance

Model `facebook/dinov3-vits16-pretrain-lvd1689m` at `114c1379950215c8b35dfcd4e90a5c251dde0d32`. DINOv3 custom gated terms; no acceptance authorized. See [checkpoint pins](weights/pretrained.json) and the [official model portal](https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m). No remote model code. Large public weights are not in Git/LFS.

## Inputs and transforms

Shared EXIF transpose → RGB → aspect-preserving maximum-side1024 (no upscale) → metadata-stripped JPEG95 subsampling0 → decode. Full frame is aspect-preservingly padded to224 square with mean-channel color; no tread crops or enhancement. Predeclared official CLS pooler_output, no result-driven CLS/patch pooling search. Official mean/std and processor resample must come from the approved pinned checkpoint; this path was not executed.

## Training, validation and test

The 22 provisional binary labels are 13 bad / 9 good across 16 suspected similarity groups, only three good groups, not confirmed tyre IDs. Two source-review photos never enter binary fitting or selection. The original deduplicated three grouped outer folds (13/9, 15/7, 16/6 train/test) are unchanged. Each binary photo gets exactly one OOF prediction. Six heads = balanced logistic or LinearSVC × C 0.01/0.1/1, train-only StandardScaler; grouped inner2 chooses balanced accuracy, first-grid ties. Final serving heads fit all22 separately and are not OOF evidence. Repeated archive exploration and retrospective fixed-model ranking are optimistic; no population/safety claim.


## Metrics and coverage

No accuracy, confusion, latency, features or head. Nullable metrics are not zero-accuracy results. See the completed two-available-candidate comparison; it is not a three-model benchmark.

[Machine-readable summary](results/summary.json), [anonymous predictions](results/per-image.json), and [append-only comparison](../../docs/foundation-next-2026-11-10/README.md).

## Prompt or questions

None. Frozen local image encoder plus small supervised linear head; no provider image requests.

## Cost and runtime

Local CPU: no API image fee or new cloud spend. Economic electricity/compute/hosting cost unknown, not zero. Measured download, first local load, cached reload, warm batch, single-image and head timings are separate in the comparison; first local load is not proven disk-cache-cold loading. DINO has no measured inference.

## Reproduce and expected artifacts

Python3.12.3, isolated environment; see [tested dependency snapshot](../../docs/foundation-next-2026-11-10/requirements-lock.txt). Help imports no heavy ML packages. Run from repository root; all data/checkpoint/output folders below are operator-supplied external private locations. Output must not exist.

```sh
python classifiers/dinov3/train.py --help
python classifiers/dinov3/test.py --benchmark
python classifiers/dinov3/weights/fetch.py --out "$WEIGHTS/dinov3"
# Explicit --execute is required for download. DINO: first independently obtain approved access/terms; this script never accepts them.
# Place acquired dinov3-access.json in "$ACCESS"; weights in "$WEIGHTS/dinov3".
python classifiers/dinov3/train.py --data-root "$PRIVATE_DATA" --out "$OUTPUT" --weights "$WEIGHTS" --access-dir "$ACCESS"
python classifiers/dinov3/test.py --image "$PHOTO" --weights "$WEIGHTS/dinov3"
```

The experiment requires the existing private manifest/splits/preprocessing-baseline schema (not distributed); it verifies source hashes and deduplication. Expected private outputs: frozen plan/hash receipt before execution, cached features, every nested trial/selection, OOF predictions, diagnostics, final numeric heads, timing, protected-source hashes and real reload smoke. `--reproduce` regenerates features and refits searches against the frozen identity. DINO without approved access writes `unrun.json` and fails rather than training a substitute.

## Limitations and rights

Provisional labels and tiny sample, repeated development, unknown pretraining overlap/background shortcuts. No validated visibility/OOD gate or calibrated clearance confidence. Human expert review mandatory; no millimetre measurement or roadworthiness certification. Model-card license is provenance, not legal clearance; DINO custom terms require the owner to independently review/request access. No photos, features, identifiers, private paths, raw logs or secrets belong in Git.
