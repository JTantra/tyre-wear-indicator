"""Stable repository discovery; dataset and private output are explicit inputs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def method_module(method,name):
 import importlib
 return importlib.import_module('classifiers.'+method+'.'+name)
