# Small final head and pinned public backbone
[head.json](head.json) contains only final numeric StandardScaler mean/scale and logistic coefficients/intercept.
No pickle deserialization in inference; no raw samples, per-row labels, features, paths or secret metadata.
[Owned-head bindings](../../common/owned-heads.json) record trusted original hashes/sizes and exact export digests.
These final engineering heads fit22 examples; their training fit is not held-out benchmark accuracy.
Trusted original joblib inspection is offline only: arbitrary pickle/joblib can execute code and must not be loaded.

[pretrained.json](pretrained.json) pins the exact public URL/repo/revision, file size and full SHA256.
Acquire explicitly from root: python classifiers/resnet18/weights/fetch.py.
Downloaded backbone files remain ignored; no Git/LFS upload. Encoder verifies pins before loading.
Without acquisition use test.py --image /private/authorized.jpg --backbone /existing/pinned/checkpoint.pth.
The CLIP argument is a folder of pinned model/config/card files; torchvision uses a checkpoint file.
No implicit download or inference on --help. Respect [upstream notices](../../../THIRD_PARTY_NOTICES.md).
Numeric head publication is narrowly authorized; giant public weights/private inputs remain prohibited.
New training: --out classifiers/resnet18/weights/generated, followed by --weights pointing there for inference.
