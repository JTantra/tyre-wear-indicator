"""Frozen safe prediction scoring, explicitly not image inference."""
import json
from pathlib import Path
from classifiers.common.paths import ROOT
METHOD_IDS={'resnet18':'resnet18','mobilenet':'mobilenet','clip':'clip','luna-responses':'luna-responses','luna-decisions':'luna-decisions','gpt41-finetuned':'gpt41-finetuned'}
def score(method):
 from tools.check_publication import metric
 folder=ROOT/'classifiers'/method/'results'
 rows=json.loads((folder/'per-image.json').read_text())
 return dict(method=method,evaluation='Archived frozen predictions, NOT fresh-image inference',all22=metric(rows) if len(rows)==22 else None,shared9=metric([r for r in rows if r['fold']==0]))
