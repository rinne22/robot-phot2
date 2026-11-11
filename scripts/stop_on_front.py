"""Generate a separate sketch that stops instead of reversing at front obstacles."""
from pathlib import Path

def build_variant(root):
    code=(root/'robot_final.ino').read_text()
    old='  if (front && back)                    return GO_RIGHT;'
    assert code.count(old)==1
    code=code.replace(old,'''  // 別版：前進系で前方を検知したら、後退せず停止する（前後同時も停止）。
  if (front && (Drive_Num == GO_ADVANCE || Drive_Num == GO_FORWARD_LEFT || Drive_Num == GO_FORWARD_RIGHT))
    return GO_STOP;
'''+old)
    old='  if (action != DEF) start_Avoid(action);'
    assert code.count(old)==1
    code=code.replace(old,'''  if (action == GO_STOP) {
    end_Avoid();              // その場で停止。自動走行は開始しない。
    lastDriveCmd = GO_STOP;   // 次の方向入力は新規の単独指示として扱う。
    warning();               // 音楽を保持し、警告だけ優先する。
  } else if (action != DEF) start_Avoid(action);''')
    # Remove the unreachable original front-only reversing rule from this variant.
    old='''  if (front && (Drive_Num == GO_ADVANCE || Drive_Num == GO_FORWARD_LEFT || Drive_Num == GO_FORWARD_RIGHT))
    return GO_BACK;          // 前進系の方向で前方障害物：後退
'''
    assert code.count(old)==1
    code=code.replace(old,'')
    code='''// 前方障害物で自動後退しない別版（2026-11-11）
// 前進・前左・前右で前方を検知したら停止し警告。再発進は次のリモコン入力。
// 手動の後退、後方障害物時の従来回避、斜め走行、音楽、ダンスは利用できます。
// Arduino IDEでは robot_front_stop フォルダの robot_front_stop.ino として保存してください。
'''+code
    (root/'design-guide/robot_front_stop.ino').write_text(code)

if __name__=='__main__':
    build_variant(Path(__file__).resolve().parents[1])
