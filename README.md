# Tyre Wear Indicator
A small visual-condition research pilot, not tread-depth measurement or roadworthiness certification.
Private images, credentials, production journals and giant checkpoints are not in Git.

## Layout
```
classifiers/
  resnet18/ mobilenet/ clip/
  luna-responses/ luna-decisions/ gpt41-finetuned/ azure-automl/
    README.md  train.py  test.py  weights/  results/  config*.json
  common/                  shared dataset, preprocessing, grouped heads, costs and provider contracts
dashboard/
  backend/                 real HTTP application and storage/security contracts
  frontend/                HTML, CSS and JavaScript
infra/                     hosting configuration examples and deployment boundaries only
tools/  tests/             repository audits and offline regression checks
docs/                      global dataset, cost, reproduction and experiment index
```

## Methods
| Method | All22 correct | Shared9 correct | Shared9 bad called good | State |
|---|---|---|---|---|
| [ResNet18](classifiers/resnet18/README.md) | 12/22 | 4/9 | 1/5 | Frozen features + saved final head |
| [MobileNet](classifiers/mobilenet/README.md) | 14/22 | 4/9 | 1/5 | Frozen features + saved final head |
| [CLIP](classifiers/clip/README.md) | 18/22 | 7/9 | 2/5 | Frozen image embeddings + saved final head |
| [Luna Responses](classifiers/luna-responses/README.md) | 19/22 | 8/9 | 0/5 | Prompted, not trained |
| [Luna Decisions](classifiers/luna-decisions/README.md) | 11/22 | 3/9 | 3/5 | Typed questions, not trained |
| [GPT-4.1 fine-tuned](classifiers/gpt41-finetuned/README.md) | Not evaluated | 9/9 | 0/5 | Hosted checkpoint, actual13 training inputs |
| [Azure AutoML](classifiers/azure-automl/README.md) | Unrun | Unrun | Unknown | Prepared10/3/9, GPU quota blocked |

22 unique binary photos (13bad/9good), two review examples and one duplicate excluded from local fitting.
Grouped OOF uses train/test13/9,15/7,16/6. Final local serving heads fit all22: OOF is not their independent test.
The shared9 were repeatedly explored development photos, not9 verified independent tyres or a prospective holdout.
Luna submitted25/scored22; GPT actually trained13 (6bad/5good/2review), then evaluated the separate9.
Diagnostic good never grants automatic safety clearance. [Dataset](docs/DATA_EXCLUDED.md) · [Experiment index](docs/EXPERIMENTS.md).

## Run from anywhere
Python3 on Linux/WSL. [Dependencies and verification](docs/VERIFICATION.md) · [Refactor evidence](docs/REFACTOR_VERIFICATION.md).
```
python classifiers/clip/train.py --help
python classifiers/clip/test.py --help
python classifiers/clip/test.py --benchmark
python /absolute/path/to/repo/classifiers/clip/test.py --benchmark
python classifiers/clip/test.py --image /private/authorized.jpg
```
--benchmark scores frozen saved predictions; --image really encodes a new image or reports missing weights/approval.
Small trained scaler/coefficients are included as non-executable numeric JSON, verified against trusted original heads.
Large public backbones need explicit pinned acquisition: see each weights/README.md. No implicit download on --help or inference.
Training refuses to overwrite included weights; use --out classifiers/clip/weights/generated for a new private experiment.
Luna train.py validates configuration, never fake-fits. GPT/AutoML train.py prepare genuine private inputs without automatic paid upload.

## Dashboard and checks
```
python -m dashboard.backend.server --bind 127.0.0.1 --port 8765 --read-only
python tools/check_publication.py
python tools/check_publication.py --staged
python tools/run_offline_tests.py
```
[Dashboard setup](dashboard/README.md) · [Hosting boundaries](infra/README.md) · [Costs](docs/COSTS.md).
No deployment or paid inference is performed by this refactor. The curated application is not the private deployed production image.

[Security](SECURITY.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Migration/source mapping](export-manifest.json).
Tiny provisional labels, suspected groups, pretraining overlap and repeated model selection limit generalization. No100% real-world claim.
