#!/usr/bin/env python3
"""Synchronize both published pages, sketches, requirements and function exports."""
from pathlib import Path
import re, json, html, csv, io, base64
from function_excel import build_xlsx, form_html
ROOT=Path(__file__).resolve().parents[1]
esc=html.escape
DESCRIPTIONS={
'set_RightMotor':'右モーターの方向端子D12/D11へ引数を出力する。',
'set_LeftMotor':'左モーターの方向端子D7/D8へ引数を出力する。',
'set_MotorSpeed':'右D9・左D6にPWMを出力する。引数は0〜255を前提とする。',
'go_Advance':'左右を前進方向、PWMを100/100にする。',
'go_Back':'左右を後退方向、PWMを100/100にする。',
'go_Left':'右前進・左後退、通常PWM100/100、ダンス中PWM180/180でその場左旋回する。',
'go_Right':'右後退・左前進、通常PWM100/100、ダンス中PWM180/180でその場右旋回する。',
'go_ForwardLeft':'左右とも前進、右PWM130・左75で前左へカーブする。',
'go_ForwardRight':'左右とも前進、右PWM75・左130で前右へカーブする。',
'go_BackLeft':'左右とも後退、右PWM75・左130で後左へカーブする。',
'go_BackRight':'左右とも後退、右PWM130・左75で後右へカーブする。',
'go_Stop':'左右PWMを0、方向4端子をLOWにする。空転停止のため車輪の即時静止は保証しない。',
'do_Drive_Tick':'走行状態に対応する出力関数を呼ぶ。不正な状態はGO_STOPに修正して停止する。',
'warning':'警告の開始を記録する。再生中または前回開始から1000ms未満なら何もしない。時刻0での初回も許可する。',
'do_Warning_Tick':'警告開始からの時間で4フェーズを判定する。偶数フェーズは2kHz矩形波、奇数は無音。200ms以上で終了し音楽の音符時刻を補正する。待機ループは使わない。',
'play_Tone':'周波数から半周期を計算し、発音時間と波形状態を設定する。freqが0以下は休符、msが0以下は発音時間0。実際の波形はdo_Music_Tickが更新する。',
'get_SongNote':'PROGMEM上の音符ペアの先頭を読み、周波数HzまたはEND_MARKを返す。有効なポインタを前提とする。',
'get_SongLength':'PROGMEM上の音符ペアの2要素目を読み、長さ係数を返す。有効なポインタを前提とする。',
'play_Note':'音符の全長を係数×TEMPO_MSで設定し、末尾20msを無音とした発音を予約する。待機せず戻る。',
'stop_Music':'曲再生・曲予約・警告音を取り消し、ポインタと半周期を解除してブザーをHIGHにする。走行状態は変更しない。',
'play_Music':'1〜9の曲番号から先頭ポインタをpgm_read_ptrで読み、再生状態と最初の音符を設定する。範囲外は無視し、走行を止めない。',
'is_MusicDue':'曲予約が存在し、予約から300ms以上経過したかを返す。',
'do_Music_Tick':'警告を更新し、警告中は音楽の更新を中断する。それ以外は曲予約、音符終了、終端、無音、半周期の順に判定し、波形を最大1回切り替える。',
'watch':'D10へ10μsパルスを送りD3のEchoを最大25ms待つ。幅÷58の整数cmを返す。タイムアウトは999で、故障と遠方を区別しない。',
'is_FrontBlocked':'20cm以下なら30ms待ち再測定し、2回とも20cm以下ならtrueを返す。センサー待機中は他の周期処理を進めない。',
'is_BackIrOn':'後方D0/D2のどちらかがLOWならtrueを返す。',
'is_BackBlocked':'後方検知後20ms待ち、再検知したらtrueを返す。',
'start_Avoid':'回避状態に上書きしてモーターを出力し、その直後から500msを計測する。警告を開始する。音楽の再生状態と曲予約は保持する。',
'end_Avoid':'回避フラグを下げ、GO_STOPにしてモーターを停止する。',
'update_Avoid':'回避中に1回だけ終了判定する。測定前後の500ms経過、または逃げる方向の障害物で停止する。旋回回避は時間だけで終了する。',
'is_CheckTime':'前進系・後退系（斜めを含む）で、新規確認要求または前回から100ms以上のときtrueを返す。',
'mark_Checked':'確認要求を解除し、測定開始側の時刻を記録する。',
'update_ObstacleFlags':'前方・後方を順番に測り、front/backを1または0に更新する。',
'decide_AvoidAction':'前後両方ならGO_RIGHT、前進系で前方のみならGO_BACK、後退系で後方のみならGO_ADVANCE、それ以外はDEFを返す。通常走行判定から呼ぶ。',
'checkSensorsAndObstacles':'回避中はupdate_Avoidだけを呼んで戻る。ダンス中は戻る。通常時は測定要否を確認し、測定・回避判断・必要時の回避開始を行う。',
'stop_Dance':'ダンスを解除しGO_STOPにしてモーターを停止する。曲再生は変更しない。',
'dance_Action':'ステップ0〜6で左右のその場旋回または停止、7と範囲外はGO_STOPを返す。',
'dance_Duration':'各ステップの設定時間msを返す。0/1は900、2/3は450、4は300、5/6は1200、7と範囲外は350。',
'start_Dance':'回避中なら無視。それ以外は先頭ステップへ戻し、次周期の初回センサー確認を要求する。曲予約だけを解除し、モーター出力は安全確認後まで行わない。',
'do_Dance_Tick':'ダンス中は初回または100ms経過時に前後を確認し、検知時は中止する。ステップ時間の経過で次に進み、8ステップ終了で先頭へ戻り繰り返す。',
'is_OppositeDrive':'上下・左右の逆向きの組合せを、順序を問わずtrueとする。斜め状態は引数に渡さず単独指示どうしを比較する。',
'get_DiagonalDrive':'上下と左右の組合せを順序に関係なく前左・前右・後左・後右へ変換し、該当なしはDEFを返す。',
'is_DiagonalComponent':'斜め走行に含まれる上下または左右の単独方向ならtrue、それ以外はfalseを返す。',
'set_Drive':'直前の単独入力と300ms以内で逆向きなら停止。900ms以内の上下＋左右は斜めにし、斜めの構成キー再受信では走行状態を保持する。入力と時刻を記録しセンサー確認を要求する。',
'read_IR_Command':'IR受信がなければNO_COMMAND。受信時はコードとリピートフラグを取得しresumeする。リピートはNO_COMMAND、それ以外はcommandを返す。',
'handle_StopButton':'回避・ダンスを解除し、stop_Musicで曲と警告を消音する。現在と直前の走行状態をGO_STOPにする。モーターは同じ周回の出力で止める。',
'handle_DriveButton':'24/82/8/90を前進/後退/左/右の単独指示に変換しset_Driveへ渡す。他のコードは何もしない。',
'get_SongNum':'NUM_CODESの受信コードに対応する曲番号1〜9を返す。該当なしは0。',
'is_NumberConflict':'300ms未満の予約があり、別の曲番号ならtrueを返す。300ms以上経過した予約は競合扱いにしない。',
'handle_NumberButton':'数字以外は無視。300ms未満の別番号なら予約取消、同番号なら予約時刻を維持する。それ以外は最新入力を新規予約として時刻を更新する。',
'do_IR_Tick':'1件の受信を処理する。OKを最優先し、回避中は他を無視。0でダンス開始/再開、ダンス中は残りを無視。通常時は方向と数字を処理する。',
'init_MotorPins':'モーター6端子を出力にしてgo_Stopを呼ぶ。',
'init_BuzzerPin':'D13にHIGHを用意してから出力に切り替え、初期化時の意図しないLOWを避ける。ブートローダー期間は制御対象外。',
'init_SensorPins':'Trigを出力、Echoと後方赤外線端子を入力にする。',
'init_IrReceiver':'D4でIR受信を開始し、ブザーと共有するD13の受信LED点滅を無効化する。',
'setup':'モーター、ブザー、センサー、IR受信の順に初期化する。',
'loop':'IR入力→ダンス→障害物判断→走行出力→音楽/警告出力→100μsまたは20μs待機を繰り返す。'}

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
  f['calls']=', '.join(dict.fromkeys(x for x in re.findall(r'\b(\w+)\s*\(',body) if x not in {'if','for','while','switch','sizeof'})) or '—'
  f['states']=', '.join(sorted(states & set(re.findall(r'\b\w+\b',body)))) or '—'
  f['desc']=DESCRIPTIONS[f['name']]
 csv_io=io.StringIO();w=csv.writer(csv_io,lineterminator="\n");w.writerow(['関数','形式','処理内容','共有状態（参照・更新）','呼び出し','先頭行','行数'])
 for f in funcs:w.writerow([f['name'],f['sig'],f['desc'],f['states'],f['calls'],f['line'],f['lines']])
 (ROOT/'design-guide/functions.csv').write_text('\ufeff'+csv_io.getvalue())
 reqs=json.loads((ROOT/'scripts/requirements.json').read_text())
 page=re.sub(r'var reqs = \[.*?\n\];', 'var reqs = '+json.dumps(reqs,ensure_ascii=False,indent=2)+';',page,count=1,flags=re.S)
 # Current validation is deliberately separate from unverified historical claims.
 results=table(['確認','環境・結果'],[
 ['PC模擬試験','実コード全体をArduino/IR模擬環境でコンパイル。47項目成功。最新コードの試験はREVIEW.mdに記録。複数入力の境界、音楽との並行処理、回避、ダンス、警告波形を含む。'],
 ['Unoビルド','Arduino AVR Boards 1.8.8 / IRremote 4.4.1 / arduino:avr:uno で最新コードのビルド成功。Flash 11,728 / 32,256 bytes、SRAM 641 / 2,048 bytes。Arduinoコア由来の未使用引数警告あり。'],
 ['Web確認','図25枚の描画、関数検索、6つの移動先、コードとダウンロードの一致を自動チェックする。実施結果はREVIEW.mdに記録。'],
 ['実機試験','未実施。モーターの向き、音質、センサー感度、OKの応答、停止距離、タイマー動作を実機で確認する。'],
 ['旧版の85件/24件','対応する試験コードがリポジトリになく、最新版の成功証拠として使わない。改訂1.6は同梱の再現可能な試験を検証記録とする。']])
 design='<section class="design" id="design"><h2>開発設計書</h2><p class="cap">最新設定統一版／2026年11月11日／Arduino Uno・OSOYOO V2.1／正本：robot_final.ino</p>'
 design+=detail(1,'目的と設計方針','<p>リモコン走行・斜め走行・ダンス・音楽・障害物回避を実装する。入力・判断・出力の役割を分け、短い周期処理で状態を更新する。センサー測定と再確認待機はブロッキング処理として残っている。</p><p>1関数1目的、固定値の集約、重複処理の共通化を原則とする。20行以内・ネスト3段・引数3個は目安であり、現状の全関数が満たすという意味ではない。</p>')
 design+=detail(2,'命名と関数規模',f'<p>定数は大文字、単語間は_。変数はlowerCamelCase。関数は動詞_対象、boolはisを原則とする。Arduino標準のsetup/loop、既存のDrive_Num・IS_IR・watch・warningとdance_Action/dance_Durationは例外として列挙する。既存のAdvance/Forwardは今回の動作修正では改名しない。</p><p>全{count}関数、スケッチ{len(code.splitlines())}行。最大は{max(funcs,key=lambda f:f["lines"])["name"]}の{max(f["lines"] for f in funcs)}行。行数は先頭行から閉じ括弧まで。関数別の形式と行数は下の関数設計書に掲載する。</p>')
 design+=detail(3,'ハードウェア構成',table(['部品','ピン','備考'],[['IR受信','D4','IRremote 4.x、D13受信LED無効'],['右モーター','PWM D9／方向D12・D11','PWM0〜255'],['左モーター','PWM D6／方向D7・D8','PWM0〜255'],['ブザー','D13','パッシブ。矩形波で音楽/警告、無音はHIGH。駆動回路に合う配線を確認'],['前方超音波','Trig D10／Echo D3','最大25ms/測定'],['後方赤外線','左D0／右D2','LOWで検知。書き込み時はD0配線を外す。Serialと共用しない']]))
 design+=detail(4,'状態と処理の順番','<p>loop() → do_IR_Tick → do_Dance_Tick → checkSensorsAndObstacles → do_Drive_Tick → do_Music_Tick → 100/20μs待機。checkSensorsAndObstacles内で、回避中はupdate_Avoidだけを実行し、ダンス中は通常の判定を省く。</p>'+table(['状態','用途'],[['Drive_Num / lastDriveCmd / lastDriveCmdMs','現在の走行・直前の単独入力・入力時刻'],['isAvoiding / avoidStartMs','回避状態と駆動開始直後の時刻'],['front / back / isCheckRequested / lastCheckMs','通常走行の障害物と測定要求/時刻'],['isDancing / danceStep / danceStepStartMs / lastDanceCheckMs','8ステップを繰り返すダンスと測定時刻'],['pendingSongNum / pendingSongMs','曲予約と300ms窓の開始'],['isMusicPlaying / currentNotePtr / noteStartMs / noteDurationMs','非ブロッキング音楽再生'],['isWarningPlaying / warningStartMs / isWarningIssued / lastWarnMs','警告再生と再開始制限']])+ '<p>基本は入力が状態を更新し出力が駆動する。ただしOKのstop_Musicは即消音、start_Avoidは回避駆動と警告開始、end_Avoid/stop_Danceは直接停止する。これらを明示的な例外とする。</p>')
 design+=detail(5,'境界条件と優先順位','<p>OK停止が最優先。次に障害物判断、その後にユーザー走行。音楽は走行と独立し、音の出力は警告が優先する。回避中はOKのみ、ダンス中はOKと0のみを受け付ける。</p>'+table(['条件','動作'],[['逆方向入力の間隔 ≤ 300ms','直前の単独入力と逆方向なら停止'],['上下＋左右の間隔 ≤ 900ms','順番を問わず斜め走行。斜めの構成キー再受信では状態を保持し、900ms窓を更新'],['方向入力の間隔 > 900ms','新しい単独方向へ変更'],['曲予約から < 300ms','別番号で取消、同番号は最初の時刻を維持'],['曲予約から ≥ 300ms後の数字入力','新規予約で置換し、新たに300ms待つ'],['通常の曲開始','予約から300ms以上、かつ警告中でない周期で開始/切替'],['回避開始から ≥ 500ms','停止。センサー測定後も時間を再確認。処理遅延による超過あり'],['警告','2kHz音50ms/無音50msを2回。開始から200ms以上で終了。前回開始から1000ms以上あける'],['ダンス','その場旋回・停止のみの8ステップを繰り返す。1周5750msが設定値。通常PWM100、ダンスPWM180、斜め外側130／内側75。実測は処理遅延分延びる']]))
 design+=detail(6,'検証記録（最新設定）',results+'<p><a href="https://github.com/rinne22/robot-phot2/blob/main/REVIEW.md">レビュー結果と再現手順</a></p><pre class="cmd">python3 tests/run_tests.py\npython3 tests/check_guide.py</pre>')
 design+=detail(7,'限界と実機で確認すること','<ul><li>超音波タイムアウトは999cm扱い。センサー故障と障害物なしを区別しない。</li><li>通常のその場旋回中は障害物判定をしない。側方センサーもなく、旋回の安全を保証しない。</li><li>センサー測定や30ms/20ms待機はIR応答と音の波形更新を遅らせる。停止出力300ms以内は目標であり実測値ではない。</li><li>停止は空転停止。車輪の静止時間・停止距離・20cm閾値の妥当性は未測定。</li><li>D13は起動時にブートローダーが駆動する場合がある。音程・音量・波形品質とI/O駆動能力を実機で確認する。</li></ul>')
 design+='</section>'
 start=page.index('<section class="design" id="design">');end=page.index('<section class="design" id="functions"',start)
 page=page[:start]+design+'\n'+page[end:]
 xlsx=build_xlsx(funcs)
 (ROOT/'design-guide/関数設計書.xlsx').write_bytes(xlsx)
 xlsx_b64=base64.b64encode(xlsx).decode()
 cards=f'<section class="design" id="functions" aria-labelledby="functions-title"><h2 id="functions-title">関数設計書</h2><p>最新設定の全{count}関数。添付Excelと同じ項目・表の構成でまとめています。</p><p><a class="fn-download" download="関数設計書.xlsx" href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{xlsx_b64}">関数設計書をダウンロード（Excel）</a></p><div class="fn-controls" hidden><label for="function-search">関数を検索</label><input id="function-search" type="search" placeholder="例：go_Stop、障害物、PWM" autocomplete="off"><span id="function-count" role="status">{count}件</span></div><p id="function-empty" hidden>該当する関数がありません。</p><div class="function-group"><h3>全関数（ソース順）</h3>'
 for f in funcs:
  cards+=f'<details class="function-card" id="fn-{f["name"]}"><summary><code>{f["name"]}()</code><span>{esc(f["desc"].split("。")[0])}</span></summary><div class="body dbody">'+form_html(f)+'</div></details>'
 cards+='</div></section>'
 start=page.index('<section class="design" id="functions"');end=page.index('\n<script>',start)
 page=page[:start]+cards+page[end:]
 page=page.replace("count + '件 / 45件'",f"count + '件 / {count}件'")
 # Rebuild the figures wrapper so all 25 diagrams belong to the same valid section.
 start=page.index('<section class="figs" id="figures">');end=page.index('  <section class="env">',start)
 old=page[start:end];figs=re.findall(r'(<h4[^>]*>図(\d+).*?</h4>)<p class="cap">(.*?)</p><div class="diagram"><pre class="mermaid">(.*?)</pre></div>',old,re.S)
 assert len(figs)==25
 fixes={
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
 E --> F{"DEF以外？"}
 F -->|はい| G["start_Avoid"] --> Z
 F -->|いいえ| Z'''),
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
 fig_html='<section class="figs" id="figures"><h2>設計図</h2><p class="cap">最新設定／図1〜6：操作シーケンス、図7〜25：処理フロー。矢印は呼び出し、状態の受け渡し、実行順を示します。</p>'
 for heading,num,cap,src in figs:
  n=int(num);src=html.unescape(src)
  if n in fixes:cap,src=fixes[n]
  src=src.replace('回避開始時刻を記録し、曲予約を解除','回避開始時刻を記録。曲予約と再生状態は保持')
  if n==2:src=src.replace('IN->>M: go_Stop 完全停止 最優先','IN->>IN: GO_STOPに更新・音楽と警告を消音\n    OUT->>M: 同じ周回の出力で停止')
  if n==5:src=src.replace('SD->>M:','SD->>SD:')
  if n==6:cap='予約から300ms未満に別の数字が届くと予約を取り消します。300ms以上なら最新入力を新規予約として扱います。';src=src.replace('0.3秒以内','300ms未満')
  if n==13:src=src.replace('|後退|','|後退系|').replace('|前進|','|前進系|')
  if n==20:
   cap='300ms未満の予約だけを競合判定に使います。期限以降の数字は新規予約です。'
   src=src.replace('依頼中の曲と別の数字?','300ms未満の予約で別の数字?').replace('同じ数字を依頼中?','300ms未満の予約で同じ数字?')
  if n==25:cap='その場旋回と停止の8ステップを繰り返します。1周の設定時間は5750ms。開始直後は最初の出力前に前後を確認し、障害物またはOKで停止、0で先頭から再開します。'
  fig_html+=heading+'<p class="cap">'+cap+'</p><div class="diagram"><pre class="mermaid">'+esc(src)+'</pre></div>'
 fig_html+='</section>\n'
 page=page[:start]+fig_html+page[end:]
 page=re.sub(r'(<code id="codeText">).*?(</code>)',lambda m:m[1]+esc(code)+m[2],page,count=1,flags=re.S)
 page=re.sub(r'<style id="function-form-style">.*?</style>', '', page, flags=re.S)
 page=page.replace('</head>', '<style id="function-form-style">.function-form{min-width:640px;table-layout:fixed}.function-form th{background:#ddd;color:#18262b;vertical-align:middle;text-align:center}.function-form td{white-space:pre-wrap;overflow-wrap:anywhere}.function-form td,.function-form th{border:1px solid #8a949a;padding:10px}.function-form tr:first-child td{font-weight:700}</style>'+'</head>')
 page=page.replace('使用言語：C言語（Arduino言語）','使用言語：C++（Arduinoスケッチ）')
 page=page.replace('IRremote</code>（4.x系）','IRremote</code>（検証版4.4.1／4.x系）')
 page=re.sub(r'<b>\d+</b> PC模擬試験項目','<b>47</b> PC模擬試験項目',page)
 page=re.sub(r'<b>\d+</b> 関数の設計',f'<b>{count}</b> 関数の設計',page)
 page=page.replace('<b>45</b> 関数の設計',f'<b>{count}</b> 関数の設計').replace('<b>24</b> 結合テスト項目','<b>47</b> PC模擬試験項目')
 page=page.replace('結合テストはPC上の疑似環境で実施。実機確認項目は開発設計に記載しています。','最新設定の検証結果は開発設計とREVIEW.mdを参照。実機試験は未実施です。')
 rev=f'<section class="overview" id="revision"><h2>最新設定統一版（2026年11月11日）</h2><p>通常PWM100、ダンスPWM180、斜め外側130／内側75、斜め入力900ms、逆方向入力300ms、8ステップ反復ダンスを基準に、要件・開発設計・全{count}関数・図25枚・掲載コード・ダウンロード・Excelを統一しました。</p><p><a href="robot_final.ino" download>Arduinoコードをダウンロード</a> ／ <a href="https://github.com/rinne22/robot-phot2/blob/main/REVIEW.md">検証記録</a></p><p>検証の対象版と結果はREVIEW.mdを参照。実機の音質・停止応答・停止距離は未確認です。</p></section>'
 page=re.sub(r'<section class="overview" id="revision">.*?</section>',lambda m:rev,page,count=1,flags=re.S)
 page=page.replace('Arduino Unoでの今回の改訂版のビルド・実機試験は未実施です。PWMや障害物検出の応答は実機で確認してください。旧版1.6の検証記録は今回の変更の確認結果ではありません。','最新設定のビルド結果はREVIEW.mdを参照。実機試験は未実施です。')
 page=re.sub(r'改訂1\.6はPC模擬試験\d+項目とUnoビルドを確認。実機試験は未実施です。','最新設定のPC模擬試験47項目とUnoビルドを確認。実機試験は未実施です。',page)
 for path in ['design-guide/index.html','index.html']:
  out=page if path.startswith('design-guide/') else page.replace('href="functions.csv"','href="design-guide/functions.csv"')
  (ROOT/path).write_text(out)
 (ROOT/'design-guide/robot_final.ino').write_text(code)
 print(f'Synchronized {count} functions, {len(figs)} diagrams and {len(reqs)} requirements')
if __name__=='__main__':main()
