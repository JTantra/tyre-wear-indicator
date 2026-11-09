"""Hosted GPT checkpoint only; no fictional local weights."""
def predict(image,config=None,execute=False,approval=None,**unused):
 from classifiers.common.approval import require
 if not execute:raise PermissionError('Hosted inference requires --execute and fresh approval')
 require(approval,'gpt-inference')
 from importlib import import_module
 from pathlib import Path
 result=import_module('classifiers.gpt41-finetuned.adapter').infer('gpt41-vision-ft-pilot',Path(image).read_bytes(),cloud_send_consent=True)
 if result.get('status')!='complete':raise RuntimeError(result.get('error','Hosted model unavailable'))
 return dict(status='complete',prediction='review',diagnostic_prediction=result['visual_condition'],needs_review=True,evaluation='Genuine approved hosted API; NOT benchmark replay')
