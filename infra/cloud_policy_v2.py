"""Current owner-approved policy: monetary cap removed, inference cap unchanged.
Do not edit/reset prior USD10 ledger events or receipts. Record estimates honestly.
"""
import math, os
AUTHORIZATION = {'event_id': 'UNAUTHORIZED_EXPORT', 'authorization': 'Fresh explicit owner authorization required; historical approval is not transferable'}
APPROVAL_MESSAGE='FRESH_OWNER_APPROVAL_REQUIRED'
INFERENCE_LIMIT=200
MONETARY_LIMIT_USD=None

def guard(ledger,reserve):
 if os.environ.get("TYRE_OWNER_AUTHORIZED_CLOUD") != "1": raise PermissionError("Fresh explicit owner cloud-send/spending authorization required")
 if not ledger.lock.exists():raise ValueError('Inference reservation requires project lease')
 if type(reserve) not in (int,float) or not math.isfinite(reserve) or reserve<0:raise ValueError('Invalid planning reservation')
 if ledger.blocked:raise ValueError('Unresolved project inference halt')
 if ledger.count>=INFERENCE_LIMIT:raise ValueError('Lifetime200 inference ceiling exhausted')
 return {'budget_authorization':AUTHORIZATION,'reserved_usd':reserve,'monetary_limit_usd':None,'owner_approval_message':APPROVAL_MESSAGE}
