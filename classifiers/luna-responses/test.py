import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
from classifiers.common.test_cli import main
if __name__=='__main__':main('luna-responses')
