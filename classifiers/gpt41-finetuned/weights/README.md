# Hosted checkpoint, not downloadable task weights
GPT-4.1 vision SFT actually completed on13 examples (6bad/5good/2review), one epoch,
effective batch1, learning-rate multiplier2, seed105. The nine evaluation photos were excluded.
No private hosted model/job/principal ID is published. [Safe training facts](../results/training.json)
and [reference configuration](../plan.json) preserve model version and protocol without a capability.
train.py prepares the genuine13-input JSONL privately; it never uploads or starts paid fine-tuning.
Cloud upload/fit/deployment needs fresh scoped owner approval and native Azure operator workflow;
there is deliberately no historical approval reuse in this source export.
test.py --image requires a privately installed completed deployment/preflight/account readback,
fresh approval and ledger, otherwise it reports unavailable. Hosted weights cannot be downloaded.
