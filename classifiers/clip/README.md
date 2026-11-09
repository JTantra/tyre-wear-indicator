# CLIP ViT-B/32 at224

## Status
Implemented for real new uploads in the original password-gated pilot at the dated snapshot; exported local app includes inspected numeric heads and needs pinned public backbones. Refactor verification uses a synthetic generated image, not private-photo rescoring. Diagnostic condition is never automatic safety approval.

## Model and checkpoint provenance
Hugging Face openai/clip-vit-base-patch32 revision3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268. CLIPVisionModelWithProjection, frozen eval, projected L2-normalized image embedding. Train-only StandardScaler + balanced logistic/LinearSVC C0.01/0.1/1; grouped inner2 search. No text embeddings, zero-shot prompt classifier or backbone fine-tuning. Final serving head clip_224/logistic/C0.01 refit on22.

Public checkpoint: https://huggingface.co/openai/clip-vit-base-patch32/tree/3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268 . Exact observed dependencies, checkpoint digests and experiment wall times: [model provenance](results/model-provenance.json). Download on reproduction only; only inspected small numeric final heads are committed; no giant weights or pickle/joblib files are committed. Torchvision's BSD code notice and upstream ImageNet/weight rights are provenance, not commercial clearance. CLIP has separate research/deployment limitations below.

## Inputs and transforms
All methods first use [canonical preprocessing](../common/preprocessing.py): EXIF-transposed RGB, longest side at most1024 LANCZOS without upscale, JPEG quality95/subsampling0, metadata stripped, no contrast/sharpen/denoise. Canonical full-frame RGB JPEG; BICUBIC mean-color letterbox224 using pinned preprocessor mean/std.384 is an additional fixed-candidate experiment with positional interpolation; DINO224/336 are separate legacy candidates. No crop or enhancement.

## Training, validation and test
22 unique binary photos:13 bad/9 good, two review inputs excluded from binary training and one duplicate removed. Three grouped outer train/test13/9,15/7,16/6; inner grouped2 on training only. No separate fixed validation set. Final head is refit on22 and its serving behavior is not independently scored by these OOF results. Suspected visual groups are not verified tyre IDs; repeated archive exploration and candidate ranking limit generalization.

## Metrics and coverage
All22: 18/22 correct, 2/13 bad called good, 22/22 binary coverage, 0 abstentions. Same9: 7/9 correct, 2/5 bad called good, 9/9 binary coverage. These are preliminary label-agreement counts, not safety performance. [Confusion matrices/accepted accuracy](results/summary.json) and [all anonymous prediction rows](results/per-image.json) preserve exact denominators. Forced-binary diagnostic coverage is not operational auto-clearance coverage, which is zero.

## Prompt or questions
None: image-feature classifier, not a prompted language model. Label targets train the small head only. Generic preprocessing/views never depend on annotation reasons.

## Cost and runtime
API fee0, not zero hosting cost. One recorded synthetic Azure smoke startup/load/request timing was 11.430406352999853seconds; n=1, not a cohort throughput estimate. Indicative active compute 0.000685824381179991180USD/image = seconds ×(2×0.000024+4×0.000003). This is already part of shared ACA compute, not an additional host per method. Local experiment runtime/version facts are in model-provenance.json. Local head-training/electricity/pretraining costs were not billed-measured. [Shared hosting/cost exclusions](../../docs/COSTS.md).

## Simple method commands
Run from repository root, or use an absolute script path from any working directory:
```sh
python classifiers/clip/train.py --help
python classifiers/clip/test.py --help
python classifiers/clip/test.py --benchmark
python /absolute/path/to/repo/classifiers/clip/test.py --benchmark
```
--benchmark evaluates [frozen saved rows](results/per-image.json), NOT image inference.
--image /absolute/path/to/authorized.jpg is genuine fresh-image inference or a clear unavailable reason; never a cached-row lookup.
See [weights and acquisition](weights/README.md). --help imports no ML/cloud packages and does not download, train or call a provider.

```sh
python classifiers/clip/weights/fetch.py
python classifiers/clip/test.py --image /private/authorized.jpg
python /absolute/path/to/repo/classifiers/clip/test.py --image /private/authorized.jpg
python classifiers/clip/train.py --data-root /private/original-archive --out classifiers/clip/weights/generated
python classifiers/clip/test.py --image /private/authorized.jpg --weights classifiers/clip/weights/generated
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
python classifiers/clip/experiment.py
python tools/run_offline_tests.py
```

Real source: [classifiers/clip/experiment.py](experiment.py). Expected local-only outputs: artifacts/custom-v2/summary.json, predictions.json, selections.json, identity.json, timing.json, head.joblib, deployment_config.json, weights/clip/. Run the documented predecessor scripts first. These commands may download public checkpoints and consume local compute; they were not run during documentation preparation. The archived counts above were recomputed from saved source predictions; synthetic test output is not a retraining result. Default final head selection must match the recorded candidate; a different archive/package build is a new experiment, not silently equivalent.

## Limitations and rights
Tiny provisional photo labels, only three suspected good visual groups, unconfirmed independence, pretraining overlap unknown, tread-design/background shortcuts, no validated visibility/OOD gate, no tread-depth or roadworthiness inference. CLIP18/22 was a retrospectively ranked fixed candidate, not proof its nested selector is best. [Third-party rights](../../THIRD_PARTY_NOTICES.md) and [experimental history](../../docs/EXPERIMENTS.md).

CLIP model card warns against untested downstream deployment/general-purpose use and requires task-specific evaluation; upstream research intent and bias/robustness limitations apply. [Pinned card](weights/upstream/clip/README.md) is included. Upstream code MIT does not establish separate mirror-weight/data commercial clearance.
