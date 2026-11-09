import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import io,json,subprocess,sys,time,unittest,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
from dashboard.backend.server import validate_image,MAX_BYTES,MAX_PIXELS
ROOT=Path(__file__).resolve().parents[next(i for i,p in enumerate(Path(__file__).resolve().parents) if (p/'export-manifest.json').is_file())]
class UploadValidation(unittest.TestCase):
 def test_paid_consent_blocks_adapter_call(self):
  from dashboard.backend.providers import Registry
  registry=Registry.__new__(Registry)
  class NeverCalled:
   def infer(self,*args):raise AssertionError('Remote provider must not be called')
  registry.remote=NeverCalled()
  with self.assertRaises(PermissionError):registry.infer('remote-test',ROOT/'does-not-exist',{'paid_consent':False})
 @unittest.skip("Private source photo excluded from publication")
 def test_truncated_image(self):
  manifest=json.loads((ROOT/'artifacts/manifest.json').read_text())
  data=(ROOT/'data/extracted'/manifest[0]['file']).read_bytes()
  with self.assertRaises(ValueError):validate_image(data[:1000])
 def test_invalid_decode(self):
  with self.assertRaises(ValueError):validate_image(b'not an image')
 def test_size_limit(self):
  with self.assertRaises(ValueError):validate_image(b'x'*(MAX_BYTES+1))
 def test_pixel_limit(self):
  from PIL import Image
  out=io.BytesIO();Image.new('L',(4001,4000)).save(out,format='PNG')
  with self.assertRaises(ValueError):validate_image(out.getvalue())
