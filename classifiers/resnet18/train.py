import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))

import argparse,json
if __name__=='__main__':
 p=argparse.ArgumentParser(description='Train only resnet18 frozen features/head with unchanged grouped folds; private inputs required. No automatic download.')
 p.add_argument('--data-root',type=Path,required=True,help='Authorized private manifest, original images and frozen splits root')
 p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'weights',help='Own method weights; refuse existing head.json')
 p.add_argument('--backbone',type=Path,help='Existing pinned public checkpoint (CLIP folder); no download')
 a=p.parse_args()
 from classifiers.common.training import train
 try:print(json.dumps(train('resnet18',a.data_root,a.out,a.backbone)))
 except (FileNotFoundError,FileExistsError,ValueError,RuntimeError) as e:p.exit(2,str(e)+'\n')
