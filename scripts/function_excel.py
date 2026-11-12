"""Create an XLSX and HTML forms using the user's uploaded function design template."""
import base64, io, re, math, zipfile
from copy import copy
from datetime import datetime
from pathlib import Path
from html import escape
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.worksheet.pagebreak import Break

# Logical input/output includes effects delegated to called functions.
IO={
'set_RightMotor':('—','D12・D11：isDir1High / isDir2High'),
'set_LeftMotor':('—','D7・D8：isDir1High / isDir2High'),
'set_MotorSpeed':('—','D9・D6：rightSpeed / leftSpeed のPWM'),
'go_Advance':('SPEED','左右前進、PWM100/100'), 'go_Back':('SPEED','左右後退、PWM100/100'),
'go_Left':('SPEED、DANCE_SPEED、isDancing','右前進・左後退、通常PWM100/100・ダンスPWM180/180'), 'go_Right':('SPEED、DANCE_SPEED、isDancing','右後退・左前進、通常PWM100/100・ダンスPWM180/180'),
'go_ForwardLeft':('DIAGONAL_OUTER_SPEED、DIAGONAL_INNER_SPEED','左右前進、右PWM220・左60'), 'go_ForwardRight':('RIGHT_CURVE_OUTER_SPEED、RIGHT_CURVE_INNER_SPEED','左右前進、右PWM40・左245'),
'go_BackLeft':('DIAGONAL_OUTER_SPEED、DIAGONAL_INNER_SPEED','左右後退、右PWM40・左245'), 'go_BackRight':('RIGHT_CURVE_OUTER_SPEED、RIGHT_CURVE_INNER_SPEED','左右後退、右PWM245・左40'),
'go_Stop':('—','左右PWM0・方向4端子LOW'),
'do_Drive_Tick':('Drive_Num','左右モーターの方向・PWM。不正状態はDrive_Num=GO_STOP'),
'warning':('millis()・micros()、isWarningPlaying、isWarningIssued、lastWarnMs','警告状態・開始時刻・フェーズ・波形状態、D13=HIGH'),
'do_Warning_Tick':('警告状態・開始時刻、millis()・micros()、音楽の再生状態','D13の警告矩形波またはHIGH、警告状態、音符の再開時刻'),
'play_Tone':('micros()、isWarningPlaying','発音時間・半周期・波形状態。警告中でなければD13=HIGH'),
'get_SongNote':('PROGMEM上の音符ペア','—'), 'get_SongLength':('PROGMEM上の音符ペア','—'),
'play_Note':('音符データ、TEMPO_MS、millis()','音符の開始時刻・長さ、発音時間・半周期・波形状態'),
'stop_Music':('—','再生・予約・警告・ダンス曲フラグを解除、音符ポインタをnull、半周期0、D13=HIGH'),
'play_Music':('SONG_TABLE、曲データ、millis()','音符ポインタ・再生フラグ・最初の音符状態（走行状態は変更しない）'),
'is_MusicDue':('pendingSongNum、pendingSongMs、millis()','—'),
'do_Music_Tick':('予約・音符・警告・波形の各状態、曲データ、millis()・micros()','曲予約・音符・再生/警告状態の更新、D13の矩形波/無音'),
'watch':('D3 Echoパルス（最大25ms待機）','D10 Trigに10μsパルス'),
'is_FrontBlocked':('watch()の距離結果、DISTANCE_LIMIT','前方センサーへの測定トリガー。初回検知時30ms待機'),
'is_BackIrOn':('後方赤外線 D0 / D2','—'),
'is_BackBlocked':('is_BackIrOn()の検知結果','初回検知時20ms待機'),
'start_Avoid':('millis()、現在の警告状態','Drive_Num・lastDriveCmd・回避フラグ/時刻、モーター、警告状態'),
'end_Avoid':('—','isAvoiding=false、Drive_Num=GO_STOP、モーター停止'),
'update_Avoid':('avoidStartMs、Drive_Num、前方センサー、millis()','終了条件成立時に回避状態解除・GO_STOP・モーター停止'),
'is_CheckTime':('Drive_Num、isCheckRequested、lastCheckMs、millis()','—'),
'mark_Checked':('millis()','isCheckRequested=false、lastCheckMs=現在時刻'),
'update_ObstacleFlags':('前後センサーの検知結果','front / back：1=検知、0=未検知'),
'decide_AvoidAction':('front、back、Drive_Num','—'),
'checkSensorsAndObstacles':('回避/ダンス状態、走行状態、前後センサー、時刻','障害物フラグ・測定時刻、必要に応じて前方停止・警告、または前進/右旋回の回避開始/終了・モーター'),
'stop_Dance':('isDanceMusic','isDancing=false、Drive_Num=GO_STOP、モーターとダンス専用曲を停止'),
'dance_Action':('—','—'), 'dance_Duration':('DANCE_SWAY_MS、DANCE_PAUSE_MS、DANCE_SPIN_MS、DANCE_LEFT_SPIN_MS、DANCE_LOOP_PAUSE_MS','—'),
'start_Dance':('isAvoiding、millis()','ダンス状態・ステップ・開始時刻・測定要求、曲予約解除、専用曲の開始、Drive_Num'),
'do_Dance_Tick':('ダンス状態・ステップ・時刻、前後センサー、millis()','ステップ/時刻/Drive_Num更新。8ステップ後は先頭へ戻る。障害物時はダンス解除とモーター停止'),
'is_DiagonalComponent':('—','—'), 'is_OppositeDrive':('—','—'), 'get_DiagonalDrive':('—','—'),
'set_Drive':('Drive_Num、lastDriveCmd、lastDriveCmdMs、CONFLICT_MS、millis()','Drive_Num、直前指示と時刻、通常入力時isCheckRequested=true'),
'read_IR_Command':('IR受信データ・リピートフラグ','resume()で次の受信を許可'),
'handle_StopButton':('—','回避・ダンス・音楽・警告・曲予約解除、D13=HIGH、Drive_NumとlastDriveCmd=GO_STOP'),
'handle_DriveButton':('millis()、直前の走行指示と時刻','set_Drive経由で走行指示・時刻・確認要求を更新'),
'get_SongNum':('NUM_CODES','—'),
'is_NumberConflict':('pendingSongNum、pendingSongMs、millis()','—'),
'handle_NumberButton':('NUM_CODES、pendingSongNum、pendingSongMs、millis()','pendingSongNum・pendingSongMs（予約取消/維持/新規予約）'),
'do_IR_Tick':('IR受信、回避・ダンス・走行・曲予約状態、時刻','ボタンに応じて走行・ダンス・曲予約・停止状態を更新。OKでD13消音'),
'init_MotorPins':('—','モーター6端子をOUTPUT、PWM0・方向LOW'),
'init_BuzzerPin':('—','D13をHIGH→OUTPUT→HIGH'),
'init_SensorPins':('—','D10=OUTPUT、D3/D0/D2=INPUT'),
'init_IrReceiver':('IR_RECEIVE_PIN、DISABLE_LED_FEEDBACK','D4でIR受信開始、受信LED点滅を無効化'),
'setup':('電源投入・リセット','モーター/ブザー停止・センサー端子設定・IR受信開始'),
'loop':('IR受信、前後センサー、各共有状態、IS_IR、時刻','走行・ダンス・回避・音楽・警告の状態と出力を周期更新、100/20μs待機'),
}
NOTES={
'watch':'タイムアウトを999cm（障害物なし）として扱う。故障と遠方を区別しない。',
'go_Stop':'空転停止。車輪が静止するまでの時間・距離は実機未確認。',
'play_Tone':'ソフトウェア波形。センサー待機中は波形更新が遅れる。',
'do_Warning_Tick':'2kHz・200msは設定値。処理遅延による音程・終了時刻のずれは実機評価する。',
'handle_StopButton':'モーター停止出力は同じ周回のdo_Drive_Tickが行う。',
'init_BuzzerPin':'ブートローダーがD13を駆動する起動期間は制御対象外。',
'get_SongNote':'notePtrは有効なPROGMEM上の音符ペアを指すこと。',
'get_SongLength':'notePtrは有効なPROGMEM上の音符ペアを指すこと。',
}

