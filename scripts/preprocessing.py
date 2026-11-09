"""Shared, enhancement-free full-image canonical pipeline for every method.

Originals are read only. No contrast/exposure/sharpness/denoise operations.
Quality flags are uncalibrated diagnostics, NOT automatic rejection or visibility.
"""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

PIPELINE_VERSION='full-frame-rgb-v1'
MAX_IMAGE_SIDE=1024
QUALITY_THRESHOLDS={'dark_pixel_luma':32,'dark_fraction_warn':.35,'clip_low':4,
                    'clip_high':251,'clipped_fraction_warn':.10,'laplacian_variance_blur_warn':50.}


def canonical_image(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as im:
        im.load(); source_size=list(im.size); orientation=im.getexif().get(274)
        image=ImageOps.exif_transpose(im).convert('RGB')
        image.thumbnail((MAX_IMAGE_SIDE,MAX_IMAGE_SIDE),Image.Resampling.LANCZOS)
        output=io.BytesIO(); image.save(output,format='JPEG',quality=95,subsampling=0)
        data=output.getvalue()
    # All methods consume exactly these canonical JPEG bytes before their explicit
    # model-specific shape adaptation; calculate diagnostics on those decoded pixels.
    with Image.open(io.BytesIO(data)) as decoded:
        gray=np.asarray(decoded.convert('L'),dtype=np.float64)
        lap=-4*gray[1:-1,1:-1]+gray[:-2,1:-1]+gray[2:,1:-1]+gray[1:-1,:-2]+gray[1:-1,2:]
        dark=float(np.mean(gray<QUALITY_THRESHOLDS['dark_pixel_luma']))
        low=float(np.mean(gray<=QUALITY_THRESHOLDS['clip_low']))
        high=float(np.mean(gray>=QUALITY_THRESHOLDS['clip_high']))
        blur=float(np.var(lap)) if lap.size else None
        flags=[]
        if dark>.35:flags.append('dark_fraction_warning')
        if low>.10:flags.append('shadow_clipping_warning')
        if high>.10:flags.append('highlight_clipping_warning')
        if blur is not None and blur<50.:flags.append('possible_blur_warning')
        record={'pipeline_version':PIPELINE_VERSION,'source_sha256':hashlib.sha256(image_bytes).hexdigest(),
                'canonical_sha256':hashlib.sha256(data).hexdigest(),'source_dimensions':source_size,
                'canonical_dimensions':list(decoded.size),'exif_orientation_applied':orientation,
                'color':'RGB','resize':'aspect-ratio-preserving thumbnail, LANCZOS, longest side <=1024, no upscale',
                'encoding':'JPEG quality95 subsampling0, metadata stripped','enhancements':[],
                'quality':{'mean_luma':float(gray.mean()),'luma_std':float(gray.std()),
                    'dark_fraction':dark,'shadow_clipped_fraction':low,'highlight_clipped_fraction':high,
                    'laplacian_variance':blur,'flags':flags,'thresholds':QUALITY_THRESHOLDS,
                    'calibrated':False,'automatic_rejection':False},
                'tread_visibility':{'status':'unassessed','method':'Requires expert or separately evaluated model; blur/exposure do not establish tread visibility.'}}
    return data,record


def build_preprocessing_manifest(root):
    import json
    rows=json.loads((root/'artifacts/manifest.json').read_text()); records=[]
    for r in rows:
        _,record=canonical_image((root/'data/extracted'/r['file']).read_bytes())
        records.append(dict(record,index=r['index']))
    result={'version':PIPELINE_VERSION,'originals_preserved':True,'records':records,
            'model_specific':{'classifier':'Decode canonical JPEG; aspect-preserving ImageOps.pad to224 with neutral RGB124/116/104; ImageNet channel normalize; no crop.',
             'decisions':'Same canonical full-frame JPEG pixels, no crop; service-internal processing unknown.',
             'vision':'Same canonical full-frame JPEG pixels, no crop; service-internal processing unknown.'},
            'quality_policy':'Diagnostics only. Thresholds provisional, not validated; tread visibility unassessed. No exposure/contrast/sharpness enhancement. No illumination ablation executed.'}
    target=root/'artifacts/preprocessing_manifest.json'; target.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import json
    print(json.dumps(build_preprocessing_manifest(Path(__file__).resolve().parents[1]),indent=2))
