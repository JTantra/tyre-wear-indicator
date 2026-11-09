"""Actual Responses v2 strict observation schema, not Decisions payload."""
from classifiers.common.luna_rubric import RUBRIC
from classifiers.common.benchmark_contract import clean_image_data_url
def vision_payload(data,deployment,multi=True):
 props={'visual_condition':{'type':'string','enum':['good','bad','review']},'visibility':{'type':'string','enum':['adequate','inadequate','uncertain']},'groove_relief':{'type':'string','enum':['distinct_raised_relief','flattened_or_shallow','obscured_or_uncertain']},'visible_damage':{'type':'string','enum':['yes','no','uncertain']},'evidence':{'type':'string'},'needs_review':{'type':'boolean'},'tread_depth_mm':{'type':'null'},'twi_verified':{'type':'null'}}
 return {'model':deployment,'input':[{'role':'user','content':[{'type':'input_text','text':RUBRIC+' Return compact observations of groove relief, wear, damage and visibility, then condition. needs_review is false for clearly visible bad evidence even if visibility is partial.'},{'type':'input_image','image_url':clean_image_data_url(data)}]}], 'text':{'format':{'type':'json_schema','name':'tyre_visual_condition_v2','strict':True,'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}}}
def parse(body):
 from importlib import import_module
 return import_module('classifiers.luna-decisions.refinement_v3').parse_v2('responses',body,True)
