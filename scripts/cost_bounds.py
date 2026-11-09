"""Public-retail cost intervals; unresolved tier/cache semantics are not invoices.
Rates are from docs/PRICING_EVIDENCE.md East US DataZoneStandard meters.
This module does NOT activate a verified rate card or invent actual usage.
"""
from decimal import Decimal
TIERS={'short':('0.11','0.011','0.1375','0.55'),'long':('0.22','0.022','0.275','0.825')}
def bounds(usage):
 result={'usd_low':None,'usd_high':None,'actual_usage':usage,'not_an_invoice':True,'rate_card_verified':False,'evidence':'docs/PRICING_EVIDENCE.md','reasoning_charged_once':True}
 if not isinstance(usage,dict): return dict(result,unknown=True,reason='missing_usage')
 I,O,T=[usage.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
 if any(type(n) is not int or n<0 for n in (I,O,T)) or I+O!=T: return dict(result,unknown=True,reason='invalid_usage')
 details=usage.get('input_tokens_details') or {}; H=details.get('cached_tokens'); W=details.get('cache_write_tokens')
 if any(v is not None and (type(v) is not int or v<0 or v>I) for v in (H,W)) or (H is not None and W is not None and H+W>I):
  return dict(result,unknown=True,reason='invalid_cache_usage')
 # Linear objectives: extremes occur at these feasible triangle corners.
 if H is None and W is None: points=[(0,0),(I,0),(0,I)]
 elif H is None: points=[(0,W),(I-W,W)]
 elif W is None: points=[(H,0),(H,I-H)]
 else: points=[(H,W)]
 amounts=[]; scenarios=[]
 for tier,rates in TIERS.items():
  ri,rh,rw,ro=map(Decimal,rates)
  for mode in ('partitioned_replacement','input_inclusive_surcharge'):
   vals=[((I-h-(w if mode=='partitioned_replacement' else 0))*ri+h*rh+w*rw+O*ro)/Decimal(1000000) for h,w in points]
   scenarios.append({'tier':tier,'write_semantics':mode,'low':float(min(vals)),'high':float(max(vals))}); amounts.extend(vals)
 return dict(result,unknown=False,usd_low=float(min(amounts)),usd_high=float(max(amounts)),cache_details_complete=H is not None and W is not None,scenarios=scenarios,interpretation='Interval over both published context rates and both unresolved 30m write rules; absent cache details range over feasible cache allocations, not assumed zero.')
