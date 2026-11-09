# Azure ML AutoMode image classification — prepared, unrun

## Status
Prepared seventh approach, NOT a seventh scored result. No AutoML training job or inference result exists. EastUSGPU quota 0; five other US regions investigated(EastUS2,NorthCentralUS,SouthCentralUS,WestUS2,WestUS3) also had zero relevant dedicated GPU quota. EastUS2 eligible A100 candidate required24 vCPU with quota 0. Availability is not quota. No quota bypass or cloud mutation is included in publication preparation.

## Model and checkpoint provenance
Native Azure ML SDKv2 automl.image_classification, AutoMode provider chooses models; no checkpoint can be named before a run. Primary metric accuracy, label target, max_trials5/max_concurrent_trials1/timeout_minutes90, no custom search_space/sweep/training_parameters or test_data inputs. These limits bound a job, not total invoice cost. [Genuine SDK builder](../../infra/automl-pilot-v1/preparation/sdk_job.py).

## Inputs and transforms
Same enhancement-free canonical RGB JPEG.13 training/validation files would be referenced by private identity-backed datastore MLTable streams;9 evaluation photos stay local and are never AML job input. MLTable uses JSONL read and image_url stream_info conversion. Service-internal training transforms/checkpoint details remain unknown until actual completed model artifacts/conda environment exist.

## Training, validation and test
Prepared10train(7 bad/3 good),3validation(1 bad/2 good),9 evaluation(5 bad/4 good), group/hash disjoint. Review3/15 and duplicate14 excluded; GPT person-screen exclusions6/16 do NOT apply to this separately approved AutoML preparation. Validation indices4/19/21; training5/6/7/9/12/13/16/17/23/24; evaluation1/2/8/10/11/18/20/22/25. Validation-only provider automl_best_child_run_id selection, download before once-only local evaluation. Previously explored provisional archive, not an independent prospective cohort.

## Metrics and coverage
All22unknown, shared9unknown, unsafe-error count/coverage/runtime/training cost unknown. Do not replace unknown with0% or100%; hypothetical loader outputs in tests are fixtures, not AutoML evidence. Once an actual model exists, the evaluator keeps all9denominator including errors and review abstentions, records5 bad denominator and coverage separately.

## Prompt or questions
None: supervised image classifier, not a prompted LLM. AutoMode model/task-specific input contract must come from the actual model signature; selected-model loader rejects mismatched schema and keeps failure denominators.

## Cost and runtime
No observed training/GPU/inference bill or model score. Quota-blocked before run; hosting/training tariff depends on an approved compute SKU, duration, trials, model deployment and private infrastructure.90minute job limits are not a financial ceiling. No GPU/model download occurs in offline publication checks. [Shared cost context](../../docs/COSTS.md).

## Reproduce and expected artifacts
Private acquisition/audit/ResNet prerequisites: [data guide](../../docs/DATA_EXCLUDED.md). Existing prepare.py explicitly requires private source labels/archive/canonical manifests plus a private identity-only datastore readback; these are withheld and must be supplied locally. Export-only Azure subscription/resource-group/workspace constants are environment-configured placeholders, never historical IDs. Preparation deps are isolated from newer Azure identity client pins; requirements-client.txt is SDK/download only, selected model needs its actual conda.yaml, not a guessed universal environment.

```sh
python infra/automl-pilot-v1/preparation/prepare.py --help
python tools/run_offline_tests.py
```

After installing preparation dependencies and supplying private receipts:

```sh
python infra/automl-pilot-v1/preparation/prepare.py --root . --out .cache/automl --datastore YOUR_PRIVATE_DATASTORE --prefix approved/automl-v1 --compute YOUR_APPROVED_GPU
```

Expected local-only partition-manifest.json, upload/train and validation annotations.jsonl/MLTable, upload/images13, evaluation/images9 and truth.json, job.yml, upload-plan.json and checksums.json. SDK build_job constructs a native job without submitting. Fresh quota/network/privacy/paid-change approval precedes any upload/submit. Genuine download_best.py selects only provider best child by validation; evaluate.py binds actual model-tree and bundle hashes, never test feedback or silent retry. Current export tests verify pure rows/job/output/selection contracts; private bundle/source tests are not falsely counted as execution.

## Limitations and rights
Quota blocked, no model quality evidence. Dataset roles are small and previously explored. Private photos remain private even for a private repository. AzureMLbatch routing of local existing heads is a hosting experiment, not this native AutoML classifier or a new seventh benchmark result. Claude remained unrun and is not substituted for AutoML.
