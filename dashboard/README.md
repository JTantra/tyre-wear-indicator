# Runnable source versus deployed pilot

The export contains genuine original audit, feature extraction/head training, inference entrypoints, API request/schema/metrics/budget code, server/UI/session/job/feedback code, and native AutoML preparation/download/evaluation helpers. It is not a fake wrapper around cached benchmark predictions. Missing private model heads/receipts cause unavailable or missing-input errors.

Original project and activeca2 manifest/build/runtime/productionledger remain untouched. Curated tree is a separate source root, not a clone of the deployed image. Source→export SHA mapping is [manifest](../export-manifest.json); modified exports have different hashes and cannot satisfy original production source bindings. No source_runtimepins or deployed manifest is rewritten.

Export-only changes: absolute WSLroot becomes source-relative; AutoML subscription/RG/workspace are environment placeholders; GPTtenant binds AZURE_TENANT_ID; private owner/IAM/auth-reconciliation branch removed and raises; cloud guard requires fresh TYRE_OWNER_AUTHORIZED_CLOUD opt-in; safe GPTplan describes actual13, not earlier15; production FINAL_BENCHMARK projection replaced with safe anonymous research aggregates; selected tests needing private assets explicitly skip. The original local app cloud registry expects private sibling adapters; these are not copied and remote availability correctly fails closed. The published safe app is local-only until separately engineered/reviewed private durable cloud runtime integration. No ca2 packaging/redeployment claim.

Local app: `python -m app.server --bind 127.0.0.1 --port 8765`. Regenerate local heads first to enable actual local infer. Its feedback SQLite and volatile in-memory job stores are development-only; generated state is ignored. Publicmode requires explicit durable feedback/job factories, HTTPS ingress/public origins, cookie/session keys and paid adapter checkpoint contract; simply binding0.0.0.0must fail without them. The existing online password-gated pilot has four methods and separate private native infrastructure; exported local registry should not be confused with its capabilities.

GPT genuine adapter conditional inputs in infra/vision-finetune/: fresh account-readback endpoint; job-readback succeeded/exact trained_model; deployment-name readback model version/provisioning/rateLimits; per-method preflight complete; configured plan.scope and AZURE_TENANT_ID; credential with CognitiveServices audience. Adapter requires cloud-send consent, complete availablemethod, validated bytes, exclusive project ledger reservation and200lifetimecap; unknown transport/usage/schema halts. These private receipts are intentionally absent and may contain identities/secrets if naively captured: keep them ignored. No command automates training/deployment/IAM under this task. Owner must independently verify new source/receipt protocol before cloud-serving this adapted tree.

Local source dependencies use pinned base/CPU/foundation lists. AutoMLpreparation requires PyYAML/Pillow/numpy and may require separately isolated MLTable dependencies; client SDK requirements conflict with older dataprep identity pins and should not be blindly merged. Selected AMLmodel requires actual emitted conda.yaml/signature, not universal MLflow guesses. Current offline publication tests do not require cloud SDK, checkpoint download or GPU.


## Current structural refactor boundary
Inspected small numeric final local heads are now explicitly owner-authorized in this private repository.
Only exact owned hashes/sizes and the safe schema are allowlisted; giant backbones, raw data, feature matrices,
private images/labels, credentials and production receipts remain excluded. Historical blanket head exclusion
above describes the prior export, not the new exception.

New start: `python -m dashboard.backend.server --bind 127.0.0.1 --port 8765 --read-only`.
Open http://127.0.0.1:8765 . Frontend and benchmark/method APIs are real loopback HTTP.
Read-only disables POST/inference/background worker; session issuance is ephemeral.
Local heads are included; availability additionally requires pinned backbones. Paid capabilities stay unavailable.
