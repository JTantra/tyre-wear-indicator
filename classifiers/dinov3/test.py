#!/usr/bin/env python3
"""Read frozen evidence or infer a genuine local image; help is dependency-light."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--benchmark',action='store_true');g.add_argument('--image',type=Path);p.add_argument('--weights',type=Path);p.add_argument('--head',type=Path,default=Path(__file__).parent/'weights/head.json');a=p.parse_args()
 if a.benchmark:print((Path(__file__).parent/'results/summary.json').read_text());return
 if not a.image or not a.weights:p.error('--image and --weights required for local inference')
 from classifiers.dinov3.inference import predict
 print(json.dumps(predict(a.image,a.weights,a.head),indent=2))
if __name__=='__main__':main()
