# Dashboard cohort projection v2

Projection updated 2026-11-18 from saved evidence only. No inference, training, acquisition,
cloud deployment or budget reconciliation accompanies this change. This changes presentation,
not the frozen benchmark: all original saved predictions, training records, cost JSON, experiment
files, model code and owned heads remain byte-identical to archive baseline
`63c074f7fe97f17196f3421e7e0001e3d0221086`. Older UI/export source bindings remain historical,
not claims that this UI is unchanged. The manifest retains those provenance hashes separately.

## Cohorts and scores

Default shared9 uses indices 1, 2, 8, 10, 11, 18, 20, 22, 25 (5 bad / 4 good).
Rows are computed from each method's saved `results/per-image.json`, not copied from
`FINAL_BENCHMARK.json` or an old summary table. Reviews and errors are incorrect in overall accuracy;
accepted accuracy excludes them and is always accompanied by binary coverage.

| Method | Shared9 correct | False good / 5 | Binary outputs / 9 | Full22 correct | False good / 13 |
|---|---:|---:|---:|---:|---:|
| ResNet18 | 4 | 1 | 9 | 12 | 2 |
| MobileNet | 4 | 1 | 9 | 14 | 3 |
| CLIP | 7 | 2 | 9 | 18 | 2 |
| Luna Responses | 8 | 0 | 8 | 19 | 1 |
| Luna Decisions | 3 | 3 | 8 | 11 | 6 |
| GPT-4.1 fine-tuned | 9 | 0 | 9 | Not evaluated | Not evaluated |

Source: [saved prediction archive](../classifiers/common/results/per-image.json) and
[cohort partitions](../classifiers/common/results/partitions.json).
Two source-review photos are outside both binary cohorts; saved rubric-v2 diagnostics each
reject 2/2. Local and GPT two-photo review diagnostics are not recorded, hence not evaluated,
not zero. The primary table has no misleading Review / 2 column.

The shared evaluation photos do not imply identical training protocols. Local shared9 uses
outer fold0 heads trained on13 binary examples. GPT training used13 different examples
(6 bad, 5 good, 2 review) after screened exclusions; Luna is prompted and has no trained head.
Full22 local results combine grouped out-of-fold predictions, not the current full-data upload head.
This repeatedly reused development archive is not an independent or prospective validation set.
Duplicate14 stays excluded; label11 remains flagged; labels remain provisional.

## Latency and costs

Cost snapshot: [verified Azure retail calculations](assets/verified-azure-costs.json),
generated 2026-11-08T23:58:34.784736+00:00. Tariffs are dated evidence, not live pricing or invoices.
See [cost assumptions and exclusions](COSTS.md).

Luna [archived per-case usage and timing](../classifiers/common/results/cloud-rounds-per-case.json)
contains exact rubric-v2 predictions, successful-request elapsed seconds, usage and low/high retail bounds.
The projection matches these to each selected cohort before computing median request latency and
arithmetic mean cost per submitted image from token usage and the frozen first-party retail meters; each per-case bound is also checked for equality. Each selected case has one physical attempt and zero
unknown-cost attempts. Shared9 medians: Responses5.411756930s and Decisions2.439905458s (n9 each);
full22 medians5.177855776s and2.437918138s (n22 each). These are archived API elapsed times,
not dashboard upload/queue latency or current SLAs. Source files do not record per-case calendar dates;
no request date is invented. They are preserved in the named archive baseline.

Shared9 Luna costs: ResponsesUSD0.000270037778–0.000476825556;
DecisionsUSD0.000167126667–0.000334253333. Full22 means: ResponsesUSD0.0002655–0.000468325;
DecisionsUSD0.0001643–0.0003286. These are cohort-matched, not the separate25-submission context
(including review and duplicate cases) in the original cost infographic. Bounds reflect short/long
context tariff uncertainty. Decisions output-zero observation does not establish a no-output-charge contract.

GPT [saved nine request timings and usage](../classifiers/gpt41-finetuned/results/per-image.json)
yield median3.445062637s (n9); token arithmetic at fine-tuned regional tariffs yieldsUSD0.002464/image.
Always add fixedUSD1.70/hour while deployed, including idle, andUSD31.9792 one-off training
(display roundedUSD31.98). No baseline-GPT tariff is copied. No full22 timing/cost/accuracy is inferred.

Local CV cohort request latency was not recorded: display Not measured, not a made-up mean.
Separate Azure synthetic startup smoke observations (n1 each, including weight loading) are
8.619960414s / 8.643395066s / 11.430406353s for ResNet/MobileNet/CLIP.
At the frozen 2vCPU/4GiB active retail allocation these model roughly
USD0.000517197625 / 0.000518603704 / 0.000685824381 per active image.
These are not cohort means, representative throughput, measured billed CPU, or total cost.
API fee is zero but compute is not. All local methods share one ACA hosting allocation;
do not triple the host or add the same active compute twice. Idle allocation, subscription grants,
storage, logging, networking, queues, local training, discounts and tax remain unallocated/excluded.

## Runtime and privacy boundary

Dashboard DTOs have an explicit field construction; no private paths, raw provider payloads,
request identifiers, photo hashes, prompts or user annotations are returned in benchmark summaries.
Only the six-method display allowlist appears in comparison families and configured upload choices.
Historical results do not enable a model. Missing adapters/backbones remain unavailable; no capability,
registry inference behavior, accounting, consent, auth, recovery or retention checks are relaxed.
The private live ledger is not present in the curated tree; current budget and invoice are unavailable,
not the historical190 requests, and providers fail closed.

Historical explorer DOM, navigation, event handlers and fetches are removed; the compatibility
`/api/per-images` endpoint and all research evidence are retained. Current upload job results remain.
No experimental classifier is deleted merely because it is omitted from this UI.

## Run and verify locally

From the repository root with its pinned Python dependencies:

    python -m dashboard.backend.server --bind 127.0.0.1 --port 8765 --read-only
    python tools/run_offline_tests.py
    python tools/check_publication.py
    python tools/check_publication.py --staged

Use isolated scratch feedback/upload directories through `TYRE_FEEDBACK_ROOT` and
`TYRE_UPLOAD_SCRATCH` for verification. Read-only mode disables inference, writes and workers.
No production settings, private ledger, original research project files or cloud resources are changed.