def rows(f):
 inp,out=IO[f['name']]
 args=f['args'].split(', ') if f['args'] else []
 argtype='\n'.join(re.sub(r'\s+\w+$','',a) for a in args) or '—'
 argnames='\n'.join(re.search(r'(\w+)$',a)[1] for a in args) or 'なし'
 return [
  ('引数',argtype,argnames),
  ('戻り値',f['ret'],'なし' if f['ret']=='void' else f['desc']),
  ('入力','状態・信号' if inp!='—' else '—',inp),
  ('出力','状態・信号' if out!='—' else '—',out),
 ]

def form_html(f):
 esc=escape
 data=rows(f)
 tr=lambda label,value:f'<tr><th scope="row">{label}</th><td colspan="3">{esc(value)}</td></tr>'
 h='<div class="tw"><table class="function-form"><colgroup><col style="width:15%"><col style="width:13%"><col style="width:19%"><col style="width:53%"></colgroup><tbody>'
 h+=tr('機能概要',f['desc'].split('。')[0])+tr('処理内容',f['desc'])+tr('関数形式',f['sig']+';')
 h+='<tr><th scope="row" rowspan="5">入出力</th><th scope="col">種類</th><th scope="col">形式</th><th scope="col">内容</th></tr>'
 for kind,typ,content in data:h+=f'<tr><th scope="row">{kind}</th><td>{esc(typ)}</td><td>{esc(content)}</td></tr>'
 h+=tr('ソースファイル','robot_final.ino')+tr('呼び出し関数',f['calls'])+tr('備考',NOTES.get(f['name'],'—'))
 return h+'</tbody></table></div>'

