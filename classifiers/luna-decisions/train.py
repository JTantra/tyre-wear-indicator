import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))

import argparse,json
if __name__=='__main__':
 p=argparse.ArgumentParser(description='luna-decisions is a prompted rubric, NOT a trained task head. Validate configuration offline; no fit or paid call.')
 p.add_argument('--validate-config',type=Path,help='Validate actual API config without submitting');a=p.parse_args()
 if a.validate_config:
  from classifiers.common.provider_runner import endpoint_url
  cfg=json.loads(a.validate_config.read_text());v=cfg['variants']
  if len(v)!=1 or v[0]['api']!='decisions':p.exit(2,'Expected exactly one decisions variant\n')
  endpoint_url(v[0]['endpoint'],'decisions');print('Configuration valid structurally; deployment/rate/approval not verified. No training.')
 else:print('Not trainable: frozen prompted visual rubric; use --validate-config. No task weights.')
