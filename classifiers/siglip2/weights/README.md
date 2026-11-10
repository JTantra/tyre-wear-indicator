# SigLIP2 Base/16 224 weights

See [pinned metadata](pretrained.json) and [method instructions](../README.md). Public checkpoint bytes remain external and ignored. `fetch.py` defaults to dry-run and never accepts custom terms; standard existing HF cache/credentials only. Do not retry an access gate or use mirrors.

`head.json` is a strictly numeric scaler + binary logistic/SVC format, no pickle, feature matrix, labels or sample metadata. This final logistic head was genuinely fit on22, reloaded and matched against sklearn and actual backbone/image smoke; it is not an OOF head.
