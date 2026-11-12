#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
import re, html, subprocess, tempfile, json
root=Path(__file__).resolve().parents[1]
class Check(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.links=[];self.stack=[];self.errors=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if 'id' in a:self.ids.append(a['id'])
  if t=='a':self.links.append(a.get('href',''))
  if t=='section':self.stack.append(a.get('id','section'))
 def handle_endtag(self,t):
  if t=='section':
   if self.stack:self.stack.pop()
   else:self.errors.append('unbalanced section')
code=(root/'robot_final.ino').read_text()
assert code==(root/'design-guide/robot_final.ino').read_text()
for path in [root/'index.html',root/'design-guide/index.html']:
 s=path.read_text();p=Check();p.feed(s)
 assert len(p.ids)==len(set(p.ids)), 'duplicate IDs'
 assert not p.errors and not p.stack, 'unbalanced sections'
 for link in p.links:
  if link.startswith('#'):assert link[1:] in p.ids,link
  elif link and not re.match(r'[a-z]+:',link):assert (path.parent/link.split('#')[0]).exists(),link
 assert html.unescape(re.search(r'<code id="codeText">(.*?)</code>',s,re.S)[1])==code
 assert len(re.findall(r'class="function-card"',s))==57
 assert len(re.findall(r'<pre class="mermaid">',s))==25
 assert '<b>57</b>' in s
 for bad in ['PWM200', 'PWM80', '9ステップ', '3450ms', '38項目', '56関数', '900msを超えない300ms', '6ステップ', '5750ms', '外側130', '内側75']:
  assert bad not in html.unescape(s),bad
 assert '時間制限なし' in s and '6190ms' in s and 'is_DiagonalComponent' in s
 for bad in ['全45関数','音楽再生時に停止','斜め移動は仕様に含めない','再生中に別の数字を押しても、曲は切り替わらない']:
  assert bad not in s,bad
 for script in re.findall(r'<script[^>]*>(.*?)</script>',s,re.S):
  with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as f:
   f.write(script);f.flush();subprocess.run(['node','--check',f.name],check=True,capture_output=True)
 print('PASS document parity, links, sections, 57 functions, 25 diagrams and JavaScript syntax:',path.relative_to(root))
subprocess.run(['python3',str(root/'scripts/update_guide.py')],check=True)
for path in ['index.html','design-guide/index.html']:
 # Running twice must not cause another diff.
 before=(root/path).read_bytes()
 subprocess.run(['python3',str(root/'scripts/update_guide.py')],check=True,capture_output=True)
 assert before==(root/path).read_bytes(),'generator not idempotent'
print('PASS repeatable generation')
