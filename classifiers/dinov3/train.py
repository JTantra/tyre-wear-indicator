#!/usr/bin/env python3
"""Train/evaluate only this frozen representation, with explicit private inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
if __name__=='__main__':
 from classifiers.common.foundation_next_experiment import main
 main(default_methods=['dinov3'])
