#!/usr/bin/env python3
"""Reload the locally trained baseline artifacts; NOT a validated safety system."""
import argparse
import json
from pathlib import Path
import joblib
from PIL import Image, ImageOps
import torch
from torchvision.models import resnet18
from torchvision.transforms import functional as TF
from preprocessing import canonical_image
import io

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument('image',type=Path); args=p.parse_args()
    torch.set_num_threads(4)
    model=resnet18(weights=None); model.fc=torch.nn.Identity()
    model.load_state_dict(torch.load(ROOT/'artifacts/classifier/frozen_resnet18.pt',weights_only=True,map_location='cpu'))
    model.eval()
    canonical,_=canonical_image(args.image.read_bytes())
    with Image.open(io.BytesIO(canonical)) as im:
        image=ImageOps.pad(im.convert('RGB'),(224,224),color=(124,116,104),method=Image.Resampling.BILINEAR)
        x=TF.normalize(TF.to_tensor(image),[.485,.456,.406],[.229,.224,.225]).unsqueeze(0)
    with torch.inference_mode(): x=model(x).numpy()
    # Only load locally-created trusted joblib files; pickle can execute code.
    head=joblib.load(ROOT/'artifacts/classifier/baseline_head.joblib')
    prob=float(head.predict_proba(x)[0,1])
    print(json.dumps({'p_good':prob,'binary_prediction':'good' if prob>=.5 else 'bad',
       'diagnostic_prediction':'review' if max(prob,1-prob)<.65 else ('good' if prob>=.5 else 'bad'),
       'warning':'Full-data fitted artifact, no held-out claim. Confidence is not calibrated visibility or roadworthiness.'}))

if __name__=='__main__':main()
