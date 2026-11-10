#!/usr/bin/env python3
"""Browser interaction and Mermaid rendering checks. Requires Playwright + Chromium."""
from pathlib import Path
import http.server, threading, functools, json, urllib.request
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=b.new_page(viewport={'width':1280,'height':900});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  url=f'http://127.0.0.1:{server.server_port}/design-guide/'
  # Fetch the exact pinned CDN bytes through the environment HTTP proxy.
  cdn='https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.min.js'
  with urllib.request.urlopen(cdn,timeout=30) as response: mermaid_bytes=response.read()
  page.route(cdn,lambda route: route.fulfill(body=mermaid_bytes,content_type='application/javascript'))
  page.goto(url,wait_until='networkidle')
  page.wait_for_function("document.querySelectorAll('.mermaid-diagram svg').length === 25",timeout=60000)
  assert page.locator('.function-card').count()==56
  page.locator('#function-search').fill('do_Warning_Tick')
  assert page.locator('#fn-do_Warning_Tick').is_visible()
  page.locator('#function-search').fill('存在しない関数XYZ')
  assert page.locator('#function-empty').is_visible()
  page.locator('#function-search').fill('')
  for anchor in ['overview','requirements','design','functions','figures','code']:
   page.locator(f'nav a[href="#{anchor}"]').click();assert page.locator('#'+anchor).count()==1
  page.locator('#openAll').click();assert page.locator('details:not([open])').count()==0
  page.locator('#closeAll').click();assert page.locator('details[open]').count()==0
  response=page.request.get(url+'robot_final.ino');assert response.text()==(root/'robot_final.ino').read_text()
  page.locator('#memo-text').fill('レビュー確認用メモ');page.locator('#memo-save').click();page.reload(wait_until='networkidle')
  assert page.locator('#memo-text').input_value()=='レビュー確認用メモ'
  page.locator('#memo-text').fill('');page.locator('#memo-save').click()
  page.set_viewport_size({'width':390,'height':844});page.goto(url,wait_until='networkidle')
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'mobile overflow'
  page.screenshot(path=str(root.parent/'mobile-review.png'),full_page=False)
  page.set_viewport_size({'width':1280,'height':900});page.goto(url+'#figures',wait_until='networkidle')
  page.wait_for_function("document.querySelectorAll('.mermaid-diagram svg').length === 25",timeout=60000)
  page.screenshot(path=str(root.parent/'figures-review.png'),full_page=False)
  assert not errors,errors
  print('PASS Chromium: 25 Mermaid diagrams, 56 functions, search, six anchors, open/close, downloads, memo persistence, mobile width, no page errors')
  b.close()
finally:server.shutdown()
