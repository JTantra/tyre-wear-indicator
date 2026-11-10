"""Method-specific public local inference entrypoint; no network."""
from classifiers.common.foundation_next import predict as _predict
from classifiers.common.foundation_next_integrity import verify
def predict(image,weights,head):
 verify('siglip2',weights)
 return _predict('siglip2',image,weights,head)
