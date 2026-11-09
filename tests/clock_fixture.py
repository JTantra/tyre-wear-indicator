import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
class Clock:
    def __init__(self): self.now=2000000000.; self.waits=[]
    def time(self): return self.now
    def sleep(self, seconds): self.waits.append(seconds); self.now+=seconds
