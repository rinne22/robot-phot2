#!/usr/bin/env python3
"""Synchronize both published pages, sketches, requirements and function exports."""
from pathlib import Path
import re, json, html, csv, io, base64
from function_excel import build_xlsx, form_html
ROOT=Path(__file__).resolve().parents[1]
esc=html.escape
from function_docs import DOCS, RETURNS
DESCRIPTIONS={name:description for name,(summary,description) in DOCS.items()}
SUMMARIES={name:summary for name,(summary,description) in DOCS.items()}

def table(headers, rows):
 return '<div class="tw"><table><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def detail(n,title,body):
 return f'<details><summary><span class="id">{n}</span><span>{title}</span></summary><div class="body dbody">{body}</div></details>'

def main():
 code=(ROOT/'robot_final.ino').read_text()
 page=(ROOT/'design-guide/index.html').read_text()
 funcs=[]
 for m in re.finditer(r'^((void|bool|int|unsigned int|DriveState) (\w+)\(([^\n]*)\))\s*\{',code,re.M):
  start=m.start();end=code.find('\n}',m.end())+2
  funcs.append(dict(sig=m[1],ret=m[2],name=m[3],args=m[4],body=code[m.end():end],line=code.count('\n',0,start)+1,lines=code.count('\n',start,end)+1))
 assert set(DESCRIPTIONS)=={f['name'] for f in funcs}
 count=len(funcs);names=set(DESCRIPTIONS)
 # Derive signatures, caller names and state references from the actual sketch.
 globals_part=code[:code.index('// ---------- 音階')]
 states=set(re.findall(r'^(?:int|bool|DriveState|uint8_t|unsigned long|const int16_t\*) (\w+)',globals_part,re.M))
 for f in funcs:
  body=re.sub(r'//[^\n]*','',f['body'])
  f['calls']=', '.join(dict.fromkeys(x for x in re.findall(r'\b(\w+)\s*\(',body) if x not in {'if','for','while','switch','sizeof','return'})) or '—'
  f['states']=', '.join(sorted(states & set(re.findall(r'\b\w+\b',body)))) or '—'
  f['summary']=SUMMARIES[f['name']]
  f['desc']=DESCRIPTIONS[f['name']]
  f['return_desc']='なし' if f['ret']=='void' else RETURNS[f['name']]
 csv_io=io.StringIO();w=csv.writer(csv_io,lineterminator="\n");w.writerow(['関数','形式','機能概要','処理内容','共有状態（参照・更新）','呼び出し','先頭行','行数'])
 for f in funcs:w.writerow([f['name'],f['sig'],f['summary'],f['desc'],f['states'],f['calls'],f['line'],f['lines']])
 (ROOT/'design-guide/functions.csv').write_text('\ufeff'+csv_io.getvalue())
 reqs=json.loads((ROOT/'scripts/requirements.json').read_text())
 page=re.sub(r'var reqs = \[.*?\n\];', 'var reqs = '+json.dumps(reqs,ensure_ascii=False,indent=2)+';',page,count=1,flags=re.S)
 # Current validation is deliberately separate from unverified historical claims.
 results=table(['確認','環境・結果'],[
 ['PC模擬試験','実コード全体をArduino/IR模擬環境でコンパイル。63項目成功。最新コードの試験はREVIEW.mdに記録。複数入力の境界、音楽との並行処理、回避、ダンス、警告波形を含む。'],
 ['Unoビルド','Arduino AVR Boards 1.8.8 / IRremote 4.4.1 / arduino:avr:uno で最新コードのビルド成功。Flash 11,904 / 32,256 bytes、SRAM 642 / 2,048 bytes。スケッチのビルドエラーなし。'],
 ['Web確認','図25枚の描画、関数検索、6つの移動先、コードとダウンロードの一致を自動チェックする。実施結果はREVIEW.mdに記録。'],
 ['実機試験','ユーザー実施：曲がり具合・一回転の角度・音楽の聞こえ方は成功との報告。その他の実機項目は未確認。'],
 ['旧版の85件/24件','対応する試験コードがリポジトリになく、最新版の成功証拠として使わない。改訂1.6は同梱の再現可能な試験を検証記録とする。']])
 design='<section class="design" id="design"><h2>開発設計書</h2><p class="cap">曲がり強調・一回転ダンス対応版／Arduino Uno・OSOYOO V2.1／正本：robot_final.ino</p>'
 design+=detail(1,'目的と設計方針','<p>リモコン走行・斜め走行・ダンス・音楽・障害物回避を実装する。入力・判断・出力の役割を分け、短い周期処理で状態を更新する。センサー測定と再確認待機はブロッキング処理として残っている。</p><p>1関数1目的、固定値の集約、重複処理の共通化を原則とする。20行以内・ネスト3段・引数3個は目安であり、現状の全関数が満たすという意味ではない。</p>')
 design+= '<p>操作仕様：ボタンを1つずつ押して離す。停止後の最初の方向は単独走行、単独走行中の上下＋左右は時間制限なく斜めに合成する。途中でOK・障害物回避・ダンスが入った場合は、その時点の走行状態から判断し直す。</p>'+table(['入力例（停止状態から）','状態の変化','右PWM / 左PWM'],[['↑の後に←／←の後に↑','GO_FORWARD_LEFT（前左）','前進220 / 前進60'],['↑の後に→／→の後に↑','GO_FORWARD_RIGHT（前右）','前進40 / 前進245'],['↓の後に←／←の後に↓','GO_BACK_LEFT（後左）','後退60 / 後退220'],['↓の後に→／→の後に↓','GO_BACK_RIGHT（後右）','後退245 / 後退40'],['前左走行中に↑をもう一度','GO_ADVANCE（直進へ復帰）','前進100 / 前進100'],['どの動作中でもOK','GO_STOP（走行・音・ダンス・回避を解除）','0 / 0']])
 design+=detail(2,'命名と関数規模',f'<p>定数は大文字、単語間は_。変数はlowerCamelCase。関数は動詞_対象、boolはisを原則とする。Arduino標準のsetup/loop、既存のDrive_Num・IS_IR・watch・warningとdance_Action/dance_Durationは例外として列挙する。既存のAdvance/Forwardは今回の動作修正では改名しない。</p><p>全{count}関数、スケッチ{len(code.splitlines())}行。最大は{max(funcs,key=lambda f:f["lines"])["name"]}の{max(f["lines"] for f in funcs)}行。行数は先頭行から閉じ括弧まで。関数別の形式と行数は下の関数設計書に掲載する。</p>')
 design+=detail(3,'ハードウェア構成',table(['部品','ピン','備考'],[['IR受信','D4','IRremote 4.x、D13受信LED無効'],['右モーター','PWM D9／方向D12・D11','PWM0〜255'],['左モーター','PWM D6／方向D7・D8','PWM0〜255'],['ブザー','D13','パッシブ。矩形波で音楽/警告、無音はHIGH。駆動回路に合う配線を確認'],['前方超音波','Trig D10／Echo D3','最大25ms/測定'],['後方赤外線','左D0／右D2','LOWで検知。書き込み時はD0配線を外す。Serialと共用しない']]))
 design+=detail(4,'状態と処理の順番','<p>loop() → do_IR_Tick → do_Dance_Tick → checkSensorsAndObstacles → do_Drive_Tick → do_Music_Tick → 100/20μs待機。checkSensorsAndObstacles内で、回避中はupdate_Avoidだけを実行し、ダンス中は通常の判定を省く。</p>'+table(['状態','用途'],[['Drive_Num / lastDriveCmd / lastDriveCmdMs','現在の走行・直前の単独入力・入力時刻'],['isAvoiding / avoidStartMs','回避状態と駆動開始直後の時刻'],['front / back / isCheckRequested / lastCheckMs','通常走行の障害物と測定要求/時刻'],['isDancing / danceStep / danceStepStartMs / lastDanceCheckMs','8ステップを繰り返すダンスと測定時刻'],['pendingSongNum / pendingSongMs','曲予約と300ms窓の開始'],['isMusicPlaying / isDanceMusic / currentNotePtr / noteStartMs / noteDurationMs','通常曲は1回、ダンス専用曲は先頭へ戻って繰り返す非ブロッキング再生'],['isWarningPlaying / warningStartMs / isWarningIssued / lastWarnMs','警告再生と再開始制限']])+ '<p>基本は入力が状態を更新し出力が駆動する。ただしOKのstop_Musicは即消音、start_Avoidは回避駆動と警告開始、end_Avoid/stop_Danceは直接停止する。前方検知時のcheckSensorsAndObstaclesもend_Avoidで直ちに停止し、直前入力を解除して警告する。これらを明示的な例外とする。</p>')
 design+=detail(5,'境界条件と優先順位','<p>OK停止が最優先。次に障害物判断、その後にユーザー走行。音楽は走行と独立し、音の出力は警告が優先する。回避中はOKのみ、ダンス中はOKと0のみを受け付ける。</p>'+table(['条件','動作'],[['逆方向入力の間隔 ≤ 300ms','直前の単独入力と逆方向なら停止'],['上下＋左右を順に押す','時間制限なし、順番を問わず斜め走行。例：↑、その後←'],['斜め走行中に方向ボタン','構成キーの再入力でその単独方向に戻る。その他の方向も単独指示とする'],['曲予約から < 300ms','別番号で取消、同番号は最初の時刻を維持'],['曲予約から ≥ 300ms後の数字入力','新規予約で置換し、新たに300ms待つ'],['通常の曲開始','予約から300ms以上、かつ警告中でない周期で開始/切替'],['前進系で前方検知','その場で停止・警告。前後同時も停止。自動後退なし'],['後退系の前進・右旋回回避から ≥ 500ms','停止。センサー測定後も時間を再確認。処理遅延による超過あり'],['警告','2kHz音50ms/無音50msを2回。開始から200ms以上で終了。前回開始から1000ms以上あける'],['ダンス','右650ms→停止180ms→左650ms→停止180ms→右一回転の目安2000ms→停止180ms→左一回転の目安2000ms→停止350msを繰り返す。1周6190msが設定値。右はDANCE_SPIN_MS、左はDANCE_LEFT_SPIN_MSを実機調整する。ダンス専用のオリジナル曲もループ再生し、OKか障害物検知で動きと曲を止める。通常PWM100、ダンスPWM180、左カーブ外側220／内側60・右カーブ外側245／内側40。実測は処理遅延分延びる']]))
 design+=detail(6,'検証記録（最新設定）',results+'<p><a href="https://github.com/rinne22/robot-phot2/blob/main/REVIEW.md">レビュー結果と再現手順</a></p><pre class="cmd">python3 tests/run_tests.py\npython3 tests/check_guide.py</pre>')
 design+=detail(7,'限界と実機で確認すること','<ul><li>超音波タイムアウトは999cm扱い。センサー故障と障害物なしを区別しない。</li><li>通常のその場旋回中は障害物判定をしない。側方センサーもなく、旋回の安全を保証しない。</li><li>センサー測定や30ms/20ms待機はIR応答と音の波形更新を遅らせる。停止出力300ms以内は目標であり実測値ではない。</li><li>停止は空転停止。車輪の静止時間・停止距離・20cm閾値の妥当性は未測定。</li><li>D13は起動時にブートローダーが駆動する場合がある。音程・音量・波形品質とI/O駆動能力を実機で確認する。</li></ul>')
 design+='</section>'
 start=page.index('<section class="design" id="design">');end=page.index('<section class="design" id="functions"',start)
 page=page[:start]+design+'\n'+page[end:]
 xlsx=build_xlsx(funcs)
 (ROOT/'design-guide/関数設計書.xlsx').write_bytes(xlsx)
 xlsx_b64=base64.b64encode(xlsx).decode()
 cards=f'<section class="design" id="functions" aria-labelledby="functions-title"><h2 id="functions-title">関数設計書</h2><p>曲がり強調・一回転ダンス対応版。実コードに対応する全{count}関数を掲載し、ダウンロード用Excelにも同じ内容を反映しています。</p><p><a class="fn-download" download="関数設計書.xlsx" href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{xlsx_b64}">関数設計書をダウンロード（Excel）</a></p><div class="fn-controls" hidden><label for="function-search">関数を検索</label><input id="function-search" type="search" placeholder="例：go_Stop、障害物、PWM" autocomplete="off"><span id="function-count" role="status">{count}件</span></div><p id="function-empty" hidden>該当する関数がありません。</p><p>斜め走行の処理：<a href="#fn-do_IR_Tick">入力受付</a> → <a href="#fn-set_Drive">走行状態の更新</a> → <a href="#fn-get_DiagonalDrive">上下と左右の組合せ</a> → <a href="#fn-do_Drive_Tick">モーター出力</a>。時間制限なしで順に押し、斜めからは方向ボタンで単独方向へ戻ります。OKと逆方向停止は優先して判定します。</p><div class="function-group"><h3>全関数（ソース順）</h3>'
 for f in funcs:
  cards+=f'<details class="function-card" id="fn-{f["name"]}"><summary><code>{f["name"]}()</code><span>{esc(f["summary"])}</span></summary><div class="body dbody">'+form_html(f)+'</div></details>'
 cards+='</div></section>'
 start=page.index('<section class="design" id="functions"');end=page.index('\n<script>',start)
 page=page[:start]+cards+page[end:]
 page=page.replace("count + '件 / 45件'",f"count + '件 / {count}件'")
 # Rebuild the figures wrapper so all 25 diagrams belong to the same valid section.
 start=page.index('<section class="figs" id="figures">');end=page.index('  <section class="env">',start)
 old=page[start:end];figs=re.findall(r'(<h4[^>]*>図(\d+).*?</h4>)<p class="cap">(.*?)</p><div class="diagram"><pre class="mermaid">(.*?)</pre></div>',old,re.S)
 assert len(figs)==25
 fixes={
 2:('前方障害物を検知したら、前進の出力より先に停止・警告します。自動後退しません。','''sequenceDiagram
 actor U as ユーザー
 participant IN as do_IR_Tick
 participant JD as checkSensorsAndObstacles
 participant SN as 前後センサー
 participant M as モーター
 participant B as ブザー
 U->>IN: ↑を押す
 IN->>IN: GO_ADVANCEを記録
 IN->>JD: 新しい指示の直後に判断
 JD->>SN: 前方と後方を確認
 SN-->>JD: 前方障害物あり
 JD->>JD: GO_STOP・直前入力を解除
 JD->>M: PWM0・方向LOWで停止
 JD->>B: warningで警告
 Note over JD,M: 前後同時でも前進系なら停止。自動後退なし。
 U->>IN: 次のリモコン入力
 Note over IN,M: 障害物が残る状態で再び↑なら再び停止'''),
 13:('回避は前進か右旋回だけです。500ms経過で停止し、前進回避の進行先に障害物がある場合も停止します。','''flowchart TD
 S([update_Avoid]) --> A{開始から500ms以上?}
 A -->|はい| X[end_Avoidで停止]
 A -->|いいえ| B{現在はGO_ADVANCE?}
 B -->|はい| F[前方障害物を確認]
 B -->|いいえ| Q[右旋回・センサー確認なし]
 F --> C{障害物あり又は測定後500ms以上?}
 Q --> C
 C -->|はい| X
 C -->|いいえ| Z([回避を継続して戻る])
 X --> Z'''),
 15:('前進系の前方検知は最優先で停止。手動後退中の後方検知だけ前進または右旋回で回避します。','''flowchart TD
 S([decide_AvoidAction]) --> A{前進系かつ前方検知?}
 A -->|はい| ST[GO_STOPを返す]
 A -->|いいえ| B{後退系かつ後方検知?}
 B -->|いいえ| N[DEFを返す]
 B -->|はい| C{前方も検知?}
 C -->|はい| R[GO_RIGHTを返す]
 C -->|いいえ| F[GO_ADVANCEを返す]'''),
 16:('自動回避で許す方向は前進と右旋回だけです。自動後退の要求は拒否して停止します。','''flowchart TD
 S([start_Avoid]) --> A{GO_ADVANCEまたはGO_RIGHT?}
 A -->|いいえ| E[end_Avoidで停止]
 A -->|はい| B[状態とモーターを更新]
 B --> C[回避フラグ・開始時刻を記録]
 C --> D[warningで警告]
 T([end_Avoid]) --> E
 E --> F[回避解除・GO_STOP・go_Stop]'''),
 4:('走行中の曲再生も、入力・出力は毎周loop()から呼びます。OKは入力処理で走行状態と音楽を解除します。','''sequenceDiagram
 actor U as ユーザー
 participant L as loop
 participant IN as do_IR_Tick
 participant MU as do_Music_Tick
 participant OUT as do_Drive_Tick
 participant B as ブザー
 U->>IN: 数字1〜9
 IN->>IN: 曲番号と予約時刻を記録
 Note over L,MU: 予約から300ms以上かつ警告終了後
 L->>OUT: 現在の走行状態を出力
 L->>MU: play_Musicで先頭音符を設定
 loop 毎周の更新
 L->>IN: 走行入力も受け付ける
 L->>OUT: 走行を継続・変更
 L->>MU: 音符と矩形波を1回更新
 MU->>B: HIGHまたはLOW
 end
 U->>IN: OK
 IN->>B: stop_Musicで消音
 IN->>IN: Drive_NumをGO_STOPにする
 L->>OUT: PWM0・方向LOWで停止'''),
 12:('回避中・ダンス中・通常走行を切り替え、同じ周回で通常判定と回避判定を重複実行しません。','''flowchart TD
 S([checkSensorsAndObstacles]) --> A{"回避中？"}
 A -->|はい| U["update_Avoid"] --> Z([終了])
 A -->|いいえ| B{"ダンス中？"}
 B -->|はい| Z
 B -->|いいえ| C{"is_CheckTime ?"}
 C -->|いいえ| Z
 C -->|はい| D["mark_Checked / update_ObstacleFlags"]
 D --> E["decide_AvoidAction"]
 E --> F{"GO_STOP？"}
 F -->|はい| ST["end_Avoid・直前入力解除・警告"] --> Z
 F -->|いいえ| H{"DEF以外？"}
 H -->|はい| G["start_Avoid"] --> Z
 H -->|いいえ| Z'''),
 23:('開始時刻から200msの警告を管理します。発音中は2kHzの矩形波を出し、50ms単位で音と無音を切り替えます。処理が遅れてもフェーズを余分に延ばしません。','''flowchart TD
 S([warning]) --> A{"警告中 または前回開始から1000ms未満？"}
 A -->|はい| Z([終了])
 A -->|いいえ| B["初回済フラグ・開始時刻・波形状態を設定"] --> Z
 T([do_Warning_Tick]) --> C{"警告中？"}
 C -->|いいえ| E([終了])
 C -->|はい| D{"開始から200ms以上？"}
 D -->|はい| F["警告終了 / HIGH / 音楽の時刻を補正"] --> E
 D -->|いいえ| G["フェーズ = 経過ms / 50"]
 G --> H{"奇数フェーズ？"}
 H -->|はい| I["HIGHで無音"] --> E
 H -->|いいえ| J{"前回切替から250μs以上？"}
 J -->|いいえ| E
 J -->|はい| K["LOWとHIGHを1回切替"] --> E''')}
 fig_html='<section class="figs" id="figures"><h2>設計図</h2><p class="cap">曲がり強調・一回転ダンス対応版／図1〜6：操作シーケンス、図7〜25：処理フロー。矢印は呼び出し、状態の受け渡し、実行順を示します。</p>'
 for heading,num,cap,src in figs:
  n=int(num);src=html.unescape(src)
  if n in fixes:cap,src=fixes[n]
  src=src.replace('回避開始時刻を記録し、曲予約を解除','回避開始時刻を記録。曲予約と再生状態は保持')
  if n==2:src=src.replace('IN->>M: go_Stop 完全停止 最優先','IN->>IN: GO_STOPに更新・音楽と警告を消音\n    OUT->>M: 同じ周回の出力で停止')
  if n==5:
   heading='<h4>図5　斜め走行への切替・単独方向への復帰・逆方向停止</h4>'
   cap='↑の後に←で前左へ。間隔に制限はありません。↑をもう一度押すと直進に戻り、OKで停止します。逆方向が300ms以内なら合成より先に停止します。'
   src="""sequenceDiagram
 actor U as ユーザー
 participant IN as do_IR_Tick
 participant SD as set_Drive
 participant OUT as do_Drive_Tick
 U->>IN: ↑を押して離す
 IN->>SD: GO_ADVANCE
 SD->>SD: 停止状態から前進へ
 OUT->>OUT: 左右PWM100で前進
 Note over U,SD: 次のボタンまでの時間制限なし
 U->>IN: ←を押して離す
 IN->>SD: GO_LEFT
 SD->>SD: 現在の前進と左を合成してGO_FORWARD_LEFT
 OUT->>OUT: 右PWM220・左PWM60で前左へ
 U->>IN: ↑をもう一度押す
 IN->>SD: GO_ADVANCE
 SD->>SD: 斜めから単独の前進へ
 U->>IN: OK
 IN->>IN: 曲と警告を消音・GO_STOP
 OUT->>OUT: 左右PWM0で停止
 Note over U,SD: 逆方向の入力は直前の単独入力と300ms以内なら停止
"""
  if n==6:cap='予約から300ms未満に別の数字が届くと予約を取り消します。300ms以上なら最新入力を新規予約として扱います。';src=src.replace('0.3秒以内','300ms未満')
  if n==13:src=src.replace('|後退|','|後退系|').replace('|前進|','|前進系|')
  if n==20:
   cap='300ms未満の予約だけを競合判定に使います。期限以降の数字は新規予約です。'
   src=src.replace('依頼中の曲と別の数字?','300ms未満の予約で別の数字?').replace('同じ数字を依頼中?','300ms未満の予約で同じ数字?')
  if n==11:
   cap='速押し不要。現在の単独走行と直交する方向で斜め走行、斜めからは方向ボタンで単独方向へ戻る。300ms以内の逆方向は停止。'
   src='''flowchart TD
 S([set_Drive]) --> A{直前入力と300ms以内で逆方向?}
 A -->|はい| STOP[GO_STOPに更新] --> Z([終了])
 A -->|いいえ| B[現在の走行と新入力を組み合わせる]
 B --> C{上下と左右の組合せ?}
 C -->|はい| D[斜め走行にする]
 C -->|いいえ| E[新しい単独方向にする]
 D --> F[入力と時刻を更新・センサー確認要求]
 E --> F
 F --> Z'''
  if n==21:
   cap='警告を優先して音符を更新します。ダンス専用曲は終端で先頭へ戻り、通常曲だけ終了します。'
   src="""flowchart TD
 S([do_Music_Tick]) --> W[do_Warning_Tick]
 W --> A{警告中?}
 A -->|はい| Z([終了])
 A -->|いいえ| B{曲予約の期限到達?}
 B -->|はい| C[通常曲を開始・切替]
 B -->|いいえ| D{曲を再生中?}
 C --> D
 D -->|いいえ| Z
 D -->|はい| E{音符の全長経過?}
 E -->|はい| F[次の音符へ]
 F --> G{END_MARK?}
 G -->|はい| H{ダンス専用曲かつダンス中?}
 H -->|はい| I[DANCE_SONGの先頭へ]
 H -->|いいえ| J[再生終了・消音・次曲予約は保持] --> Z
 I --> K[play_Note]
 G -->|いいえ| K
 K --> L[発音時間・半周期に従い波形を更新]
 E -->|いいえ| L
 L --> Z
"""
  if n==25:
   src="""flowchart TD
 S([0ボタン]) --> A{回避中?}
 A -->|はい| Z([終了])
 A -->|いいえ| B[ステップ0・専用曲の先頭から再開]
 B --> C[最初のモーター出力前に前後を確認]
 T([do_Dance_Tick]) --> C
 C --> D{障害物あり?}
 D -->|はい| STOP[ダンスと専用曲を停止] --> Z
 D -->|いいえ| E{ステップ時間経過?}
 E -->|いいえ| Z
 E -->|はい| F[次のステップへ・8で0へ戻る]
 F --> G[右・停止・左・停止・右一回転・停止・左一回転・停止]
 G --> Z
 M([do_Music_Tick]) --> N[専用曲の終端で先頭へ戻る]
 N --> Z
 O([OK]) --> STOP
"""
  if n==25:cap='右→停止→左→停止→右一回転→停止→左一回転→停止の8ステップを繰り返します。1周の初期設定時間は6190ms。右DANCE_SPIN_MS=2000・左DANCE_LEFT_SPIN_MS=2000は実機調整が必要です。専用曲もループし、OKか障害物で動きと曲を停止します。開始直後は最初の出力前に前後を確認し、障害物またはOKで停止、0で先頭から再開します。'
  fig_html+=heading+'<p class="cap">'+cap+'</p><div class="diagram"><pre class="mermaid">'+esc(src)+'</pre></div>'
 fig_html+='</section>\n'
 page=page[:start]+fig_html+page[end:]
 page=re.sub(r'(<code id="codeText">).*?(</code>)',lambda m:m[1]+esc(code)+m[2],page,count=1,flags=re.S)
 page=re.sub(r'<style id="function-form-style">.*?</style>', '', page, flags=re.S)
 page=page.replace('</head>', '<style id="function-form-style">.function-form{min-width:640px;table-layout:fixed}.function-form th{background:#ddd;color:#18262b;vertical-align:middle;text-align:center}.function-form td{white-space:pre-wrap;overflow-wrap:anywhere}.function-form td,.function-form th{border:1px solid #8a949a;padding:10px}.function-form tr:first-child td{font-weight:700}</style>'+'</head>')
 page=page.replace('使用言語：C言語（Arduino言語）','使用言語：C++（Arduinoスケッチ）')
 page=page.replace('IRremote</code>（4.x系）','IRremote</code>（検証版4.4.1／4.x系）')
 page=re.sub(r'<b>\d+</b> PC模擬試験項目','<b>63</b> PC模擬試験項目',page)
 page=re.sub(r'<b>\d+</b> 関数の設計',f'<b>{count}</b> 関数の設計',page)
 page=page.replace('<b>45</b> 関数の設計',f'<b>{count}</b> 関数の設計').replace('<b>24</b> 結合テスト項目','<b>63</b> PC模擬試験項目')
 page=page.replace('結合テストはPC上の疑似環境で実施。実機確認項目は開発設計に記載しています。','最新設定の検証結果は開発設計とREVIEW.mdを参照。曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。')
 rev=f'<section class="overview" id="revision"><h2>メイン版：自動後退なし</h2><p>前進・前左・前右で前方の障害物を検知すると停止して警告します。前後同時に検知しても前進系では停止します。障害物を理由に自動後退する機能は廃止しました。リモコンの↓による手動後退は利用できます。</p><p>前左220/60・前右40/245、後退も対応する強さ。ダンスは右・左・右一回転・左一回転と専用曲をループします。</p><p><a id="main-code-download" class="fn-download" href="robot_final.ino" download="robot_final.ino">メインコードをダウンロード</a> ／ <a href="https://github.com/rinne22/robot-phot2/blob/main/REVIEW.md">検証記録</a></p><p>全{count}関数・図25枚・要件・掲載コード・ダウンロード・Excelを同じメイン仕様に統一しています。曲がり具合・一回転の角度・音楽の聞こえ方は、ユーザーによる実機確認で成功しています。</p></section>'
 page=re.sub(r'<section class="overview" id="revision">.*?</section>',lambda m:rev,page,count=1,flags=re.S)
 page=page.replace('Arduino Unoでの今回の改訂版のビルド・曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。PWMや障害物検出の応答は実機で確認してください。旧版1.6の検証記録は今回の変更の確認結果ではありません。','最新設定のビルド結果はREVIEW.mdを参照。曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。')
 page=re.sub(r'改訂1\.6はPC模擬試験\d+項目とUnoビルドを確認。曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。','最新設定のPC模擬試験63項目とUnoビルドを確認。曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。',page)
 page=re.sub(r'<section[^>]*id="dance-speed-update".*?</section>', '<section class="overview" id="dance-speed-update"><h2>かんたん斜め走行</h2><p>前左は外側PWM220・内側PWM60を維持し、前右は外側PWM245・内側PWM40へ強化しました。後退も左右それぞれ同じ強さに対応します。ボタンは1つずつ押して離してください。速押し・同時押しは不要です。</p><ul><li>「↑」の後に「←」：前進しながら左へ（逆の順番でも可）</li><li>「↑」の後に「→」：前進しながら右へ（逆の順番でも可）</li><li>「↓」の後に「←」：後退しながら左へ（逆の順番でも可）</li><li>「↓」の後に「→」：後退しながら右へ（逆の順番でも可）</li></ul><p>斜め走行中に構成する方向をもう一度押すとその単独方向へ戻り、OKで停止します。上下・左右の反対入力が300ms以内なら停止します。通常PWM100、ダンスPWM180、左カーブ外側220／内側60・右カーブ外側245／内側40。</p><p>実機に新しいスケッチを書き込んでから操作してください。旧スケッチでは操作は変わりません。ダンスは右→左→右に一回転→左に一回転を狙う旋回と、専用の軽快なオリジナル曲をループします。DANCE_SPIN_MS=2000とDANCE_LEFT_SPIN_MS=2000は目安です。回転が足りなければ長く、回り過ぎなら短く調整してください。</p></section>',page,count=1,flags=re.S)
 page=page.replace('最新設定のPC模擬試験47項目','最新設定のPC模擬試験63項目')
 page=re.sub(r'<section[^>]*id="requirements".*?</section>', '<section class="top" id="requirements"><h2>要件定義</h2><p class="cap">曲がり強調・一回転ダンス対応版。操作例は要求1-13、確認項目は要求7-1に掲載しています。</p><h3>要求1　リモコンで走行を制御する</h3><p><span class="tag">内容</span>矢印を1つずつ順に押して、前進・後退・旋回・斜め走行を指示する。上下と左右の組合せに時間制限は設けず、OKを最優先の停止とする。</p><p><span class="tag">理由</span>速押しや同時押しに頼らず、リモコンから目的の走行を選べるようにするため。</p></section>',page,count=1,flags=re.S)
 overview='<section class="overview" id="overview" aria-labelledby="overview-title"><h2 id="overview-title">ロボットの主な動作</h2><p class="cap">曲がり強調・一回転ダンス対応版。概要・要件定義・開発設計・関数設計・設計図を同じ操作仕様で統一しています。</p><div class="tiles"><article><h3>01　順に押して斜め走行</h3><p>矢印は1つずつ押して離します。上下と左右を順に押すだけで斜め走行。速押し・同時押しは不要で、入力間隔の時間制限もありません。</p></article><article><h3>02　障害物回避と停止</h3><p>前進・後退と斜め走行では前後を確認します。前進系で前方検知なら停止し、手動後退中の後方検知には前進回避を優先します。OKは走行・音楽・ダンス・回避をまとめて停止します。</p></article><article><h3>03　音楽とダンス</h3><p>1〜9で走行しながら曲を再生。0で右・左・右一回転・左一回転を狙う8ステップと専用曲をループします。ダンス中も前後を確認し、障害物で中止します。</p></article></div>'+table(['1つ目のボタン','2つ目のボタン','動作'],[['↑','←','前進しながら左へ'],['↑','→','前進しながら右へ'],['↓','←','後退しながら左へ'],['↓','→','後退しながら右へ']])+'<p>上下と左右は逆の順番でも同じです。斜め走行中に方向ボタンを押し直すと、その単独方向へ戻ります。例：↑、←で前左、↑をもう一度押すと直進。直前の単独入力と反対の方向が300ms以内に届くと停止します。</p><p>通常PWM100／ダンスPWM180／左カーブ外側220・内側60／右カーブ外側245・内側40。新しい操作を使うには<a href="robot_final.ino" download>最新コード</a>をArduinoに書き込んでください。</p><p class="cap">PC模擬試験63項目・Unoビルド成功。曲がり具合・一回転の角度・音楽の聞こえ方はユーザーによる実機確認済みです。その他の実機項目は未確認です。</p><p><a href="https://osoyoo.com/2020/05/12/v2-1-robot-car-kit-for-arduino-tutorial-introduction/">OSOYOO公式組み立てガイド ↗</a></p></section>'
 page=re.sub(r'<section[^>]*id="overview".*?</section>',lambda m:overview,page,count=1,flags=re.S)
 # Prominent variant download in Overview and a full preview in Code.
 # Remove the obsolete variant comparison and second sketch preview.
 page=re.sub(r'<div id="code-options">.*?(?:</details></div>|</p></div>)', '',page,count=1,flags=re.S)
 choices='<div id="code-options"><h2>メインのArduinoコード</h2><p>配布するコードは自動後退なしのメイン版に統一しました。前方障害物では停止・警告し、手動後退と後方障害物時の従来回避は利用できます。</p><p><a id="canonical-code-download" class="fn-download" href="robot_final.ino" download="robot_final.ino">robot_final.ino をダウンロード</a></p><p>Arduino IDEでは robot_final フォルダ内に robot_final.ino として保存し、書き込んでください。以前の自動後退版は使わず、このコードへ置き換えてください。</p><p>掲載全文・設計書・関数表・Excelもこのメインコードが対象です。</p></div>'
 page=page.replace('<section class="code-sec" id="code">','<section class="code-sec" id="code">'+choices,1)
 if 'id="transfer-nav-link"' not in page:
  page=page.replace('</nav>','<a id="transfer-nav-link" href="../file-transfer/">ファイル受け渡し</a></nav>',1)
 # Publish test downloads from a stable section on both entry pages.
 page=re.sub(r'<section class="design" id="tests">.*?</section>', '',page,flags=re.S)
 test_section='<section class="design" id="tests"><h2>単体テスト・結合テスト結果</h2><p>現行の自動後退しないメイン版を検証。PCスタブ上の単体34件・結合29件、計63件すべて合格。Arduino Uno向けビルドも成功しています。</p><p>実機確認：曲がり具合・一回転の角度・音楽の聞こえ方は、ユーザーから成功の報告を受けています。角度などの数値測定記録は未提出で、その他の実機項目は未確認です。</p><p><a class="fn-download" href="../test-results/単体テスト仕様兼結果書.xlsx" download>単体テスト結果書（Excel・34件）</a> <a class="fn-download" href="../test-results/結合テスト仕様兼結果書.xlsx" download>結合テスト結果書（Excel・29件）</a></p><p><a href="../test-results/">全テストの仕様・結果を閲覧</a> ／ <a href="../test-results/host-test.log" download>実行ログ</a> ／ <a href="../test-results/results.json" download>結果データ（JSON）</a></p><p>Excelには初期条件・入力・期待値・実行結果・試験コードの行番号を記録。添付の別機種向け資料を参考に、現行コードを直接コンパイルして検証しています。</p></section>'
 page=page.replace('<section class="design" id="functions"',test_section+'<section class="design" id="functions"',1)
 if 'id="tests-nav-link"' not in page:
  page=page.replace('</nav>','<a id="tests-nav-link" href="#tests">テスト結果</a></nav>',1)
 for path in ['design-guide/index.html','index.html']:
  out=page if path.startswith('design-guide/') else page.replace('href="functions.csv"','href="design-guide/functions.csv"').replace('href="../file-transfer/"','href="file-transfer/"')
  if not path.startswith('design-guide/'): out=out.replace('href="../test-results/','href="test-results/')
  (ROOT/path).write_text(out)
 (ROOT/'design-guide/robot_final.ino').write_text(code)
 (ROOT/'design-guide/robot_front_stop.ino').write_text(code)  # 旧リンクも同一のメインコードを配布
 print(f'Synchronized {count} functions, {len(figs)} diagrams and {len(reqs)} requirements')
if __name__=='__main__':main()
