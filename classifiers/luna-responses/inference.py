"""Genuine responses path with method-owned rubric and explicit approval."""
def predict(image,config=None,execute=False,approval=None,**unused):
 from classifiers.common.luna_single import predict as actual
 return actual('luna-responses',image,config,execute,approval)
