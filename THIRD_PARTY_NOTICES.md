# Third-party provenance, not legal clearance

No root LICENSE is invented: private source access/publication permission does not license customer data or third-party model weights. Owner must determine project source licensing; private publication is not a blanket rights grant.

Torchvision code BSD-3-Clause: [copied upstream notice](third_party/torchvision-LICENSE.txt), source https://github.com/pytorch/vision/blob/main/LICENSE . ResNet/MobileNet/EfficientNet weights derive from ImageNet; separate dataset/weight commercial-use clearance was not established. Recorded exact URLs/digests are in [model provenance](results/model-provenance.json).

CLIP: https://github.com/openai/CLIP/blob/main/LICENSE upstream code MIT; HFmirror card does not specify a separate weight license. [Pinned card](third_party/clip/README.md) preserves research-use, deployment evaluation, bias/robustness limits; not zero-shot classification in this project. Revision3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268. No commercial/legal clearance inferred.

DINOv2-small legacy comparison: [pinned card](third_party/dinov2/README.md), Apache-2.0 upstream code/model-card assertion, revisioned25f3a31f01632728cabb09d1542f84ab7b0056. Dataset/pretraining overlap and rights still require review.

Luna/GPT/AML are provider-hosted services subject to Azure/OpenAI service terms and entitlements; no open license over hosted checkpoints is asserted. Python/package dependencies keep their own licenses. Authorized input archives/person-content/customer annotations are excluded and never licensed by this file.
