# GPT-4.1 supervised vision fine-tune

## Status
Completed actual supervised vision SFT and nine-image evaluation; original live upload adapter existed at the dated snapshot. Curated export has the genuine payload/parser/cost/consent/ledger adapter, not private deployment/IAM/receipt metadata. It will remain unavailable without fresh exact-model deployment and preflight receipts. No model training/deployment/inference ran during publication preparation.

## Model and checkpoint provenance
Azure OpenAI gpt-4.1-2025-04-14, version2025-04-14; supervised Standard regional fine-tuning in NorthCentralUS; fine-tuned hosting Standard and untuned baseline DataZoneStandard. Private trained model identifier/job IDs are omitted; do not invent a downloadable local checkpoint. Effective completed hyperparameters: n_epochs1, batch_size1, learning_rate_multiplier2, seed 105. Earlier submitted payload used one epoch and provider defaults for batch/LR; the completed job readback is authoritative. [Actual training facts](results/training.json).

## Inputs and transforms
Same full-frame enhancement-free RGB canonical JPEG(max1024,JPEG95,EXIF stripped). Image detail high, generic rubric system text, assistant target JSON with exactly visual_condition good/bad/review. No filenames, annotation reasons, few-shot images or evaluation inputs in training. Inference uses /openai/v1/chat/completions, strict json_schema, temperature0, seed 105, max_completion_tokens64, store:false. Genuine [adapter](adapter.py) enforces usage totals/schema/refusal checks and reports unknowns rather than fabricated zero cost.

## Training, validation and test
Actual uploaded13:6 bad,5 good,2 review; planned15 was superseded by two person-content exclusions(indices6/16). Training indices3,4,5,7,9,12,13,15,17,19,21,23,24. No separate validation partition was submitted. Same separate nine evaluation photos5 bad/4 good(indices1,2,8,10,11,18,20,22,25); duplicate14 excluded. Label11 was preserved, not silently relabeled. Grouping is a visual hypothesis; all archive previously explored. Training and evaluation are group-disjoint under that hypothesis, but not proved independent tyres. No22-photoFTscore.

## Metrics and coverage
FT9/9 correct,0/5 bad called good,9/9binary coverage,zero reviews/errors; untuned GPT baseline8/9,0/5 bad called good. These nine show development agreement, NOT100% populationaccuracy or safety. FTmedian HTTP3.445062637seconds over9; baseline3.796544313seconds. No local serving-head OOF analogy: FT evaluated on9, local heads used outer folds and final22refits. [Metrics](results/summary.json) · [Anonymous outputs/usage](results/per-image.json).

## Prompt or questions
Exact generic rubric and one-key output schema are in [training facts](results/training.json) and [safe adapter plan](plan.json). Same condition rubric as Luna v2; condition-only schema differs from Luna's observations and typed predicates. No review confidence probability is fabricated.

## Cost and runtime
Observed evaluation9864input/54output tokens,zero cached,9attempts. USD0.002464/image=(9864×2.2+54×8.8)/1million/9. Completed trained_tokens1162880: one-off retail trainingUSD31.9792=(tokens/1000)×0.0275. Fine-tuned regional hostingUSD1.70/hour WHILE DEPLOYED EVEN WITH NO REQUESTS; separate from shared app hosting.24hours×30days=USD1224/month. At1000images/day, API+FTmodel hostingUSD0.043264/image; at10000/dayUSD0.006544, before appinfra/train amortization. These are dated tariff estimates, not invoices. [Costs](../../docs/COSTS.md).

## Simple method commands
Run from repository root, or use an absolute script path from any working directory:
```sh
python classifiers/gpt41-finetuned/train.py --help
python classifiers/gpt41-finetuned/test.py --help
python classifiers/gpt41-finetuned/test.py --benchmark
python /absolute/path/to/repo/classifiers/gpt41-finetuned/test.py --benchmark
```
--benchmark evaluates [frozen saved rows](results/per-image.json), NOT image inference.
--image /absolute/path/to/authorized.jpg is genuine fresh-image inference or a clear unavailable reason; never a cached-row lookup.
See [weights and acquisition](weights/README.md). --help imports no ML/cloud packages and does not download, train or call a provider.

train.py --data-root /private/archive --out /repo/.cache/gpt-training prepares actual13 image JSONL examples; no automatic upload.
Hosted inference requires a genuinely completed private deployment/preflight readback plus fresh approval.

## Reproduce and expected artifacts
Install base/source dependencies; Azure identity credential is an optional cloud dependency. Privately recover the authorized archive, run audit/ResNet, then:

```sh
python classifiers/gpt41-finetuned/preparation.py --out .cache/gpt-training
python tools/run_offline_tests.py
```

The offline generator creates the real13 training image/assistant-label JSONL and a checksummed receipt, verifies source bytes and disjoint indices; it does not upload or fit. Its private outputs are ignored. Payload model=gpt-4.1-2025-04-14, seed 105, method.supervised.hyperparameters n_epochs1, trainingType Standard; never place a fake historical training file/model ID into a runnable payload. Actual cloud reproduction requires owner-approved upload via the provider Files endpoint, returned training file ID, one SFT job, completed exact trained-model readback, authorized deployment and preflight. Those are paid changes and intentionally not automated by this documentation export. No runnable claim for retained production receipts; [adapter receipt requirements](../../dashboard/README.md) describe the conditional real inference path and failure gates. Expected local-only training.jsonl and receipt.json; real offline tests exercise adapter parse/cost/payload with synthetic contracts only.

## Limitations and rights
Thirteen actual examples and nine explored evaluation photos are too small for safety or generalization guarantees. Person-content screening and authorization do not establish rights to publish the remaining images. Provider-hosted model has service terms and fixed-cost exposure; no open weight license is asserted. Larger blind expert-labeled independent-tyre comparison is still needed.
