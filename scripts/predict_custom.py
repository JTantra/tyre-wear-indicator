#!/usr/bin/env python3
"""Offline saved custom-model smoke. All images require review until safety validation."""
import argparse
import io
import json
from pathlib import Path
import joblib
import torch
from PIL import Image
try:
    from .custom_improvements import ROOT, REPRESENTATIONS, backbone, tensors_for, extract, canonical_image, digest
except ImportError:
    from custom_improvements import ROOT, REPRESENTATIONS, backbone, tensors_for, extract, canonical_image, digest

def predict(image_path,artifacts=ROOT/'artifacts/custom-improvements'):
    config=json.loads((artifacts/'deployment_config.json').read_text())
    name,mode=next((n,m) for n,m in REPRESENTATIONS if n+'_'+m==config['candidate'])
    summary=json.loads((artifacts/'summary.json').read_text())
    provenance=summary['provenance'][config['candidate']]
    if digest(artifacts/'head.joblib')!=summary['head_sha256']:raise ValueError('Saved head hash mismatch')
    state=artifacts/(name+'_frozen.pt')
    if digest(state)!=provenance['frozen_state_sha256']:raise ValueError('Saved backbone hash mismatch')
    torch.set_num_threads(4)
    model=backbone(name,False,state);head=joblib.load(artifacts/'head.joblib')
    data,_=canonical_image(Path(image_path).read_bytes())
    with Image.open(io.BytesIO(data)) as im:x=extract(model,tensors_for(im.convert('RGB'),mode),mode)
    prediction=int(head.predict(x)[0]);margin=float(head.decision_function(x)[0])
    return {'prediction':'review','needs_review':True,'tread_visibility':'unassessed',
        'diagnostic_binary_prediction':'good' if prediction else 'bad','decision_margin':margin,
        'candidate':config['candidate'],'tread_depth_mm':None,'roadworthiness_certified':False,
        'reason':'No validated tread visibility/OOD or safety threshold. Diagnostic output is not clearance.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('image',type=Path)
    parser.add_argument('--artifacts',type=Path,default=ROOT/'artifacts/custom-improvements')
    args=parser.parse_args();print(json.dumps(predict(args.image,args.artifacts),indent=2))
