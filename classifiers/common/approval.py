"""Fresh private approval; historical benchmark/cost rows grant no capability."""
import json,os,time
from pathlib import Path
from classifiers.common.paths import ROOT
def require(approval,operation):
 if os.environ.get('TYRE_OWNER_AUTHORIZED_CLOUD')!='1' or approval is None:raise PermissionError('Fresh owner cloud-send/spending approval and private receipt required')
 path=Path(approval).resolve()
 if not path.is_relative_to((ROOT/'.cache').resolve()):raise PermissionError('Approval must be private under .cache, never original production receipts')
 row=json.loads(path.read_text())
 if row.get('operation')!=operation or row.get('approved') is not True or type(row.get('expires_unix')) not in (int,float) or row['expires_unix']<=time.time():raise PermissionError('Approval scope expired/mismatched')
 ledger=ROOT/'infra/experiment-request-ledger.json'
 if not ledger.is_file():raise PermissionError('Fresh operator-owned ledger/limit receipt required; no production budget reuse/reset')
 return row
