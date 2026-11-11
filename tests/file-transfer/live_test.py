"""Live Supabase API integration check. Reads temporary test users from stdin.
No passwords, user tokens or signed URLs are printed or saved.
Only objects created under the supplied test accounts are deleted.
"""
import json,sys,urllib.request,urllib.error,uuid,time,hashlib,re
from pathlib import Path
cfg=(Path(__file__).resolve().parents[2]/'file-transfer/config.js').read_text()
base=re.search(r"supabaseUrl:\s*'([^']+)'",cfg)[1]
key=re.search(r"publishableKey:\s*'([^']+)'",cfg)[1]
users=json.load(sys.stdin)
def req(path,data=None,token=None,method=None,raw=False,headers=None):
 h={'apikey':key,'Content-Type':'application/json','Cache-Control':'no-cache'}
 if token:h['Authorization']='Bearer '+token
 if headers:h.update(headers)
 body=data if raw else json.dumps(data).encode() if data is not None else None
 r=urllib.request.Request(base+path,data=body,headers=h,method=method or ('POST' if body is not None else 'GET'))
 try:
  with urllib.request.urlopen(r,timeout=45) as response:
   b=response.read();status=response.status
  return status,b if raw else json.loads(b) if b else None
 except urllib.error.HTTPError as e:
  content=e.read().decode();raise RuntimeError('HTTP '+str(e.code)+' '+content) from None
sessions=[];objects=[];reservations=[];checks=0

def passed(name):
 global checks
 checks+=1;print('PASS '+name,flush=True)
try:
 for u in users:
  _,data=req('/auth/v1/token?grant_type=password',{'email':u['email'],'password':u['password']})
  sessions.append(data['access_token']);assert data['user']['id']==u['id']
 passed('two separate temporary accounts authenticate against hosted Supabase')
 a,b=sessions
 payload=b'Relay live cloud verification\n'+uuid.uuid4().bytes*8
 _,f=req('/rest/v1/rpc/transfer_reserve',{'p_filename':'relay-verification.txt','p_size':len(payload),'p_mime':'text/plain'},a)
 if isinstance(f,list):f=f[0]
 reservations.append(f['id'])
 path='/storage/v1/object/pc-transfer/'+f['object_path']
 req(path,payload,a,method='POST',raw=True,headers={'Content-Type':'application/octet-stream','x-upsert':'false','cache-control':'no-store'})
 objects.append(f['object_path'])
 _,listing=req('/rest/v1/transfer_files?select=id,filename,status,size_bytes&status=eq.ready',token=a)
 assert any(x['id']==f['id'] and x['status']=='ready' and x['size_bytes']==len(payload) for x in listing)
 passed('capacity reservation, real Storage upload and ready metadata work')
 # A new login creates an independent session; no upload process or original session is used.
 _,new_login=req('/auth/v1/token?grant_type=password',{'email':users[0]['email'],'password':users[0]['password']})
 other_pc=new_login['access_token']
 _,download=req('/storage/v1/object/authenticated/pc-transfer/'+f['object_path'],token=other_pc,raw=True)
 assert hashlib.sha256(download).digest()==hashlib.sha256(payload).digest()
 passed('independent login downloads identical bytes from cloud storage')
 _,others=req('/rest/v1/transfer_files?select=id',token=b)
 assert not any(x['id']==f['id'] for x in others)
 for token,path_suffix in [(b,'authenticated'),(None,'public')]:
  try:req('/storage/v1/object/'+path_suffix+'/pc-transfer/'+f['object_path'],token=token,raw=True)
  except RuntimeError:pass
  else:raise AssertionError('unauthorized download succeeded')
 passed('another account and anonymous direct access cannot read the object')
 _,signed=req('/storage/v1/object/sign/pc-transfer/'+f['object_path'],{'expiresIn':30},a)
 link=signed.get('signedURL') or signed.get('signedUrl')
 url=base+'/storage/v1'+link if link.startswith('/object/') else link
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Cache-Control':'no-cache'}),timeout=30) as r:shared=r.read()
 assert shared==payload
 passed('signed URL downloads the one private file without login')
 _,short=req('/storage/v1/object/sign/pc-transfer/'+f['object_path'],{'expiresIn':1},a)
 short_link=short.get('signedURL') or short.get('signedUrl')
 short_url=base+'/storage/v1'+short_link if short_link.startswith('/object/') else short_link
 time.sleep(3)
 try:
  with urllib.request.urlopen(short_url+'&fresh='+uuid.uuid4().hex,timeout=30) as response:response.read()
 except urllib.error.HTTPError as error:
  assert error.code in (400,401,403)
 else:raise AssertionError('expired signed URL was accepted')
 passed('expired signed URL rejects a fresh anonymous request')

 try:req('/rest/v1/rpc/transfer_reserve',{'p_filename':'too-large.bin','p_size':50000001,'p_mime':'application/octet-stream'},a)
 except RuntimeError:pass
 else:raise AssertionError('oversize accepted')
 passed('hosted SQL rejects uploads over 50 MB')
 req('/storage/v1/object/pc-transfer',{'prefixes':[f['object_path']]},b,method='DELETE')
 _,still_there=req('/storage/v1/object/authenticated/pc-transfer/'+f['object_path'],token=a,raw=True)
 assert still_there==payload
 passed('other user deletion does not delete the owner file')
 req('/storage/v1/object/pc-transfer',{'prefixes':[f['object_path']]},a,method='DELETE');objects.clear()
 _,listing=req('/rest/v1/transfer_files?select=id',token=a)
 assert not any(x['id']==f['id'] for x in listing)
 try:req('/storage/v1/object/authenticated/pc-transfer/'+f['object_path']+'?fresh='+uuid.uuid4().hex,token=a,raw=True)
 except RuntimeError:pass
 else:raise AssertionError('deleted object still present')
 passed('Storage deletion removes metadata and prevents further downloads')
 _,usage=req('/rest/v1/rpc/transfer_usage',{},a)
 assert usage['own_bytes']==0 and usage['used_bytes']==0
 passed('quota returned to zero after cleanup')
 print(f'{checks} hosted Supabase integration checks passed; no test objects retained.',flush=True)
finally:
 if sessions:
  a=sessions[0]
  if objects:
   try:req('/storage/v1/object/pc-transfer',{'prefixes':objects},a,method='DELETE')
   except Exception as e:print('Cleanup needed for test objects: '+str(e),file=sys.stderr)
  for id in reservations:
   try:req('/rest/v1/rpc/transfer_cancel',{'p_id':id},a)
   except Exception:pass
