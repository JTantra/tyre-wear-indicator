"""Pinned frozen CPU image representations. Local files only; never remote code."""
import hashlib,io,json,time
from pathlib import Path
SPECS={
 'clip':dict(repo='openai/clip-vit-base-patch32',revision='3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268',checkpoint='pytorch_model.bin',pooling='projected L2-normalized image embedding',license='Upstream CLIP MIT; separate mirror weight license unspecified'),
 'dinov3':dict(repo='facebook/dinov3-vits16-pretrain-lvd1689m',revision='114c1379950215c8b35dfcd4e90a5c251dde0d32',checkpoint='model.safetensors',pooling='official CLS pooler_output; no patch/pooling search',license='DINOv3 custom gated terms; no acceptance authorized'),
 'siglip2':dict(repo='google/siglip2-base-patch16-224',revision='75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2',checkpoint='model.safetensors',pooling='official get_image_features = attention pooled vision pooler_output, no extra L2 normalization',license='Apache-2.0 official pinned model card')}
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def load_backbone(name,folder):
 import torch
 from safetensors.torch import load_file
 from transformers import CLIPVisionConfig,CLIPVisionModelWithProjection,SiglipVisionConfig,SiglipVisionModel,DINOv3ViTConfig,DINOv3ViTModel
 folder=Path(folder);cfg=json.loads((folder/'config.json').read_text())
 if name=='clip':
  model=CLIPVisionModelWithProjection(CLIPVisionConfig(**cfg['vision_config']))
  state=torch.load(folder/'pytorch_model.bin',map_location='cpu',weights_only=True)
  state={k:v for k,v in state.items() if k.startswith(('vision_model.','visual_projection.'))}
  ids=state.pop('vision_model.embeddings.position_ids',None)
  if ids is not None and not torch.equal(ids,torch.arange(ids.shape[1]).unsqueeze(0)):raise ValueError('Unexpected legacy position ids')
 elif name=='siglip2':
  model=SiglipVisionModel(SiglipVisionConfig(**cfg['vision_config']))
  state={k:v for k,v in load_file(str(folder/'model.safetensors')).items() if k.startswith('vision_model.')}
 elif name=='dinov3':
  model=DINOv3ViTModel(DINOv3ViTConfig(**cfg));state=load_file(str(folder/'model.safetensors'))
 else:raise ValueError('Unknown representation')
 model.load_state_dict(state,strict=True);model.eval();model.requires_grad_(False);return model

def adapt(image,folder):
 import torch,numpy as np
 from PIL import Image,ImageOps
 cfg=json.loads((Path(folder)/'preprocessor_config.json').read_text());mean=cfg['image_mean'];std=cfg['image_std']
 image=ImageOps.pad(image,(224,224),method=Image.Resampling(cfg.get('resample',3)),color=tuple(round(x*255) for x in mean))
 # Same float32 arithmetic as torchvision ToTensor + Normalize, no stretch/crop.
 x=torch.from_numpy(np.array(image,dtype=np.uint8).transpose(2,0,1).copy()).float().div(255.)
 return (x-torch.tensor(mean)[:,None,None])/torch.tensor(std)[:,None,None]
def extract(model,tensors,name,batch_size=4):
 import torch,numpy as np
 blocks=[]
 with torch.inference_mode():
  for i in range(0,len(tensors),batch_size):
   output=model(pixel_values=torch.stack(tensors[i:i+batch_size]))
   x=torch.nn.functional.normalize(output.image_embeds,dim=1) if name=='clip' else output.pooler_output
   blocks.append(x.cpu().numpy())
 return np.concatenate(blocks)
def canonical(source):
 from PIL import Image
 from classifiers.common.preprocessing import canonical_image
 data,record=canonical_image(source)
 with Image.open(io.BytesIO(data)) as im:image=im.convert('RGB')
 return image,record
def predict(name,image_path,weights,head):
 import torch
 from classifiers.common.numeric_linear_head import load,decision
 torch.set_num_threads(4)
 # Decode/validate local image before loading large checkpoint. No network here.
 image,_=canonical(Path(image_path).read_bytes());x=extract(load_backbone(name,weights),[adapt(image,weights)],name)
 margin=float(decision(load(head,x.shape[1]),x)[0])
 return dict(forced_binary_prediction='good' if margin>0 else 'bad',decision_margin=margin,operational_prediction='review',visibility='unassessed',evaluation='Full-data artifact inference, not held-out accuracy')
