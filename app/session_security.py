"""Purpose-bound, restart-verifiable sessions. Secrets never enter projections/logs."""
import base64, hashlib, hmac, json, os, re, secrets, time
from dataclasses import dataclass
from urllib.parse import urlsplit


def b64(data): return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')
def unb64(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value): raise ValueError('Invalid encoding')
    data = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if b64(data) != value: raise ValueError('Noncanonical encoding')
    return data

def owner_hash(owner): return hashlib.sha256(owner.encode()).hexdigest()

@dataclass(frozen=True)
class Session:
    id: str
    nonce: str
    issued: int
    expires: int
    kid: str
    csrf: str

class SessionSecurity:
    def __init__(self, keys, current, audience, public=False, ttl=3600):
        if not keys or current not in keys or len(keys)>8: raise RuntimeError('Signing key ring/current key required')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', k) or len(v)<32 or len(v)>64 for k,v in keys.items()):
            raise RuntimeError('Invalid signing key ring')
        self.keys, self.current, self.audience, self.public, self.ttl = keys, current, audience, public, ttl
        self.cookie_name = '__Host-tyre_session' if public else 'tyre_session'
    @classmethod
    def from_env(cls, public=False):
        raw=os.environ.get('TYRE_SESSION_KEYRING')
        if not raw:
            if public: raise RuntimeError('Persistent shared signing key ring required')
            keys={'dev': secrets.token_bytes(32)}; current='dev'
        else:
            try:
                value=json.loads(raw); keys={k:unb64(v) for k,v in value.items()}; current=os.environ['TYRE_SESSION_CURRENT_KID']
            except Exception: raise RuntimeError('Invalid session key configuration') from None
        audience=os.environ.get('TYRE_SESSION_AUDIENCE', 'tyre-wear-indicator')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', audience): raise RuntimeError('Invalid session audience')
        return cls(keys,current,audience,public)
    def mac(self, kid, purpose, data):
        return b64(hmac.new(self.keys[kid], (purpose+'\0'+self.audience+'\0'+data).encode(), hashlib.sha256).digest())
    def issue(self, owner=None):
        t=int(time.time()); owner=owner or secrets.token_hex(16)
        if not re.fullmatch('[a-f0-9]{32}',owner): raise ValueError('Invalid owner')
        payload={'v':1,'kid':self.current,'owner':owner,'nonce':secrets.token_hex(16),'iat':t,'exp':t+self.ttl,'aud':self.audience,'purpose':'session'}
        encoded=b64(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())
        cookie=encoded+'.'+self.mac(self.current,'session',encoded)
        return cookie,self.verify(cookie)
    def verify(self, cookie):
        try:
            if not isinstance(cookie,str) or len(cookie)>1024: return None
            encoded,sig=cookie.split('.')
            p=json.loads(unb64(encoded)); kid=p['kid']
            if set(p)!={'v','kid','owner','nonce','iat','exp','aud','purpose'} or kid not in self.keys: return None
            if not hmac.compare_digest(sig,self.mac(kid,'session',encoded)): return None
            if type(p['v']) is not int or p['v']!=1 or p['aud']!=self.audience or p['purpose']!='session': return None
            if type(p['iat']) is not int or type(p['exp']) is not int or not p['iat']<=time.time()+30 or p['exp']<=time.time() or not 0<p['exp']-p['iat']<=self.ttl: return None
            if not all(isinstance(p[k],str) and re.fullmatch('[a-f0-9]{32}',p[k]) for k in ('owner','nonce')): return None
            csrf=self.mac(kid,'csrf',p['owner']+'\0'+p['nonce']+'\0'+str(p['exp']))
            return Session(p['owner'],p['nonce'],p['iat'],p['exp'],kid,csrf)
        except (ValueError,KeyError,TypeError): return None
    def cookie(self, value):
        return self.cookie_name+'='+value+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+str(self.ttl)+('; Secure' if self.public else '')
    def from_headers(self, headers):
        values=[]
        for header in headers.get_all('Cookie',[]):
            for item in header.split(';'):
                if '=' in item:
                    k,v=item.strip().split('=',1)
                    if k==self.cookie_name: values.append(v)
        return self.verify(values[0]) if len(values)==1 else None

class OriginPolicy:
    def __init__(self, public=False, origins=(), port=8765, ingress=False):
        self.public=public; self.ingress=ingress; self.authorities={}
        if public and not ingress: raise RuntimeError('Public mode requires enforced ACA HTTPS ingress boundary')
        for origin in origins:
            p=urlsplit(origin)
            try: _=p.port
            except ValueError: raise RuntimeError('Invalid public origin') from None
            if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or '*' in origin or p.netloc!=p.netloc.lower() or origin!='https://'+p.netloc:
                raise RuntimeError('Exact HTTPS origins required')
            if not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]{1,5})?',p.netloc): raise RuntimeError('Invalid public authority')
            self.authorities[p.netloc]=origin
        if public and not self.authorities: raise RuntimeError('Explicit public HTTPS origins required')
        if not public: self.authorities={h+':'+str(port):'http://'+h+':'+str(port) for h in ('127.0.0.1','localhost')}
    def check(self, headers, write=False):
        hosts=headers.get_all('Host',[])
        if len(hosts)!=1 or hosts[0] not in self.authorities: return False
        if self.public and headers.get_all('X-Forwarded-Proto',[])!=['https']: return False
        origins=headers.get_all('Origin',[])
        effective=self.authorities[hosts[0]]
        if len(origins)>1 or (origins and origins[0]!=effective): return False
        if write and origins!=[effective]: return False
        if headers.get_all('Sec-Fetch-Site',[]) and (len(headers.get_all('Sec-Fetch-Site'))!=1 or headers['Sec-Fetch-Site'] not in {'same-origin','none'}): return False
        return True

def recovery_capability(owner): return owner+'.'+secrets.token_urlsafe(32)
def recovery_parts(token):
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}\.[A-Za-z0-9_-]{43}',token): raise ValueError('Invalid recovery capability')
    return token.split('.')[0],hashlib.sha256(token.encode()).hexdigest()
