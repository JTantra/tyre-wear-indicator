"""Shared-password site gate. Never grants paid inference permission.
Password verifier and signing keys arrive via native secret references, not files.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())))
_sys.path.insert(1,str(next(p for p in _Path(__file__).resolve().parents if (p/'export-manifest.json').is_file())/'classifiers/common'))
import hashlib,hmac,json,re,threading,time
from urllib.parse import parse_qs,urlsplit
from dashboard.backend.providers import Registry,LOCAL
from dashboard.backend.session_security import SessionSecurity,b64,unb64

FT_ID='gpt41-vision-ft-pilot'
ITERATIONS=600000
LOGIN=b'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TWI private access</title></head><body><main><h1>Tyre Wear Indicator</h1><p>This research dashboard is password protected. Results require human review and are not roadworthiness certification.</p><form method="post" action="/auth/login"><label>Website password <input name="password" type="password" autocomplete="current-password" required maxlength="256"></label><button type="submit">Open dashboard</button></form></main></body></html>'''
class PasswordGate:
 def __init__(self,verifier,security):
  try:
   if isinstance(verifier,str):verifier=json.loads(verifier)
   if set(verifier)!={'algorithm','iterations','salt','digest'} or verifier['algorithm']!='pbkdf2-sha256' or type(verifier['iterations']) is not int or verifier['iterations']!=ITERATIONS:raise ValueError()
   salt=unb64(verifier['salt']);digest=unb64(verifier['digest'])
   if len(salt)!=16 or len(digest)!=32:raise ValueError()
  except Exception:raise RuntimeError('A valid private site password verifier is required') from None
  self.verifier=verifier;self.salt=salt;self.digest=digest
  fingerprint=hashlib.sha256(json.dumps(verifier,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
  self.signer=SessionSecurity(security.keys,security.current,'tyre-site-gate-v6-'+fingerprint,security.public)
  self.signer.cookie_name='__Host-tyre_gate' if security.public else 'tyre_gate'
  self.lock=threading.Lock();self.window_end=0;self.attempts=0
 @staticmethod
 def derive(password):
  if not isinstance(password,str) or not 16<=len(password)<=256:raise ValueError('Use a password or passphrase of 16 to 256 characters')
  import secrets
  salt=secrets.token_bytes(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,ITERATIONS)
  return {'algorithm':'pbkdf2-sha256','iterations':ITERATIONS,'salt':b64(salt),'digest':b64(digest)}
 def verify(self,password):
  if not isinstance(password,str) or not 1<=len(password)<=256:return False
  actual=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),self.salt,ITERATIONS)
  return hmac.compare_digest(actual,self.digest)
 def from_headers(self,headers):return self.signer.from_headers(headers)
 def allow_attempt(self):
  # Global single-replica throttle; don't trust arbitrary forwarded client-IP headers.
  with self.lock:
   now=time.monotonic()
   if now>=self.window_end:self.window_end=now+60;self.attempts=0
   self.attempts+=1;return self.attempts<=20

class FourOptionRegistry(Registry):
 def __init__(self,remote=None):
  if remote is not None and getattr(remote,'durable_job_checkpoint_contract',None)!='public-server-v4/1':raise RuntimeError('Verified durable paid adapter required')
  self.remote=remote;self.remote_error=None
 def methods(self):
  rows=[dict(r) for r in super().methods() if r['id'] in LOCAL]
  for n,row in enumerate(rows,1):row.update(option_number=n,label=str(n)+'. '+LOCAL[row['id']][0])
  ft=next((dict(r) for r in self.remote.methods() if r['id']==FT_ID),None) if self.remote else None
  if ft is None:ft={'id':FT_ID,'family':'vision-finetune','status':'unavailable','reason':'Paid inference disabled: shared ledger halt and website managed-identity serving verification remain unresolved.','paid':True,'cloud':True,'requires_paid_consent':True,'is_async':False}
  ft.update(option_number=4,label='4. GPT-4.1 Vision / fine-tuned pilot',paid=True,evaluation_population=9,operational_policy='Mandatory human review; nine-photo development result is not production accuracy or roadworthiness evidence.')
  return rows+[ft]
 def infer(self,method_id,path,context):
  if method_id not in {*LOCAL,FT_ID}:raise PermissionError('Only the four selected website methods are permitted')
  if method_id==FT_ID and next(r for r in self.methods() if r['id']==FT_ID)['status']!='available':raise PermissionError('Fine-tuned serving access is not verified or authorized')
  return super().infer(method_id,path,context)

def wrap_handler(base,gate):
 from dashboard.backend import server
 class GatedHandler(base):
  def auth_response(self,status,body=b'',location=None,cookies=(),json_response=False):
   if json_response:body=json.dumps({'error':body}).encode()
   self.send_response(status);self.send_header('Content-Type','application/json' if json_response else 'text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)))
   self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
   if gate.signer.public:self.send_header('Strict-Transport-Security','max-age=31536000')
   if location:self.send_header('Location',location)
   if status==429:self.send_header('Retry-After','60')
   for cookie in cookies:self.send_header('Set-Cookie',cookie)
   self.close_connection=True;self.send_header('Connection','close');self.end_headers()
   if self.command!='HEAD':self.wfile.write(body)
  def auth_origin(self,write=False):
   if server.POLICY is None or not server.POLICY.check(self.headers,write):self.auth_response(403,'Allowed site origin required',json_response=True);return False
   return True
  def guard(self,write=False):
   if not self.auth_origin(write):return False
   if not gate.from_headers(self.headers):
    if self.command in {'GET','HEAD'} and not urlsplit(self.path).path.startswith('/api/'):self.auth_response(303,location='/auth/login')
    else:self.auth_response(401,'Website password required',json_response=True)
    return False
   return super().guard(write)
  def do_GET(self):
   if urlsplit(self.path).path=='/auth/login':
    if self.auth_origin():self.auth_response(200,LOGIN)
    return
   super().do_GET()
  def do_POST(self):
   path=urlsplit(self.path).path
   if path=='/auth/login':
    if not self.auth_origin(True):return
    lengths=self.headers.get_all('Content-Length',[])
    if len(lengths)!=1 or not re.fullmatch('[0-9]{1,5}',lengths[0]) or self.headers.get_all('Transfer-Encoding',[]):self.auth_response(400,'Invalid login body',json_response=True);return
    length=int(lengths[0])
    if length>4096:self.auth_response(413,'Login body too large',json_response=True);return
    if self.headers.get_all('Content-Type',[])!=['application/x-www-form-urlencoded']:self.auth_response(415,'Use the website login form',json_response=True);return
    if not gate.allow_attempt():self.auth_response(429,'Too many login attempts; wait one minute',json_response=True);return
    try:
     form=parse_qs(self.read_body(length).decode('utf-8'),keep_blank_values=True,strict_parsing=True,max_num_fields=2)
     if set(form)!={'password'} or len(form['password'])!=1:raise ValueError()
     valid=gate.verify(form['password'][0])
    except (ValueError,UnicodeError,OSError,TimeoutError):self.auth_response(400,'Invalid login form',json_response=True);return
    if not valid:self.auth_response(401,'Incorrect website password',json_response=True);return
    token,_=gate.signer.issue();self.auth_response(303,location='/',cookies=[gate.signer.cookie(token)]);return
   if path=='/auth/logout':
    if not self.guard(True):return
    cookies=[s.cookie('').replace('Max-Age='+str(s.ttl),'Max-Age=0') for s in [gate.signer,server.SECURITY]]
    self.auth_response(303,location='/auth/login',cookies=cookies);return
   super().do_POST()
  def do_HEAD(self):
   if self.guard():self.auth_response(405,'Method not allowed',json_response=True)
  def do_OPTIONS(self):
   if self.guard():self.auth_response(405,'Method not allowed',json_response=True)
  do_PUT=do_OPTIONS
  do_DELETE=do_OPTIONS
 return GatedHandler
