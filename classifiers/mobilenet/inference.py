"""mobilenet: real frozen ImageNet features + saved numeric final head."""
import io,json
from pathlib import Path
from classifiers.common.acquisition import verify
from classifiers.common.preprocessing import canonical_image
from classifiers.common.numeric_head import load,decision
WEIGHTS=Path(__file__).resolve().parent/'weights'
def encoder(weights=WEIGHTS,backbone=None):
 import torch
 from torchvision import models
 weights=Path(weights);pin=json.loads((WEIGHTS/'pretrained.json').read_text())[0]
 path=verify(backbone or (weights/'backbone.pth' if (weights/'backbone.pth').exists() else WEIGHTS/'backbone.pth'),pin)
 torch.set_num_threads(4)
 model=models.mobilenet_v3_large(weights=None)
 model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True)
 model.classifier=torch.nn.Identity()
 model.eval();model.requires_grad_(False);return model
def features(model,data,weights=WEIGHTS):
 import torch
 from PIL import Image,ImageOps
 from torchvision.transforms import functional as TF
 canonical,_=canonical_image(data)
 with Image.open(io.BytesIO(canonical)) as im:
  image=ImageOps.pad(im.convert('RGB'),(224,224),color=(124,116,104),method=Image.Resampling.BILINEAR)
  tensor=TF.normalize(TF.to_tensor(image),[.485,.456,.406],[.229,.224,.225])
 with torch.inference_mode():return model(tensor.unsqueeze(0)).numpy()
def predict(image,weights=WEIGHTS,backbone=None):
 import math
 model=encoder(weights,backbone);x=features(model,Path(image).read_bytes(),weights)
 margin=float(decision(load(Path(weights)/'head.json',x.shape[1]),x)[0])
 result=dict(prediction='review',needs_review=True,diagnostic_binary_prediction='good' if margin>0 else 'bad',decision_margin=margin,roadworthiness_certified=False,tread_depth_mm=None,evaluation='Fresh-image full-data serving inference; NOT frozen benchmark scoring')

 return result
