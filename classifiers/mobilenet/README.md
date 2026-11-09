# MobileNetV3-Large

## Status
Implemented for real new uploads in the original password-gated pilot at the dated snapshot; exported local app includes inspected numeric heads and needs pinned public backbones. Refactor verification uses a synthetic generated image, not private-photo rescoring. Diagnostic condition is never automatic safety approval.

## Model and checkpoint provenance
torchvision MobileNet_V3_Large_Weights.IMAGENET1K_V2; frozen ImageNet backbone, classifier removed, 960-dimensional features. Train-only StandardScaler + balanced logistic/LinearSVC head grid C0.01/0.1/1, grouped inner2 balanced accuracy, first-grid tie. Final deployment was mobilenet_v3_large_full/logistic/C0.01, grouped full22 selection then refit; headline is the fixed MobileNet candidate OOF, not the nested architecture selector.

Public checkpoint: https://download.pytorch.org/models/mobilenet_v3_large-5c1a4163.pth . Exact observed dependencies, checkpoint digests and experiment wall times: [model provenance](results/model-provenance.json). Download on reproduction only; only inspected small numeric final heads are committed; no giant weights or pickle/joblib files are committed. Torchvision's BSD code notice and upstream ImageNet/weight rights are provenance, not commercial clearance. CLIP has separate research/deployment limitations below.

## Inputs and transforms
All methods first use [canonical preprocessing](../common/preprocessing.py): EXIF-transposed RGB, longest side at most1024 LANCZOS without upscale, JPEG quality95/subsampling0, metadata stripped, no contrast/sharpen/denoise. Canonical full-frame RGB JPEG, neutral BILINEAR letterbox224, ImageNet channel mean/std. Full frame retained. Other experiment candidates include EfficientNet full/grid and ResNet50; full-grid is a label-free four-quadrant diagnostic, not detected tyre ROI.

## Training, validation and test
22 unique binary photos:13 bad/9 good, two review inputs excluded from binary training and one duplicate removed. Three grouped outer train/test13/9,15/7,16/6; inner grouped2 on training only. No separate fixed validation set. Final head is refit on22 and its serving behavior is not independently scored by these OOF results. Suspected visual groups are not verified tyre IDs; repeated archive exploration and candidate ranking limit generalization.

## Metrics and coverage
All22: 14/22 correct, 3/13 bad called good, 22/22 binary coverage, 0 abstentions. Same9: 4/9 correct, 1/5 bad called good, 9/9 binary coverage. These are preliminary label-agreement counts, not safety performance. [Confusion matrices/accepted accuracy](results/summary.json) and [all anonymous prediction rows](results/per-image.json) preserve exact denominators. Forced-binary diagnostic coverage is not operational auto-clearance coverage, which is zero.

## Prompt or questions
None: image-feature classifier, not a prompted language model. Label targets train the small head only. Generic preprocessing/views never depend on annotation reasons.

## Cost and runtime
API fee0, not zero hosting cost. One recorded synthetic Azure smoke startup/load/request timing was 8.643395066000267seconds; n=1, not a cohort throughput estimate. Indicative active compute 0.000518603703960016020USD/image = seconds ×(2×0.000024+4×0.000003). This is already part of shared ACA compute, not an additional host per method. Local experiment runtime/version facts are in model-provenance.json. Local head-training/electricity/pretraining costs were not billed-measured. [Shared hosting/cost exclusions](../../docs/COSTS.md).

## Simple method commands
Run from repository root, or use an absolute script path from any working directory:
```sh
python classifiers/mobilenet/train.py --help
python classifiers/mobilenet/test.py --help
python classifiers/mobilenet/test.py --benchmark
python /absolute/path/to/repo/classifiers/mobilenet/test.py --benchmark
```
--benchmark evaluates [frozen saved rows](results/per-image.json), NOT image inference.
--image /absolute/path/to/authorized.jpg is genuine fresh-image inference or a clear unavailable reason; never a cached-row lookup.
See [weights and acquisition](weights/README.md). --help imports no ML/cloud packages and does not download, train or call a provider.

```sh
python classifiers/mobilenet/weights/fetch.py
python classifiers/mobilenet/test.py --image /private/authorized.jpg
python /absolute/path/to/repo/classifiers/mobilenet/test.py --image /private/authorized.jpg
python classifiers/mobilenet/train.py --data-root /private/original-archive --out classifiers/mobilenet/weights/generated
python classifiers/mobilenet/test.py --image /private/authorized.jpg --weights classifiers/mobilenet/weights/generated
```
Training consumes only this method's fixed representation, unchanged head grid/grouped folds.
Final heads default to this method's weights/; included head.json is never silently overwritten.
--out generates a new private experiment; inference --weights resolves that exact output directory.
The public backbone still resolves to the pinned same method default unless --backbone is given.
The historical broad candidate/architecture comparison below is preserved separately in experiment.py,
not called by train.py. Its protected-original hash assertions are archived provenance, not a claim that
path-rewritten source is byte-identical. No private training/rescoring was done to prove this migration.

## Reproduce and expected artifacts
After private acquisition and [setup](../../docs/DATA_EXCLUDED.md), historical source comparison (requires private inputs and explicit compute approval), not the simple train.py interface:

```sh
python classifiers/mobilenet/experiment.py
python tools/run_offline_tests.py
```

Real source: [classifiers/mobilenet/experiment.py](experiment.py). Expected local-only outputs: artifacts/custom-improvements/summary.json, predictions.json, selections.json, timing.json, head.joblib, deployment_config.json, mobilenet_v3_large_frozen.pt. Run the documented predecessor scripts first. These commands may download public checkpoints and consume local compute; they were not run during documentation preparation. The archived counts above were recomputed from saved source predictions; synthetic test output is not a retraining result. Default final head selection must match the recorded candidate; a different archive/package build is a new experiment, not silently equivalent.

## Limitations and rights
Tiny provisional photo labels, only three suspected good visual groups, unconfirmed independence, pretraining overlap unknown, tread-design/background shortcuts, no validated visibility/OOD gate, no tread-depth or roadworthiness inference. CLIP18/22 was a retrospectively ranked fixed candidate, not proof its nested selector is best. [Third-party rights](../../THIRD_PARTY_NOTICES.md) and [experimental history](../../docs/EXPERIMENTS.md).
