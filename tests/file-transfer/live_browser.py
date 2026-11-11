"""Real Chromium + real Supabase, credentials only via stdin; no mocked endpoints."""
import os,json,sys,http.server,threading,functools,uuid,urllib.request,urllib.error,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[2]
users=json.load(sys.stdin)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/file-transfer/'
name='relay-browser-'+uuid.uuid4().hex+'.txt';payload=b'Relay real browser cloud transfer verification\n'
try:
 with sync_playwright() as p:
  options={'executable_path':'/usr/bin/chromium','headless':True,'args':['--no-sandbox']}
  proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
  bridge=os.environ.get('RELAY_VERIFIED_HTTPS_BRIDGE')=='1'
  if proxy and not bridge:options['proxy']={'server':proxy,'bypass':'127.0.0.1,localhost'}
  browser=p.chromium.launch(**options)
  def new_context():
   context=browser.new_context()
   if bridge:
    # Cloud Chromium does not trust the executor's HTTPS inspection CA.
    # Forward bytes through urllib with inherited CA trust and TLS verification ON.
    # All responses come from the real project; no fixture/mocked data is used.
    def forward(route):
     request=route.request
     headers={k:v for k,v in request.headers.items() if k.lower() not in ['host','content-length','connection','accept-encoding']}
     upstream=urllib.request.Request(request.url,data=request.post_data_buffer,method=request.method,headers=headers)
     try:response=urllib.request.urlopen(upstream,timeout=45)
     except urllib.error.HTTPError as e:response=e
     with response:
      body=response.read();response_headers={k:v for k,v in response.headers.items() if k.lower() not in ['content-length','transfer-encoding','content-encoding','connection']}
      route.fulfill(status=response.status,headers=response_headers,body=body)
    cfg=(root/'file-transfer/config.js').read_text();endpoint=re.search(r"supabaseUrl:\s*'([^']+)'",cfg)[1]
    context.route(endpoint+'/**',forward)
   return context
  page=new_context().new_page();page.set_viewport_size({'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  failures=[];page.on('requestfailed',lambda r:failures.append((r.url.split('?')[0],r.failure)))
  page.goto(url,wait_until='networkidle')
  assert not page.locator('#setup-notice').is_visible()
  page.locator('#email').fill(users[0]['email']);page.locator('#password').fill(users[0]['password']);page.locator('#login').click()
  try:expect(page.locator('#upload-top')).to_be_enabled(timeout=10000)
  except Exception:
   print('Browser diagnostic:',failures,'notice:',page.locator('#toast').text_content(),flush=True)
   raise
  page.locator('#file-input').set_input_files({'name':name,'mimeType':'text/plain','buffer':payload})
  expect(page.locator('#file-list tr').filter(has_text=name)).to_have_count(1,timeout=45000)
  print('PASS real browser logs in and uploads through Supabase Storage',flush=True)
  # Close original page. A separate context has no sessionStorage from that page.
  page.close()
  pc_b=new_context().new_page();pc_b.goto(url)
  pc_b.locator('#email').fill(users[0]['email']);pc_b.locator('#password').fill(users[0]['password']);pc_b.locator('#login').click()
  row=pc_b.locator('#file-list tr').filter(has_text=name);expect(row).to_have_count(1,timeout=45000)
  with pc_b.expect_download(timeout=45000) as info:row.get_by_role('button',name=name+'をダウンロード',exact=True).click()
  assert Path(info.value.path()).read_bytes()==payload
  print('PASS new isolated browser context downloads identical bytes after original page closes',flush=True)
  row.get_by_role('button',name=name+'をプレビュー',exact=True).click();expect(pc_b.locator('#preview-content pre')).to_have_text(payload.decode().strip())
  pc_b.get_by_role('button',name='プレビューを閉じる').click()
  row.get_by_role('button',name=name+'の共有リンク',exact=True).click();pc_b.locator('#create-share').click();expect(pc_b.locator('#share-url')).not_to_have_value('',timeout=45000)
  pc_b.get_by_role('button',name='共有を閉じる').click()
  row.get_by_role('button',name=name+'を削除',exact=True).click();pc_b.locator('#confirm-delete').click();expect(row).to_have_count(0,timeout=45000)
  pc_b.locator('#logout').click();expect(pc_b.locator('#auth-panel')).to_be_visible(timeout=45000)
  assert not errors,errors
  print('PASS real preview, shared URL creation, deletion and logout; no page errors',flush=True)
  if bridge:print('Transport note: verified HTTPS bridge used for executor CA trust; native Chromium remote TLS is not verified here.',flush=True)
  browser.close()
finally:server.shutdown()
