"""Pure payload/evaluation contracts, used by the separate bounded HTTP runner.

Requests match official Decisions/Responses docs; live Azure compatibility remains integration-gated.
The separate run_benchmark.py defaults to dry-run and has real loopback transport tests.
Image bytes are the sole case-specific input: no filenames, labels, YAML reasons,
confidence, contact sheets or review annotations enter model requests.
"""
from __future__ import annotations

import base64
import io
from collections import Counter
from PIL import Image, ImageOps

RUBRIC_VERSION = 'visual-condition-v1'
RUBRIC = (
    'Classify visible tyre tread condition, not measured depth or legal roadworthiness. '
    'good: visible grooves and tread relief, without clearly visible severe wear/damage. '
    'bad: clearly bald/worn tread, very shallow-looking grooves, cracks or visible severe damage. '
    'review: tread is not adequately visible, evidence conflicts, or you cannot decide reliably. '
    'Tread design (lug, zigzag, longitudinal), wheel appearance, and background alone do not establish condition. '
    'Do not infer millimetres or physical TWI verification. Judge only the supplied photograph.'
)


def clean_image_data_url(image_bytes):
    """Normalize pixels only, stripping metadata; never attach the original filename."""
    try:
        from .preprocessing import canonical_image
    except ImportError:
        from preprocessing import canonical_image
    canonical,_ = canonical_image(image_bytes)
    return 'data:image/jpeg;base64,' + base64.b64encode(canonical).decode('ascii')


def decisions_payload(image_bytes, deployment, multi_question=False):
    choices = [{'value': k, 'description': text} for k, text in [
        ('good', 'Grooves/relief clearly visible and no obvious severe wear/damage.'),
        ('bad', 'Clearly worn/bald/shallow-looking tread or visible severe damage.'),
        ('review', 'Insufficient, conflicting or uncertain visual evidence.')]]
    questions = [{'type': 'choice', 'name': 'condition', 'instructions': RUBRIC, 'choices': choices}]
    if multi_question:
        questions = [
            {'type': 'predicate', 'name': 'tread_visible',
             'instructions': 'Is enough of the tread face visible and sufficiently clear to assess visual condition? Sidewall/rim alone is insufficient.'},
            {'type': 'predicate', 'name': 'clear_damage',
             'instructions': 'Is there clearly visible cracking, exposed cords/carcass, or torn/missing tread? Do not infer hidden damage.'},
            *questions]
    return {'model': deployment,
            'input': [{'role': 'user', 'content': [
                {'type': 'input_text', 'text': 'Assess this photograph using the supplied visual-condition rubric.'},
                {'type': 'input_image', 'image_url': clean_image_data_url(image_bytes)}]}],
            'questions': questions}


def vision_payload(image_bytes, deployment, multi_question=False):
    properties = {
        'visual_condition': {'type': 'string', 'enum': ['good', 'bad', 'review']},
        'visibility': {'type': 'string', 'enum': ['adequate', 'inadequate', 'uncertain']},
        'visible_damage': {'type': 'string', 'enum': ['yes', 'no', 'uncertain']},
        'evidence': {'type': 'string'},
        'needs_review': {'type': 'boolean'},
        'tread_depth_mm': {'type': 'null'},
        'twi_verified': {'type': 'null'},
    }
    instruction = RUBRIC
    if multi_question:
        instruction += (' Assess tread visibility first; inspect groove/relief wear second; '
                        'inspect cracks/exposed cords/torn tread third; then classify. '
                        'Explain only visible evidence. Inadequate visibility or uncertainty must route to review.')
    return {'model': deployment, 'input': [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': instruction},
        {'type': 'input_image', 'image_url': clean_image_data_url(image_bytes)}]}],
        'text': {'format': {'type': 'json_schema', 'name': 'tyre_visual_condition', 'strict': True,
                           'schema': {'type': 'object', 'properties': properties,
                                      'required': list(properties), 'additionalProperties': False}}}}


def normalise_decisions(answers, min_good_probability, min_visibility_probability=None):
    """Validation-selected thresholds only. Malformed/refused results fail closed."""
    if not 0 <= min_good_probability <= 1:
        raise ValueError('Invalid good threshold')
    if min_visibility_probability is not None and not 0 <= min_visibility_probability <= 1:
        raise ValueError('Invalid visibility threshold')
    if not isinstance(answers, list) or not all(isinstance(a, dict) for a in answers):
        return {'prediction': 'review', 'reason': 'malformed_answers'}
    names = [a.get('name') for a in answers]
    if any(not isinstance(n, str) for n in names) or len(set(names)) != len(names) or any(a.get('type') == 'refusal' for a in answers):
        return {'prediction': 'review', 'reason': 'refusal_or_duplicate_answer'}
    by_name = {a.get('name'): a for a in answers}
    if min_visibility_probability is not None:
        visible = by_name.get('tread_visible', {})
        prob = visible.get('probability')
        if visible.get('type') != 'predicate' or type(prob) not in (int, float) or not 0 <= prob <= 1 or prob < min_visibility_probability:
            return {'prediction': 'review', 'reason': 'visibility_gate'}
    result = by_name.get('condition', {})
    choice = result.get('choice')
    if result.get('type') != 'choice' or choice not in ('good', 'bad', 'review'):
        return {'prediction': 'review', 'reason': 'missing_or_malformed_choice'}
    probabilities = result.get('probabilities')
    if not isinstance(probabilities, list) or not all(isinstance(p, dict) for p in probabilities):
        return {'prediction': 'review', 'reason': 'missing_probabilities'}
    values = [p.get('value') for p in probabilities]
    probs = [p.get('probability') for p in probabilities]
    if (len(values) != 3 or any(not isinstance(v, str) for v in values) or set(values) != {'good', 'bad', 'review'}
            or any(type(p) not in (int, float) or not 0 <= p <= 1 for p in probs)
            or abs(sum(probs) - 1) > 1e-4):
        return {'prediction': 'review', 'reason': 'invalid_probabilities'}
    by_value = dict(zip(values, probs))
    if choice == 'good' and by_value['good'] < min_good_probability:
        return {'prediction': 'review', 'reason': 'good_threshold'}
    return {'prediction': choice, 'reason': 'model_choice'}


