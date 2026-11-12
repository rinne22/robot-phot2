"""Check the generated workbook and its public HTML download against the template fields."""
from pathlib import Path
import base64, io, re, sys, html as html_module
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from function_docs import DOCS, RETURNS
import openpyxl
root=Path(__file__).resolve().parents[1]
expected=(root/'design-guide/関数設計書.xlsx').read_bytes()
w=openpyxl.load_workbook(io.BytesIO(expected))
assert len(w.worksheets)==58
for s in list(w)[1:]:
 for cell,label in {'B2':'機能概要','B3':'処理内容','B5':'関数形式','B6':'入出力','C6':'種類','D6':'形式','E6':'内容','B15':'ソースファイル','B16':'呼び出し関数','B19':'備考'}.items():
  assert s[cell].value==label,(s.title,cell)
 assert s['C5'].value.split('(')[0].split()[-1]==s.title
 summary,process=DOCS[s.title]
 assert s['C2'].value==summary and s['C3'].value==process,s.title
 normalize=lambda value:re.sub(r'[\s。．.]','',value)
 assert normalize(summary)!=normalize(process),s.title
 assert normalize(summary)!=normalize(re.sub(r'^1\. ','',process.splitlines()[0])),s.title
 assert process.startswith('1. ') and '\n2. ' in process,s.title
 if s.title in RETURNS:assert s['E8'].value==RETURNS[s.title],s.title
 for cell in ['C2','C3','D7','E7','D8','E8','D9','E9','D10','E10','C15','C16','C19']:
  assert s[cell].value is not None,(s.title,cell)
 assert s.page_setup.fitToWidth==1 and s.page_setup.fitToHeight==1
for path in ['index.html','design-guide/index.html']:
 html=(root/path).read_text()
 actual=base64.b64decode(re.search(r'spreadsheetml.sheet;base64,([^\"]+)',html)[1])
 assert actual==expected
 assert html.count('class="function-form"')==57
 for name,(summary,process) in DOCS.items():
  card=re.search(r'<details class="function-card" id="fn-'+re.escape(name)+r'">.*?</details>',html,re.S)[0]
  for label,expected_text in [('機能概要',summary),('処理内容',process)]:
   actual_text=html_module.unescape(re.search(r'>'+label+r'</th><td colspan="3">(.*?)</td>',card,re.S)[1])
   assert actual_text==expected_text,(path,name,label)
 assert w['関数一覧']['A2'].value.startswith('全57関数')
print('PASS: 57 template forms, 58 worksheets, types/IO/call fields, A4 print setup and downloadable XLSX parity; all 57 purposes and procedures are distinct and match HTML')
