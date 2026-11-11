"""Local UI/API-contract tests; mock endpoints do not prove live Supabase works."""
from pathlib import Path
import http.server, threading, functools, json, uuid, re, io
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}/file-transfer/'
A='11111111-1111-4111-8111-111111111111'
try:
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(base,wait_until='networkidle')
  assert page.locator('#setup-notice').is_visible()
  assert page.locator('#upload-top').is_disabled() and page.locator('#login').is_disabled()
  assert page.locator('#file-list tr').count()==0
  page.screenshot(path=str(root.parent/'relay-unconfigured.png'))
  print('PASS unconfigured state is explicit and cloud actions are disabled')
  state={'files':{},'bytes':{},'stop':False,'deny_usage':False,'bad_size':False}
  api_calls=[]
  def route_api(route):
   req=route.request;u=urlparse(req.url);path=u.path;method=req.method
   if method=='OPTIONS':
    route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'GET,POST,DELETE,PUT,OPTIONS'});return
   api_calls.append((method,path))
   def reply(data,status=200,raw=False):route.fulfill(status=status,body=data if raw else json.dumps(data),headers={'access-control-allow-origin':'*','content-type':'application/octet-stream' if raw else 'application/json'})
   data={}
   if 'application/json' in req.headers.get('content-type','') and req.post_data:
    data=json.loads(req.post_data)
   if path=='/auth/v1/token':
    assert 'authorization' not in req.headers,'Public key must not be sent as a bearer token on unauthenticated Auth calls'
    return reply({'access_token':'test-user-token','refresh_token':'refresh-test','expires_in':3600,'user':{'id':A,'email':'test@example.com'}})
   if path=='/auth/v1/user':return reply({'id':A,'email':'test@example.com'})
   if path=='/auth/v1/logout':return reply(None,204)
   if path.endswith('/transfer_usage'):
    if state['deny_usage']:return reply({'message':'quota check unavailable'},503)
    return reply({'used_bytes':sum(f['size_bytes'] for f in state['files'].values()),'own_bytes':sum(f['size_bytes'] for f in state['files'].values()),'limit_bytes':800000000,'file_limit':50000000,'uploads_enabled':not state['stop'],'reason':'管理者が停止中' if state['stop'] else ''})
   if path.endswith('/transfer_reserve'):
    if state['stop']:return reply({'message':'管理者が停止中'},400)
    id=str(uuid.uuid4());f={'id':id,'filename':data['p_filename'],'size_bytes':data['p_size'],'mime_type':data['p_mime'],'created_at':'2026-11-11T03:00:00Z','object_path':A+'/'+id,'status':'pending'};state['files'][id]=f;return reply(f)
   if path.endswith('/transfer_cancel'):
    f=state['files'].get(data['p_id'])
    if f and f['status']=='pending':del state['files'][f['id']]
    return reply(None,204)
   if path=='/rest/v1/transfer_files':
    offset=int(parse_qs(u.query).get('offset',['0'])[0]);return reply([f for f in state['files'].values() if f['status']=='ready'][offset:offset+500])
   if '/storage/v1/object/sign/' in path:
    return reply({'signedURL':path.replace('/storage/v1','')+'?token=limited-capability'})
   if '/storage/v1/object/authenticated/' in path:
    object_path=path.split('/pc-transfer/')[1];return reply(state['bytes'][object_path],raw=True)
   if path=='/storage/v1/object/pc-transfer' and method=='DELETE':
    for key in data['prefixes']:
     state['bytes'].pop(key,None)
     for id,f in list(state['files'].items()):
      if f['object_path']==key:del state['files'][id]
    return reply([])
   if '/storage/v1/object/pc-transfer/' in path and method=='POST':
    assert req.headers['content-type']=='application/octet-stream'
    key=path.split('/pc-transfer/')[1];payload=req.post_data_buffer
    f=next(f for f in state['files'].values() if f['object_path']==key)
    assert len(payload)==f['size_bytes']
    state['bytes'][key]=payload;f['status']='ready';return reply({'Key':key})
   return reply({'message':'unexpected mock endpoint '+path},500)
  page.route('**/config.js',lambda route:route.fulfill(body="window.TRANSFER_CONFIG={supabaseUrl:'https://testproject.supabase.co',publishableKey:'sb_publishable_test_public_only',bucket:'pc-transfer'};",content_type='application/javascript'))
  page.route('https://testproject.supabase.co/**',route_api)
  page.goto(base,wait_until='networkidle')
  page.locator('#email').fill('test@example.com');page.locator('#password').fill('test-password-123');page.locator('#login').click()
  expect(page.locator('#upload-top')).to_be_enabled()
  unsafe=b'<script>window.INJECTED=true</script><h1>Not executable</h1>'
  filename='<img src=x onerror=alert(1)>.html'
  page.locator('#file-input').set_input_files([{'name':filename,'mimeType':'text/html','buffer':unsafe},{'name':'notes.txt','mimeType':'text/plain','buffer':b'hello from PC A'},{'name':'photo.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082')}])
  expect(page.locator('#file-list tr')).to_have_count(3)
  assert '3件中3件' in page.locator('#toast').inner_text()
  assert page.evaluate('window.INJECTED') is None
  print('PASS multiple actual request bodies, progress completion, list and filename escaping')
  # Simulated separate PC context: no shared sessionStorage, same cloud-side mock state.
  pc_b=b.new_page(viewport={'width':1280,'height':900});pc_b.route('**/config.js',lambda route:route.fulfill(body="window.TRANSFER_CONFIG={supabaseUrl:'https://testproject.supabase.co',publishableKey:'sb_publishable_test_public_only',bucket:'pc-transfer'};",content_type='application/javascript'));pc_b.route('https://testproject.supabase.co/**',route_api)
  pc_b.goto(base);assert pc_b.locator('#auth-panel').is_visible()
  pc_b.locator('#email').fill('test@example.com');pc_b.locator('#password').fill('test-password-123');pc_b.locator('#login').click();expect(pc_b.locator('#file-list tr')).to_have_count(3)
  row=pc_b.locator('tr').filter(has_text='notes.txt')
  with pc_b.expect_download() as d:row.get_by_role('button',name='notes.txtをダウンロード',exact=True).click()
  assert Path(d.value.path()).read_bytes()==b'hello from PC A'
  pc_b.close()
  print('PASS independent browser session lists stored records and downloads matching bytes (mock cloud)')
  page.get_by_role('button',name=filename+'をプレビュー',exact=True).click();page.locator('#preview-content pre').wait_for()
  assert page.locator('#preview-content pre').inner_text()==unsafe.decode()
  assert page.evaluate('window.INJECTED') is None
  page.get_by_role('button',name='プレビューを閉じる').click()
  page.locator('#search').fill('notes');assert page.locator('#file-list tr').count()==1;page.locator('#search').fill('')
  page.get_by_role('button',name='notes.txtの共有リンク',exact=True).click();page.locator('#share-duration').select_option('300');page.locator('#create-share').click();expect(page.locator('#share-url')).not_to_have_value('')
  link=page.locator('#share-url').input_value();assert link.startswith('https://testproject.supabase.co/storage/v1/object/sign/pc-transfer/') and 'download=notes.txt' in link
  page.get_by_role('button',name='共有を閉じる').click()
  print('PASS HTML preview is plain text, search, signed download URL contract and duration selection')
  page.locator('[data-filter="images"]').click();assert page.locator('#file-list tr').count()==1;page.locator('[data-filter="all"]').click()
  page.locator('#sort').select_option('name')
  page.screenshot(path=str(root.parent/'relay-files.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.screenshot(path=str(root.parent/'relay-mobile.png'),full_page=True)
  print('PASS category filters, sort control and responsive mobile layout')
  state['stop']=True;page.locator('#refresh').click();expect(page.locator('#upload-top')).to_be_disabled()
  assert page.locator('#drop-zone').get_attribute('aria-disabled')=='true'
  state['stop']=False;state['deny_usage']=True;page.locator('#refresh').click();page.wait_for_timeout(100);assert page.locator('#upload-top').is_disabled()
  state['deny_usage']=False;page.locator('#refresh').click();expect(page.locator('#upload-top')).to_be_enabled()
  page.locator('#file-input').set_input_files({'name':'empty.txt','mimeType':'text/plain','buffer':b''});expect(page.locator('#queue-list')).to_contain_text('空のファイル')
  print('PASS administrative stop, fail-closed quota check and zero-byte rejection')
  page.locator('#select-all').check();page.locator('#delete-selected').click();page.locator('#confirm-cancel').click();assert page.locator('#file-list tr').count()==3
  page.locator('#delete-selected').click();page.locator('#confirm-delete').click();expect(page.locator('#file-list tr')).to_have_count(0)
  page.locator('#logout').click();expect(page.locator('#auth-panel')).to_be_visible()
  assert page.evaluate('sessionStorage.length')==0
  assert not errors,errors
  print('PASS deletion confirmation/cancellation, bulk delete, logout cleanup; no page errors')
  b.close()
finally:server.shutdown()
