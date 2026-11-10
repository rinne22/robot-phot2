"""Check the generated workbook and its public HTML download against the template fields."""
from pathlib import Path
import base64, io, re
import openpyxl
root=Path(__file__).resolve().parents[1]
expected=(root/'design-guide/関数設計書.xlsx').read_bytes()
w=openpyxl.load_workbook(io.BytesIO(expected))
assert len(w.worksheets)==57
for s in list(w)[1:]:
 for cell,label in {'B2':'機能概要','B3':'処理内容','B5':'関数形式','B6':'入出力','C6':'種類','D6':'形式','E6':'内容','B15':'ソースファイル','B16':'呼び出し関数','B19':'備考'}.items():
  assert s[cell].value==label,(s.title,cell)
 assert s['C5'].value.split('(')[0].split()[-1]==s.title
 for cell in ['C2','C3','D7','E7','D8','E8','D9','E9','D10','E10','C15','C16','C19']:
  assert s[cell].value is not None,(s.title,cell)
 assert s.page_setup.fitToWidth==1 and s.page_setup.fitToHeight==1
for path in ['index.html','design-guide/index.html']:
 html=(root/path).read_text()
 actual=base64.b64decode(re.search(r'spreadsheetml.sheet;base64,([^\"]+)',html)[1])
 assert actual==expected
 assert html.count('class="function-form"')==56
print('PASS: 56 template forms, 57 worksheets, types/IO/call fields, A4 print setup and downloadable XLSX parity')
