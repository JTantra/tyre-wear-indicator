import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
import argparse
from classifiers.common.acquisition import fetch
if __name__=='__main__':
 p=argparse.ArgumentParser(description='Explicit public pretrained download with exact hashes; never Git/LFS.');p.parse_args()
 print(fetch(Path(__file__).resolve().parent))
