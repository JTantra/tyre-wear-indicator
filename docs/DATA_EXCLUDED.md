# Private input acquisition and excluded assets

No photos, ZIPs, contact sheets, raw YAMLannotation reasons/UUIDfilenames, retained feedback, raw providerresponses/base64imagepayloads, IAMARMreadbacks, runtimecredentials/verifiers/capabilities, journal/productionreceiptstore, venv/cache/harnessarchive or weights/joblib are published. No external dataset-upload permission is implied by privateGitHub.

Acquire the original TWI_1_1.zip only from the owner through an approved private local channel. No public dataset URL exists. Place at data/raw/TWI_1_1.zip in an ignored directory. The source audit pins the expected archive SHA256; a changed dataset needs deliberate new-protocol review, not modification to make old scores appear reproducible. Archive identity checksum is not a grant of rights. Exact private filename/hash mapping remains in the original project, not this anonymous result view.

On Linux/WSL with base dependencies:

```sh
python classifiers/common/audit_dataset.py
python classifiers/resnet18/experiment.py
python classifiers/mobilenet/experiment.py
python classifiers/clip/experiment.py
```

Audit writes private artifacts/manifest.json and safe extraction with traversal/size checks; it also creates contact sheets/privateannotationchecklists, so all artifacts remain ignored. ResNet computes canonicalmanifest+grouped splits; exact archive order/hash tie-breaks reproduce recorded visualgroups. Mobile/CLIP expect those frozen splits. CLIPprotection also expects data/raw.sha256 and the label review checklist: create the checksum locally using `python tools/check_private_archive.py` after authorized acquisition. This helper validates the pinned archive and writes its local sha receipt without publishing or uploading it.

Excluded pretrainedweights: torchvision recorded versioned downloads in classifiers/common/results/model-provenance.json; CLIP/DINO revision-pinned GETdownload via custom_refinement_v2.prepare_weights. No public weights downloaded during docs preparation. Exact locally serialized weight/checkpoint digests and upstream download digests have DIFFERENT serialization meaning; do not interchange. Source models use frozen publicbackbones, trainedhead regenerates privately from sourcearchive, noLFSbilling or hostedmirror.

AutoMLhelper retains sourceprivatereceiptchecks: needs identity-only datastore receipt at infra/azureml-network-v2/private-datastore-readback.json and safe configured ftplan evaluation_indices. ReceiptcredentialsTypeNone means identity-backed, not a SAS/key; source labels stay at data/extracted/TWI/TWI_labels.yaml. Generate/verify these locally through separately approved Ops; do not commit copies. Publicresults stable integerindices do not establish identity/anonymity of the underlying photos; no image/reason/providerrequest/customerdata is retained in the projection.

Publication manifest maps exported sources and originalSHA/changes; private preparation exclusion inventory hashes filenames before storage outside the export. Categories and reason are recorded without publishing original photo/UUIDpaths. All originals retained locally, no history/data/ledger deletion or overwrite.


## Current structural refactor boundary
Inspected small numeric final local heads are now explicitly owner-authorized in this private repository.
Only exact owned hashes/sizes and the safe schema are allowlisted; giant backbones, raw data, feature matrices,
private images/labels, credentials and production receipts remain excluded. Historical blanket head exclusion
above describes the prior export, not the new exception.
