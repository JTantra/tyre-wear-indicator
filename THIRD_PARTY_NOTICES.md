# Third-party provenance, not legal clearance

No root LICENSE is invented: private source access/publication permission does not license customer data or third-party model weights. Owner must determine project source licensing; private publication is not a blanket rights grant.

Torchvision code BSD-3-Clause: [copied upstream notice](classifiers/common/torchvision-LICENSE.txt), source https://github.com/pytorch/vision/blob/main/LICENSE . ResNet/MobileNet/EfficientNet weights derive from ImageNet; separate dataset/weight commercial-use clearance was not established. Recorded exact URLs/digests are in [model provenance](classifiers/common/results/model-provenance.json).

CLIP: https://github.com/openai/CLIP/blob/main/LICENSE upstream code MIT; HFmirror card does not specify a separate weight license. [Pinned card](classifiers/clip/weights/upstream/clip/README.md) preserves research-use, deployment evaluation, bias/robustness limits; not zero-shot classification in this project. Revision3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268. No commercial/legal clearance inferred.

DINOv2-small legacy comparison: [pinned card](classifiers/clip/legacy/dinov2/README.md), Apache-2.0 upstream code/model-card assertion, revisioned25f3a31f01632728cabb09d1542f84ab7b0056. Dataset/pretraining overlap and rights still require review.

Luna/GPT/AML are provider-hosted services subject to Azure/OpenAI service terms and entitlements; no open license over hosted checkpoints is asserted. Python/package dependencies keep their own licenses. Authorized input archives/person-content/customer annotations are excluded and never licensed by this file.


## Current structural refactor boundary
Inspected small numeric final local heads are now explicitly owner-authorized in this private repository.
Only exact owned hashes/sizes and the safe schema are allowlisted; giant backbones, raw data, feature matrices,
private images/labels, credentials and production receipts remain excluded. Historical blanket head exclusion
above describes the prior export, not the new exception.

## New frozen encoders (2026-11-10)

SigLIP2 Base: official Google model-card Apache-2.0 assertion at revision75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2. [Pinned public card](classifiers/siglip2/weights/upstream/siglip2/README.md) and [checkpoint digests](classifiers/siglip2/weights/pretrained.json); no public backbone bytes or input data in Git. Transformers4.57.1 code Apache-2.0.

DINOv3-S: custom gated terms, revision114c1379950215c8b35dfcd4e90a5c251dde0d32; no terms accepted or licensed-access inference made. [Unrun status and owner access action](classifiers/dinov3/README.md). Do not confuse historical DINOv2 Apache provenance with DINOv3 rights.
