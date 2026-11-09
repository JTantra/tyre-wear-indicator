"""Usage-based *estimates*, never invoices. No built-in production price guesses.

Cache-write billing varies by model: a verified rate card must declare whether
write price replaces ordinary input price or is an additional surcharge.
Reasoning tokens are already part of output_tokens and are never added again.
"""
from datetime import datetime
from decimal import Decimal
import math

IDENTITY = ('model', 'model_version', 'sku', 'geography', 'currency', 'api', 'context_tier')
COMPONENTS = ('input', 'output', 'cache_write', 'cache_hit')


def usage_components(usage):
    if not isinstance(usage, dict): return None
    try:
        i, o, total = [usage[k] for k in ('input_tokens', 'output_tokens', 'total_tokens')]
        if any(type(x) is not int or x < 0 for x in (i, o, total)) or i + o != total: return None
        details = usage['input_tokens_details']
        hit, write = details['cached_tokens'], details['cache_write_tokens']
        reasoning = usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)
        if any(type(x) is not int or x < 0 for x in (hit, write, reasoning)): return None
        if hit + write > i or reasoning > o: return None
        return {'input': i, 'output': o, 'cache_hit': hit, 'cache_write': write,
                'reasoning_included_in_output': reasoning, 'total_tokens': total}
    except (KeyError, TypeError): return None


def valid_total(usage):
    if not isinstance(usage, dict): return None
    nums = [usage.get(k) for k in ('input_tokens', 'output_tokens', 'total_tokens')]
    if any(type(x) is not int or x < 0 for x in nums) or nums[0]+nums[1] != nums[2]: return None
    return nums[2]


def validate_rate(rate, variant):
    if rate is None: return False
    if any(rate.get(k) != variant.get(k) or rate.get(k) is None for k in IDENTITY):
        raise ValueError('Rate identity/tier mismatch')
    if rate.get('schema_version') != 1: raise ValueError('Unsupported rate schema')
    if rate.get('verified') is not True: return False
    for k in ('source_url', 'semantics_source_url'):
        if not str(rate.get(k, '')).startswith('https://'): raise ValueError('Missing rate evidence URL')
    for k in ('retrieved_at', 'effective_at'):
        if datetime.fromisoformat(rate[k].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Rate evidence requires dated timezone')
    if rate.get('write_semantics') not in ('input_inclusive_surcharge', 'partitioned_replacement'):
        raise ValueError('Unverified cache billing semantics')
    if rate.get('output_includes_reasoning') is not True: raise ValueError('Output billing semantics required')
    if type(rate.get('context_min_tokens')) is not int or type(rate.get('context_max_tokens')) is not int:
        raise ValueError('Explicit context tier limits required')
    if not 0 <= rate['context_min_tokens'] <= rate['context_max_tokens']: raise ValueError('Invalid tier')
    for k in COMPONENTS:
        x = rate['per_million'][k]
        if isinstance(x, bool) or not math.isfinite(float(x)) or Decimal(str(x)) < 0:
            raise ValueError('Invalid rate')
    return True


def estimate(usage, rate, variant):
    verified = validate_rate(rate, variant)
    u = usage_components(usage)
    unknown = {'estimated_cost': None, 'known_subtotal': 0.0, 'unknown': True,
               'components': u, 'currency': variant.get('currency'), 'not_an_invoice': True}
    if not verified or u is None: return unknown
    if not rate['context_min_tokens'] <= u['input'] <= rate['context_max_tokens']:
        raise ValueError('Actual usage context tier mismatch')
    ordinary = u['input'] - u['cache_hit']
    if rate['write_semantics'] == 'partitioned_replacement': ordinary -= u['cache_write']
    quantities = dict(input=ordinary, output=u['output'], cache_hit=u['cache_hit'], cache_write=u['cache_write'])
    costs = {k: float(Decimal(str(rate['per_million'][k])) * quantities[k] / Decimal(1000000)) for k in COMPONENTS}
    return dict(unknown, estimated_cost=sum(costs.values()), known_subtotal=sum(costs.values()),
                unknown=False, component_costs=costs, billable_quantities=quantities,
                rate_evidence=rate)


def aggregate(costs, logical_images, accepted):
    unknown = sum(c.get('estimated_cost') is None for c in costs)
    known = sum(c.get('known_subtotal', 0.0) for c in costs)
    total = None if unknown else known
    return {'physical_requests': len(costs), 'submitted_logical_images': logical_images,
            'accepted_classifications': accepted, 'unknown_cost_attempts': unknown,
            'known_subtotal': known, 'estimated_cost': total,
            'estimated_cost_per_submitted_image': total/logical_images if total is not None and logical_images else None,
            'known_subtotal_per_submitted_image': known/logical_images if logical_images else None,
            'effective_cost_per_accepted_classification': total/accepted if total is not None and accepted else None,
            'not_an_invoice': True}


def local_economics(inference_seconds, training_seconds, tariff_per_hour=None, volume=None):
    result = {'api_fee': 0, 'measured_seconds_per_image': inference_seconds,
              'economic_cost_per_image': None, 'scenario': None}
    if tariff_per_hour is None: return result
    if not math.isfinite(tariff_per_hour) or tariff_per_hour < 0 or type(volume) is not int or volume <= 0:
        raise ValueError('Scenario requires nonnegative tariff and positive amortization volume')
    result['scenario'] = {'tariff_per_hour': tariff_per_hour, 'volume': volume,
                          'training_seconds': training_seconds, 'assumptions_not_invoice': True}
    result['economic_cost_per_image'] = (inference_seconds + training_seconds/volume)*tariff_per_hour/3600
    return result