def build_xlsx(funcs):
 w=openpyxl.Workbook();index=w.active;index.title='関数一覧'
 index.append(['関数設計書（改訂1.6）','2026年11月10日'])
 index.append(['添付の帳票に合わせた全56関数','実機試験は未実施'])
 index.append(['No.','関数名','機能概要','関数形式','ソース行'])
 index.freeze_panes='C4';index.auto_filter.ref=f'A3:E{len(funcs)+3}'
 for col,width in [('A',8),('B',32),('C',65),('D',65),('E',12)]:index.column_dimensions[col].width=width
 for i,f in enumerate(funcs,1):
  s=w.create_sheet(f['name']);s.sheet_view.showGridLines=False
  # Recreate the observed form structure without publishing the uploaded workbook.
  edge=Side(style='thin',color='808080')
  for row in s.iter_rows(min_row=2,max_row=19,min_col=2,max_col=5):
   for cell in row:
    cell.font=Font(name='ＭＳ Ｐゴシック',size=11)
    cell.border=Border(left=edge,right=edge,top=edge,bottom=edge)
  for region in ['B3:B4','B6:B14','B16:B18','C2:E2','C3:E4','C5:E5','C10:C14','C15:E15']:s.merge_cells(region)
  for cell,value in {'B2':'機能概要','B3':'処理内容','B5':'関数形式','B6':'入出力','C6':'種類','D6':'形式','E6':'内容','C7':'引数','C8':'戻り値','C9':'入力','C10':'出力','B15':'ソースファイル','B16':'呼び出し関数','B19':'備考'}.items():
   s[cell]=value;s[cell].fill=PatternFill('solid',fgColor='DDDDDD');s[cell].font=Font(name='ＭＳ Ｐゴシック',size=11,bold=True)
  # Keep the template's four-column account form, enlarge text areas to avoid clipping.
  s.column_dimensions['A'].width=3;s.column_dimensions['B'].width=17
  s.column_dimensions['C'].width=13;s.column_dimensions['D'].width=24;s.column_dimensions['E'].width=68
  s.merge_cells('C16:E18');s.merge_cells('C19:E19')
  s['C2']=f['desc'].split('。')[0];s['C3']=f['desc'];s['C5']=f['sig']+';'
  for row,(kind,typ,content) in zip([7,8,9,10],rows(f)):
   s[f'D{row}']=typ;s[f'E{row}']=content
  # The first template provides five output slots; one merged text field is clearer for logical output.
  s.merge_cells('D10:D14');s.merge_cells('E10:E14')
  s['C15']='robot_final.ino';s['C16']=f['calls'];s['C19']=NOTES.get(f['name'],'—')
  for row in s:
   for cell in row:
    if cell.value is not None:cell.alignment=Alignment(horizontal='left',vertical='center',wrap_text=True)
  for cell in ['B2','B3','B5','B6','B15','B16','B19','C6','D6','E6']:
   s[cell].alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
  for r,height in {2:52,3:38,4:38,5:48,6:23,7:55,8:80,9:80,10:18,11:18,12:18,13:18,14:18,15:26,16:25,17:25,18:25,19:62}.items():s.row_dimensions[r].height=height
  s['B21']='関数一覧へ';s['B21'].hyperlink="#'関数一覧'!A1";s['B21'].style='Hyperlink'
  s.print_area='B2:E19';s.page_setup.orientation='portrait';s.page_setup.paperSize=s.PAPERSIZE_A4
  s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=1;s.sheet_properties.pageSetUpPr.fitToPage=True
  s.print_options.horizontalCentered=True
  index.append([i,f['name'],f['desc'].split('。')[0],f['sig']+';',f['line']])
  index.cell(i+3,2).hyperlink=f"#'{s.title}'!B2";index.cell(i+3,2).style='Hyperlink'
 for row in index:
  for c in row:c.alignment=Alignment(vertical='top',wrap_text=True)
  if row[0].row>3:index.row_dimensions[row[0].row].height=50
 for c in index[3]:c.font=Font(name='ＭＳ Ｐゴシック',bold=True);c.fill=PatternFill('solid',fgColor='DDDDDD')
 fixed=datetime(2026,11,10);w.properties.created=fixed;w.properties.modified=fixed
 temp=io.BytesIO();w.save(temp)
 # Stable ZIP metadata and workbook modified property allow repeatable generation.
 source=zipfile.ZipFile(temp);out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as target:
  for name in sorted(source.namelist()):
   data=source.read(name)
   if name=='docProps/core.xml':data=re.sub(rb'<dcterms:modified[^>]*>.*?</dcterms:modified>',b'<dcterms:modified xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="dcterms:W3CDTF">2026-11-10T00:00:00Z</dcterms:modified>',data)
   info=zipfile.ZipInfo(name,(2026,11,10,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;target.writestr(info,data)
 return out.getvalue()
