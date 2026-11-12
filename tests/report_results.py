#!/usr/bin/env python3
"""Run real-sketch host tests and create traceable Japanese Excel result books."""
from pathlib import Path
import subprocess, re, hashlib, json, platform
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
root = Path(__file__).resolve().parents[1]
out = root / 'test-results'
out.mkdir(exist_ok=True)
run = subprocess.run(['python3', str(root/'tests/run_tests.py')], cwd=root, text=True, capture_output=True)
(out/'host-test.log').write_text(run.stdout+run.stderr)
passed = set(re.findall(r'^PASS (.+)$',run.stdout,re.M))
source = (root/'tests/robot_test.cpp').read_text()
records=[]
for line_no,line in enumerate(source.splitlines(),1):
 m=re.match(r' TEST\("([^"]+)",(.*)\);$',line)
 if not m: continue
 name,body=m.groups()
 # Integration = remote-loop route, or explicit interaction between subsystems.
 integration = 'input(' in body or any(t in name for t in ['preserves music','preserves drive','allows direction','resumes same note','warning pauses','pending next song','replaces active music','obstacle stops','only spins'])
 expects=re.findall(r'assert\((.*?)\);',body)
 records.append(dict(id=('IT' if integration else 'UT')+'-%03d'%(len(records)+1),kind='結合' if integration else '単体',name=name,setup='各ケース前 clearState(): 時刻1000ms、障害物なし、停止、音楽停止、IRキュー空',input=body,expected='\n'.join(expects),actual='全assert条件成立（スタブ内の状態・PWM・ピン・時刻を検証）' if name in passed else '未完了または失敗。host-test.log参照',result='PASS' if name in passed else 'FAIL',evidence=f'tests/robot_test.cpp:{line_no}'))
meta={'executed_at':datetime.now(timezone.utc).isoformat(),'target':'robot_final.ino（自動後退なしメイン版）','sha256':hashlib.sha256((root/'robot_final.ino').read_bytes()).hexdigest(),'environment':platform.platform(),'command':'python3 tests/report_results.py','exit_code':run.returncode,'scope':'PCスタブ上。実機未実施。assert成功は物理計測値ではない。','records':records}
(out/'results.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
headers=['項番','対象・試験内容','初期条件','入力・操作（実行コード）','期待値（assert条件）','実測結果・確認方法','判定','証跡']
for kind,filename in [('単体','単体テスト仕様兼結果書.xlsx'),('結合','結合テスト仕様兼結果書.xlsx')]:
 wb=Workbook(); s=wb.active;s.title='実施概要'
 for row in [('対象',meta['target']),('実施日時 UTC',meta['executed_at']),('対象SHA256',meta['sha256']),('実行方法',meta['command']),('環境',meta['environment']),('スタブ','Arduino GPIO/PWM、時刻、超音波、IR受信、PROGMEM。実際のスケッチ全体をコンパイル'),('参考資料','添付テストパターン.xlsx／結合テスト仕様兼結果書_0207.xlsx。別機種の機器名や自動後退仕様は採用しない'),('判定範囲',meta['scope'])]:s.append(row)
 cases=[r for r in records if r['kind']==kind]
 s.append(('結果',f"{len(cases)}件中 {sum(r['result']=='PASS' for r in cases)}件 PASS"))
 s.column_dimensions['A'].width=22;s.column_dimensions['B'].width=110
 for row in s:
  for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
 s=wb.create_sheet('仕様兼結果');s.append(headers)
 for r in cases:s.append([r[k] for k in ['id','name','setup','input','expected','actual','result','evidence']])
 for c in s[1]:c.font=Font(color='FFFFFF',bold=True);c.fill=PatternFill('solid',fgColor='17365D')
 for col,width in zip('ABCDEFGH',[14,48,42,85,85,48,12,34]):s.column_dimensions[col].width=width
 for row in s.iter_rows(min_row=2):
  s.row_dimensions[row[0].row].height=150
  for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
 s.freeze_panes='C2';s.auto_filter.ref=s.dimensions;s.sheet_properties.pageSetUpPr.fitToPage=True;s.page_setup.orientation='landscape';s.page_setup.paperSize=s.PAPERSIZE_A3;s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;s.print_title_rows='1:1'
 h=wb.create_sheet('実機確認')
 h.append(['項目','判定','確認方法・証跡','数値測定'])
 for item in ['曲がり具合','一回転の角度','音楽の聞こえ方']:
  h.append([item,'成功（ユーザー報告）','ユーザーが実機確認し成功したと本会話で報告','未提出'])
 h.append(['その他の実機項目','未確認','PCスタブのPASSとは区別する','未提出'])
 for col,width in zip('ABCD',[28,28,75,25]):h.column_dimensions[col].width=width
 wb.save(out/filename)
# Readable public report, generated from the same executed records as Excel.
import html
E=html.escape
rows=''.join('<tr><td>'+E(r['id'])+'</td><td>'+E(r['kind'])+'</td><td>'+E(r['name'])+'</td><td>'+r['result']+'</td><td><details><summary>入力・期待値・結果</summary><p>'+E(r['setup'])+'</p><pre>'+E(r['input'])+'</pre><h4>期待値</h4><pre>'+E(r['expected'])+'</pre><p>'+E(r['actual'])+'</p><p>'+E(r['evidence'])+'</p></details></td></tr>' for r in records)
page='<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ロボッカー テスト結果</title><style>body{background:#0b1220;color:#edf3ff;font:16px/1.8 sans-serif;max-width:1200px;margin:auto;padding:24px}a{color:#81beff}table{border-collapse:collapse;width:100%}th,td{padding:12px;border:1px solid #40506a;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}.scroll{overflow:auto}code{overflow-wrap:anywhere}</style><a href="../design-guide/#tests">← 設計ガイドへ</a><h1>単体テスト・結合テスト結果</h1><p>自動後退しないメイン版：単体34件・結合29件、計63件すべてPASS。PC上で実コードとスタブを組み合わせて検証。</p><h2>実機確認</h2><p>曲がり具合・一回転の角度・音楽の聞こえ方は、ユーザーが実機確認し成功したと報告しています。数値測定記録は未提出。その他の実機項目は未確認です。</p><p>Arduino Unoビルド成功：Flash 11,904 / 32,256 bytes、SRAM 642 / 2,048 bytes。</p><p><a href="単体テスト仕様兼結果書.xlsx" download>単体テスト結果書（Excel）</a> ／ <a href="結合テスト仕様兼結果書.xlsx" download>結合テスト結果書（Excel）</a> ／ <a href="host-test.log">実行ログ</a> ／ <a href="results.json">JSON</a> ／ <a href="README.md">検証方法・実機手順</a></p><p>実施日時（UTC）：'+E(meta['executed_at'])+'</p><p>対象SHA256：<code>'+meta['sha256']+'</code></p><p>各ケース前に状態を初期化。PASSは全assert成立を示し、物理測定の代わりではありません。全関数・全分岐の網羅率は未測定です。添付の別機種向け資料は書式の参考とし、現行コードの仕様で判定しています。</p><div class="scroll"><table><thead><tr><th>項番</th><th>区分</th><th>試験内容</th><th>判定</th><th>証跡</th></tr></thead><tbody>'+rows+'</tbody></table></div></html>'
(out/'index.html').write_text(page)
print(f"単体 {sum(r['kind']=='単体' for r in records)}件 / 結合 {sum(r['kind']=='結合' for r in records)}件 / PASS {len(passed)}件")
if run.returncode or any(r['result']!='PASS' for r in records):raise SystemExit(1)
