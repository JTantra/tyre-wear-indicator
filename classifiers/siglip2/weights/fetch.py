#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
if __name__=='__main__':
 from classifiers.common.foundation_next_acquisition import main
 main('siglip2')
