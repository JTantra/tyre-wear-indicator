"""Real CLIP projected L2 vision embedding; not zero-shot text matching."""
import io,json
from pathlib import Path
from classifiers.common.acquisition import verify
from classifiers.common.preprocessing import canonical_image
from classifiers.common.numeric_head import load,decision
WEIGHTS=Path(__file__).resolve().parent/'weights'
def encoder(weights=WEIGHTS,backbone=None):
 import torch
 from transformers import CLIPVisionConfig,CLIPVisionModelWithProjection
 weights=Path(weights);folder=Path(backbone) if backbone else (weights/'clip' if (weights/'clip').exists() else WEIGHTS/'clip')
 records=json.loads((WEIGHTS/'pretrained.json').read_text())
 for row in records:verify(folder/Path(row['file']).name,row)
 torch.set_num_threads(4)
 config=json.loads((folder/'config.json').read_text())
 model=CLIPVisionModelWithProjection(CLIPVisionConfig(**config['vision_config']))
 state=torch.load(folder/'pytorch_model.bin',map_location='cpu',weights_only=True)
 state={k:v for k,v in state.items() if k.startswith('vision_model.') or k.startswith('visual_projection.')}
 ids=state.pop('vision_model.embeddings.position_ids',None)
 if ids is not None:assert torch.equal(ids,torch.arange(ids.shape[1]).unsqueeze(0))
 model.load_state_dict(state,strict=True);model.eval();model.requires_grad_(False);return model
def features(model,data,weights=WEIGHTS):
 import torch
 from PIL import Image,ImageOps
 from torchvision.transforms import functional as TF
 config=json.loads((WEIGHTS/'upstream/clip/preprocessor_config.json').read_text())
 mean=config['image_mean'];std=config['image_std'];canonical,_=canonical_image(data)
 with Image.open(io.BytesIO(canonical)) as im:
  image=ImageOps.pad(im.convert('RGB'),(224,224),method=Image.Resampling.BICUBIC,color=tuple(round(v*255) for v in mean))
  tensor=TF.normalize(TF.to_tensor(image),mean,std)
 with torch.inference_mode():
  x=model(pixel_values=tensor.unsqueeze(0),interpolate_pos_encoding=True).image_embeds
  return torch.nn.functional.normalize(x,dim=1).numpy()
def predict(image,weights=WEIGHTS,backbone=None):
 model=encoder(weights,backbone);x=features(model,Path(image).read_bytes(),weights)
 margin=float(decision(load(Path(weights)/'head.json',512),x)[0])
 return dict(prediction='review',needs_review=True,diagnostic_binary_prediction='good' if margin>0 else 'bad',decision_margin=margin,roadworthiness_certified=False,tread_depth_mm=None,evaluation='Fresh-image full-data serving inference; NOT frozen benchmark scoring')