def normalise_vision(result):
    """Refusals/transport failures must be routed to review by the future caller."""
    if not isinstance(result, dict):
        return {'prediction': 'review', 'reason': 'invalid_schema'}
    condition = result.get('visual_condition')
    if (condition not in ('good', 'bad', 'review') or result.get('visibility') not in ('adequate', 'inadequate', 'uncertain')
            or result.get('visible_damage') not in ('yes', 'no', 'uncertain')
            or type(result.get('needs_review')) is not bool
            or not isinstance(result.get('evidence'), str)
            or 'tread_depth_mm' not in result or result['tread_depth_mm'] is not None
            or 'twi_verified' not in result or result['twi_verified'] is not None):
        return {'prediction': 'review', 'reason': 'invalid_schema_or_physical_claim'}
    if result['needs_review'] or result['visibility'] != 'adequate' or result['visible_damage'] == 'uncertain' or (condition == 'good' and result['visible_damage'] == 'yes'):
        return {'prediction': 'review', 'reason': 'review_or_visibility_gate'}
    return {'prediction': condition, 'reason': 'model_choice'}


def validate_split(rows):
    """Reject missing groups, duplicate hashes crossing splits, and tyre leakage."""
    errors = []
    for key in ('tyre_group_id', 'sha256'):
        memberships = {}
        for r in rows:
            split, value = r.get('split'), r.get(key)
            if split not in ('train', 'validation', 'test') or not isinstance(value, str) or not value.strip():
                errors.append(f'Missing/invalid {key} or split')
                continue
            memberships.setdefault(value, set()).add(split)
        errors.extend(f'{key} crosses splits: {v}' for v, splits in memberships.items() if len(splits) > 1)
    return errors


def evaluate_independent_tyres(rows):
    """One preaggregated row per independent tyre, including abstentions/errors.

    This is a metrics helper, not a way to turn unverified IDs into independence.
    Caller must resolve photo aggregation and expert truth before using it.
    """
    ids = [r.get('tyre_id') for r in rows]
    if not rows or any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Require nonempty independent unique tyre IDs')
    if any(r.get('truth') not in ('good', 'bad', 'review') or r.get('prediction') not in ('good', 'bad', 'review') for r in rows):
        raise ValueError('Invalid truth/prediction')
    confusion = {truth: {pred: 0 for pred in ('good', 'bad', 'review')} for truth in ('good', 'bad', 'review')}
    for r in rows:
        confusion[r['truth']][r['prediction']] += 1
    binary = [r for r in rows if r['truth'] in ('good', 'bad')]
    accepted = [r for r in binary if r['prediction'] != 'review']
    bad = [r for r in binary if r['truth'] == 'bad']
    accepted_bad = [r for r in bad if r['prediction'] != 'review']
    def ratio(a, b):
        return a/b if b else None
    per_class = {}
    for label in ('good', 'bad'):
        tp = confusion[label][label]
        # Denominator includes review predictions as missed automatic decisions.
        support = sum(confusion[label].values())
        predicted = sum(confusion[t][label] for t in confusion)
        precision, recall = ratio(tp, predicted), ratio(tp, support)
        f1 = (2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else 0.0)
        per_class[label] = {'precision': precision, 'recall': recall, 'f1': f1, 'support': support}
    return {'tyre_count': len(rows), 'confusion': confusion,
            'binary_truth_count': len(binary),
            'coverage': ratio(len(accepted), len(binary)),
            'review_rate_all': ratio(sum(r['prediction']=='review' for r in rows), len(rows)),
            'accepted_binary_accuracy': ratio(sum(r['truth']==r['prediction'] for r in accepted), len(accepted)),
            'all_binary_correct_auto_fraction': ratio(sum(r['truth']==r['prediction'] for r in binary), len(binary)),
            'unsafe_clearance_rate_all_bad': ratio(confusion['bad']['good'], len(bad)),
            'binary_false_negative_rate_accepted_bad': ratio(confusion['bad']['good'], len(accepted_bad)),
            'per_class': per_class,
            'macro_f1': sum(v['f1'] for v in per_class.values())/2,
            'balanced_accuracy': (sum(v['recall'] for v in per_class.values())/2 if all(v['recall'] is not None for v in per_class.values()) else None)}
