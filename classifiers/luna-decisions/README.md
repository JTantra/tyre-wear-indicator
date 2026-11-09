# Luna Decisions — refined rubric v2

## Status
Benchmark-only in the original dated app snapshot, not removed and not claimed live. Same underlying model as the other Luna API, not a separately fine-tuned backbone. Fresh execution requires explicit cloud-send and spend approval, configured endpoint/deployment and authorized credential; publication checks never call the service.

## Model and checkpoint provenance
Azure OpenAI gpt-6-luna version2026-09-22, DataZoneStandard capacity20, US geography. Endpoint route /openai/v1/decisions; historical credential used the Cognitive Services audience. Service-owned checkpoint/internal image processing is unavailable and no model weights are exported. No dataset training/fine-tuning: generic frozen rubric only, no few-shot images or annotation reasons.

## Inputs and transforms
Same enhancement-free full-frame RGB canonical JPEG pipeline (EXIF orientation, max1024 no upscale, JPEG95/subsampling0). The service receives image bytes and a generic rubric; no filenames, truth, annotation reasons or customer IDs. Service-internal transforms are unknown. One Decisions request asks typed tread_visible and clear_damage predicates plus a good/bad/review condition choice. Direct returned three-way choice is the v2 headline; the predicates are retained, not converted into invented calibrated probabilities. Legacy gates/forced-binary/grouped-threshold alternatives are separate diagnostics, not the promoted result.

## Training, validation and test
No training or separate validation set for this prompted API experiment. Rubric was developed on the previously explored archive.25 physical cases =22 unique binary photos(13 bad/9 good)+2source-review+1duplicate repeatability case. Shared9 is local outer-fold0(5 bad/4 good), not an independent new holdout; local grouped13/9,15/7,16/6 counts describe local head experiments, not Luna training.

## Metrics and coverage
All22: 11/22 correct, 6/13 bad→good, 20/22 accepted binary outputs, 2 review abstentions. Shared9: 3/9 correct, 3/5 bad→good, 8/9 binary coverage and 1 abstention. Reviews stay in the accuracy denominator. Accepted accuracy and full confusion are separate in [metrics](results/summary.json). No operational safety approval, population-accuracy or unseen tyre validation claim.

## Prompt or questions
Exact full rubric and genuine payload/parser source: [refinement_v3.py](refinement_v3.py). [Question notes](QUESTIONS.md) quote both typed predicates and explain the condition summary; Responses observation fields are preserved. Legacy v1 generic single/multi questions: [benchmark_contract.py](../common/benchmark_contract.py). No hidden Human Review section was restored to the current [visual](../../docs/assets/twi-six-methods-costs.svg); scientific review limitations still apply.

## Cost and runtime
Actual25-case usage: input37354, output0, zero observed cache reads/writes. Retail mean USD0.0001643576–0.0003287152 per submitted image, not per22scored image or accepted classification. Formula(input×short0.11/long0.22 + output×short0.55/long0.825)/1million/25. Short/long context threshold remains unresolved; Decisions charging semantics partly unresolved; zero returned output is not proof of a zero-output-charge contract. HTTP timings in [safe per-case records](../common/results/cloud-rounds-per-case.json) exclude decode/auth/queue. Shared ACA frontend/backend costs are additional to API tokens. [Cost evidence/exclusions](../../docs/COSTS.md).

## Simple method commands
Run from repository root, or use an absolute script path from any working directory:
```sh
python classifiers/luna-decisions/train.py --help
python classifiers/luna-decisions/test.py --help
python classifiers/luna-decisions/test.py --benchmark
python /absolute/path/to/repo/classifiers/luna-decisions/test.py --benchmark
```
--benchmark evaluates [frozen saved rows](results/per-image.json), NOT image inference.
--image /absolute/path/to/authorized.jpg is genuine fresh-image inference or a clear unavailable reason; never a cached-row lookup.
See [weights and acquisition](weights/README.md). --help imports no ML/cloud packages and does not download, train or call a provider.

train.py is not trainable: validate with --validate-config config.example.json.
Fresh --image requires --execute, a private --config, --approval under repo/.cache, owner authorization and a fresh operator ledger.

## Reproduce and expected artifacts
Install base dependencies and privately recover the archive as in [data guide](../../docs/DATA_EXCLUDED.md). Configure a COPY of [safe example](../common/luna.example.json), never commit real endpoints/credentials or provider replies. The genuine rb engine and v2 payload/parser are used by the opt-in runner:

```sh
python classifiers/common/luna_runner.py --config classifiers/common/luna.example.json --out .cache/luna-dry
python tools/run_offline_tests.py
```

Without private inputs the dry planner fails honestly with missing-data, not fabricated results. With private inputs dry mode validates image hashes and plans cases without a request. Only separately approved execution adds --execute with TYRE_OWNER_AUTHORIZED_CLOUD set to1 and a fresh operator-owned config. Outputs are local-only events.jsonl and summary.json; no automatic retries, no IAM/provisioning writes, no historical owner grants or production budget migration. Recorded benchmark results are [projected raw predictions](results/per-image.json), not new execution claims. See [runtime boundaries](../../dashboard/README.md).

## Limitations and rights
Generic visual judgment cannot verify depth, TWI, hidden condition or safety. Tiny preliminary labels, archive-driven rubric selection, no expert adjudication, unknown service image transforms and version longevity. Provider availability, entitlement/quota and fresh paid-run preflight must be independently verified. No cloud subscription, endpoint or authorization is transferred by this private export.
