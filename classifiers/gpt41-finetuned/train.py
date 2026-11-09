import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))

import argparse,importlib,json
if __name__=='__main__':
 p=argparse.ArgumentParser(description='Prepare actual13 supervised vision examples offline. No automatic upload, hosted fit, deployment or paid call.')
 p.add_argument('--data-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True,help='Private new directory, never Git; contains image payloads')
 a=p.parse_args()
 try:result=importlib.import_module('classifiers.gpt41-finetuned.preparation').prepare(a.out,a.data_root);print(json.dumps(result))
 except FileNotFoundError:p.exit(2,'Unavailable: authorized private images/manifest/frozen split required; no training or upload performed\n')
