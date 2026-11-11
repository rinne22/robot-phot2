// リモコン操作ロボット（走行・音楽・超音波センサー・後方赤外線センサー・ブザー）
// 処理の流れ： 入力(do_IR_Tick) → 判断(checkSensorsAndObstacles) → 出力(do_Drive_Tick)
// Arduino Uno / IRremote 4.x / レビュー改訂 1.6 (2026-11-10)
//
// 【配線の注意】
//  ・D0（左後方センサー）をつないだままだとUSB書き込みに失敗することがあります。
//    書き込み中だけ配線を外してください。（そのためSerialは使っていません）
//  ・サーボ(D5)は使っていません。Servoをattachすると D9/D10 のPWMが使えなくなります。

#include <IRremote.hpp>
#include <avr/pgmspace.h>

// ---------- ピン定義 ----------
#define IR_RECEIVE_PIN   4    // リモコン受信機

#define SPEED_PIN_R        9    // 右モーター PWM
#define RIGHT_DIR_PIN1  12   // 右モーター 方向1
#define RIGHT_DIR_PIN2  11   // 右モーター 方向2
#define SPEED_PIN_L        6    // 左モーター PWM
#define LEFT_DIR_PIN1   7    // 左モーター 方向1
#define LEFT_DIR_PIN2   8    // 左モーター 方向2

#define BUZZ_PIN         13   // ブザー（LOWで鳴動、HIGHで停止）
#define BACK_IR_L_PIN      0    // 左後方 赤外線センサー（障害物でLOW）
#define BACK_IR_R_PIN      2    // 右後方 赤外線センサー（障害物でLOW）
#define ECHO_PIN         3    // 超音波 Echo
#define TRIG_PIN         10   // 超音波 Trig

// ---------- 設定値 ----------
#define DISTANCE_LIMIT    20   // 前方の障害物とみなす距離（cm）
#define SPEED            140  // 通常走行・ダンスの基本速度（0〜255、従来200）
#define CHECK_INTERVAL_MS   100  // センサー確認の間隔（ms）
#define CONFLICT_MS      300  // 逆向きのコードを矛盾とみなす時間（ms）
#define AVOID_MS         500  // 回避動作を続ける時間（ms）
#define WARN_TONE_HZ     2000 // パッシブブザーの警告周波数（Hz）
#define WARN_PHASE_MS    50   // 警告の各フェーズ（ms）
#define WARN_INTERVAL_MS    1000 // 警告音の最短間隔（ms）
#define TEMPO_MS         150  // 8分音符1つの長さ（ms）
#define SONG_COUNT       9    // 曲の数（ボタン1〜9）
#define NO_COMMAND      -1    // 受信なし

// ---------- リモコンのボタンコード ----------
#define IR_ADVANCE 24   // ↑
#define IR_BACK    82   // ↓
#define IR_RIGHT   90   // →
#define IR_LEFT    8    // ←
#define IR_STOP    28   // OK
#define IR_DANCE   25   // 0ボタン (0x19) - ダンス開始
const uint8_t NUM_CODES[SONG_COUNT] = { 69, 70, 71, 68, 64, 67, 7, 21, 9 };  // ボタン1〜9

// ---------- 状態 ----------
int front = 0;                   // 前方に障害物 1=あり
int back  = 0;                   // 後方に障害物 1=あり

enum DriveState { GO_ADVANCE, GO_LEFT, GO_RIGHT, GO_BACK, GO_STOP, DEF,
                  GO_FORWARD_LEFT, GO_FORWARD_RIGHT, GO_BACK_LEFT, GO_BACK_RIGHT };  // DEF は「動作なし」
DriveState Drive_Num = GO_STOP;          // 現在の動作状態（初期値は停止）
DriveState lastDriveCmd = GO_STOP;            // 直前に受け付けた走行コマンド
unsigned long lastDriveCmdMs = 0;
bool IS_IR = true;               // ループ遅延の切替

bool isAvoiding = false;           // 回避動作中か
unsigned long avoidStartMs = 0;
unsigned long lastCheckMs = 0;       // 最後に障害物を調べた時刻
int pendingSongNum = 0;             // 再生を依頼された曲番号（0=依頼なし）
unsigned long pendingSongMs = 0;     // 曲を依頼された時刻
bool isCheckRequested = false;         // 新しい指示の直後はすぐ判断する

// 0ボタンで開始するダンス（delayで待たずに進める）
bool isDancing = false;
uint8_t danceStep = 0;
unsigned long danceStepStartMs = 0;
unsigned long lastDanceCheckMs = 0;
const uint8_t DANCE_STEPS = 9;

// 音楽と警告音は delay で待たず、loop から定期的に更新する
bool isMusicPlaying = false;
const int16_t* currentNotePtr = nullptr;
unsigned long noteStartMs = 0;
unsigned long noteDurationMs = 0;
unsigned long toneDurationMs = 0;
unsigned long halfPeriodUs = 0;
unsigned long lastToneToggleUs = 0;
bool isToneLow = false;
bool isWarningPlaying = false;
unsigned long warningStartMs = 0;
unsigned long warningPhaseMs = 0;
unsigned long lastWarnMs = 0;
bool isWarningIssued = false;
unsigned long lastWarningToggleUs = 0;
bool isWarningToneLow = false;
uint8_t warningPhase = 0;

// ---------- 音階 ----------
#define NC4 262
#define ND4 294
#define NE4 330
#define NF4 349
#define NG4 392
#define NA4 440
#define NB4 494
#define NC5 523
#define ND5 587
#define NE5 659
#define NF5 698
#define NG5 784
#define END_MARK -1

const int16_t SONG_1[] PROGMEM = { NC4,2, ND4,2, NE4,2, NF4,2, NG4,2, NA4,2, NB4,2, NC5,4, END_MARK,0 };
const int16_t SONG_2[] PROGMEM = { NC4,2, NC4,2, NG4,2, NG4,2, NA4,2, NA4,2, NG4,4,
                                  NF4,2, NF4,2, NE4,2, NE4,2, ND4,2, ND4,2, NC4,4, END_MARK,0 };
const int16_t SONG_3[] PROGMEM = { NC4,2, ND4,2, NE4,2, NF4,2, NE4,2, ND4,2, NC4,4,
                                  NE4,2, NF4,2, NG4,2, NA4,2, NG4,2, NF4,2, NE4,4,
                                  NC4,4, NC4,4, NC4,4, NC4,4,
                                  NC4,1, NC4,1, ND4,1, ND4,1, NE4,1, NE4,1, NF4,1, NF4,1, NE4,2, ND4,2, NC4,4, END_MARK,0 };
const int16_t SONG_4[] PROGMEM = { NG4,2, NE4,2, NE4,4, NF4,2, ND4,2, ND4,4,
                                  NC4,2, ND4,2, NE4,2, NF4,2, NG4,2, NG4,2, NG4,4, END_MARK,0 };
const int16_t SONG_5[] PROGMEM = { NG4,1, NG4,1, NA4,2, NG4,2, NC5,2, NB4,4,
                                  NG4,1, NG4,1, NA4,2, NG4,2, ND5,2, NC5,4,
                                  NG4,1, NG4,1, NG5,2, NE5,2, NC5,2, NB4,2, NA4,2,
                                  NF5,1, NF5,1, NE5,2, NC5,2, ND5,2, NC5,4, END_MARK,0 };
const int16_t SONG_6[] PROGMEM = { NE4,2, ND4,2, NC4,2, ND4,2, NE4,2, NE4,2, NE4,4,
                                  ND4,2, ND4,2, ND4,4, NE4,2, NG4,2, NG4,4, END_MARK,0 };
const int16_t SONG_7[] PROGMEM = { NE4,2, NE4,2, NE4,4, NE4,2, NE4,2, NE4,4,
                                  NE4,2, NG4,2, NC4,3, ND4,1, NE4,4, END_MARK,0 };
const int16_t SONG_8[] PROGMEM = { NE4,2, NE4,2, NF4,2, NG4,2, NG4,2, NF4,2, NE4,2, ND4,2,
                                  NC4,2, NC4,2, ND4,2, NE4,2, NE4,3, ND4,1, ND4,4, END_MARK,0 };
const int16_t SONG_9[] PROGMEM = { NC4,2, NE4,2, NG4,2, NC5,4, NG4,2, NC5,6, END_MARK,0 };

const int16_t* const SONG_TABLE[SONG_COUNT] PROGMEM = { SONG_1, SONG_2, SONG_3, SONG_4, SONG_5, SONG_6, SONG_7, SONG_8, SONG_9 };

// =====================================================
// 出力：モーター制御
// =====================================================
void set_RightMotor(bool isDir1High, bool isDir2High) {
  digitalWrite(RIGHT_DIR_PIN1, isDir1High);
  digitalWrite(RIGHT_DIR_PIN2, isDir2High);
}

void set_LeftMotor(bool isDir1High, bool isDir2High) {
  digitalWrite(LEFT_DIR_PIN1, isDir1High);
  digitalWrite(LEFT_DIR_PIN2, isDir2High);
}

void set_MotorSpeed(int rightSpeed, int leftSpeed) {   // 左右のPWMを設定
  analogWrite(SPEED_PIN_R, rightSpeed);
  analogWrite(SPEED_PIN_L, leftSpeed);
}

void go_Advance() {            // 前進
  set_RightMotor(HIGH, LOW);  set_LeftMotor(HIGH, LOW);
  set_MotorSpeed(SPEED, SPEED);
}

void go_Back() {               // 後退
  set_RightMotor(LOW, HIGH);  set_LeftMotor(LOW, HIGH);
  set_MotorSpeed(SPEED, SPEED);
}

void go_Left() {               // 左折（その場旋回：右前進・左後退）
  set_RightMotor(HIGH, LOW);  set_LeftMotor(LOW, HIGH);
  set_MotorSpeed(SPEED, SPEED);
}

void go_Right() {              // 右折（その場旋回：右後退・左前進）
  set_RightMotor(LOW, HIGH);  set_LeftMotor(HIGH, LOW);
  set_MotorSpeed(SPEED, SPEED);
}

// 左右の回転速度を変え、進みながら曲がる（内側は半速）
void go_ForwardLeft() {
  set_RightMotor(HIGH, LOW); set_LeftMotor(HIGH, LOW);
  set_MotorSpeed(SPEED, SPEED / 2);
}

void go_ForwardRight() {
  set_RightMotor(HIGH, LOW); set_LeftMotor(HIGH, LOW);
  set_MotorSpeed(SPEED / 2, SPEED);
}

void go_BackLeft() {
  set_RightMotor(LOW, HIGH); set_LeftMotor(LOW, HIGH);
  set_MotorSpeed(SPEED / 2, SPEED);
}

void go_BackRight() {
  set_RightMotor(LOW, HIGH); set_LeftMotor(LOW, HIGH);
  set_MotorSpeed(SPEED, SPEED / 2);
}

void go_Stop() {               // 完全停止（PWM0・方向LOW/LOW）
  set_MotorSpeed(0, 0);
  set_RightMotor(LOW, LOW);  set_LeftMotor(LOW, LOW);
}

void do_Drive_Tick() {         // Drive_Num に従ってモーターを動かす
  switch (Drive_Num) {
    case GO_ADVANCE: go_Advance(); break;
    case GO_BACK:    go_Back();    break;
    case GO_LEFT:    go_Left();    break;
    case GO_RIGHT:   go_Right();   break;
    case GO_FORWARD_LEFT:  go_ForwardLeft();  break;
    case GO_FORWARD_RIGHT: go_ForwardRight(); break;
    case GO_BACK_LEFT:     go_BackLeft();     break;
    case GO_BACK_RIGHT:    go_BackRight();    break;
    case GO_STOP:    go_Stop();    break;
    default: Drive_Num = GO_STOP; go_Stop(); break;
  }
}

// =====================================================
// ブザー
// =====================================================
// 警告音は音楽より優先。50msの2kHz音と50msの無音を2回。
void warning() {
  unsigned long now = millis();
  if (isWarningPlaying || (isWarningIssued && now - lastWarnMs < WARN_INTERVAL_MS)) return;
  isWarningIssued = true;
  lastWarnMs = now;
  warningStartMs = now;
  warningPhaseMs = now;
  warningPhase = 0;
  isWarningPlaying = true;
  lastWarningToggleUs = micros();
  isWarningToneLow = false;
  digitalWrite(BUZZ_PIN, HIGH);
}

void do_Warning_Tick() {
  if (!isWarningPlaying) return;
  unsigned long now = millis();
  unsigned long elapsedMs = now - warningStartMs;
  if (elapsedMs >= 4UL * WARN_PHASE_MS) {
    isWarningPlaying = false;
    digitalWrite(BUZZ_PIN, HIGH);
    if (isMusicPlaying) noteStartMs += elapsedMs;
    lastToneToggleUs = micros();
    isToneLow = false;
    return;
  }
  warningPhase = elapsedMs / WARN_PHASE_MS;
  if (warningPhase % 2 != 0) {
    isWarningToneLow = false;
    digitalWrite(BUZZ_PIN, HIGH);
    return;
  }
  unsigned long nowUs = micros();
  if (nowUs - lastWarningToggleUs >= 500000UL / WARN_TONE_HZ) {
    lastWarningToggleUs = nowUs;
    isWarningToneLow = !isWarningToneLow;
    digitalWrite(BUZZ_PIN, isWarningToneLow ? LOW : HIGH);
  }
}

// 指定した1音の発音を開始する。実際のLOW/HIGH切替はdo_Music_Tickで行う。
void play_Tone(int freq, int ms) {
  toneDurationMs = ms > 0 ? (unsigned long)ms : 0;
  halfPeriodUs = freq > 0 ? 500000UL / (unsigned long)freq : 0;
  lastToneToggleUs = micros();
  isToneLow = false;
  if (!isWarningPlaying) digitalWrite(BUZZ_PIN, HIGH);
}

int get_SongNote(const int16_t* notePtr) {
  return (int16_t)pgm_read_word(notePtr);
}

int get_SongLength(const int16_t* notePtr) {
  return (int16_t)pgm_read_word(notePtr + 1);
}

// 1音 + 20msの休止をスケジュールする
void play_Note(const int16_t* notePtr) {
  noteDurationMs = (unsigned long)get_SongLength(notePtr) * TEMPO_MS;
  noteStartMs = millis();
  int soundMs = noteDurationMs > 20 ? (int)(noteDurationMs - 20) : 0;
  play_Tone(get_SongNote(notePtr), soundMs);
}

void stop_Music() {
  isMusicPlaying = false;
  currentNotePtr = nullptr;
  pendingSongNum = 0;
  isWarningPlaying = false;
  halfPeriodUs = 0;
  digitalWrite(BUZZ_PIN, HIGH);
}

// 再生を開始するが、走行状態は変更しない
void play_Music(int songNum) {
  if (songNum < 1 || songNum > SONG_COUNT) return;
  currentNotePtr = (const int16_t*)pgm_read_ptr(&SONG_TABLE[songNum - 1]);
  isMusicPlaying = true;
  play_Note(currentNotePtr);
}

bool is_MusicDue() {
  return pendingSongNum != 0 && millis() - pendingSongMs >= CONFLICT_MS;
}

void do_Music_Tick() {
  do_Warning_Tick();
  if (isWarningPlaying) return;  // 同じブザーなので警告音を優先

  // 走行中・停止中を問わず曲を開始 / 切替
  if (is_MusicDue()) {
    int songNum = pendingSongNum;
    pendingSongNum = 0;
    play_Music(songNum);
  }
  if (!isMusicPlaying || currentNotePtr == nullptr) return;

  unsigned long nowMs = millis();
  if (nowMs - noteStartMs >= noteDurationMs) {
    currentNotePtr += 2;  // 周波数と長さの次の組
    if (get_SongNote(currentNotePtr) == END_MARK) {
      isMusicPlaying = false;
      currentNotePtr = nullptr;
      halfPeriodUs = 0;
      digitalWrite(BUZZ_PIN, HIGH);
      return;
    }
    play_Note(currentNotePtr);
    nowMs = millis();
  }

  // 休符 / 音符末尾の20ms無音
  if (halfPeriodUs == 0 || nowMs - noteStartMs >= toneDurationMs) {
    if (isToneLow) {
      isToneLow = false;
      digitalWrite(BUZZ_PIN, HIGH);
    }
    return;
  }

  // 1ループにつき1回だけ波形を進め、他の制御をブロックしない
  unsigned long nowUs = micros();
  if (nowUs - lastToneToggleUs >= halfPeriodUs) {
    lastToneToggleUs = nowUs;
    isToneLow = !isToneLow;
    digitalWrite(BUZZ_PIN, isToneLow ? LOW : HIGH);
  }
}

// =====================================================
// センサー
// =====================================================
int watch() {                  // 超音波センサーで前方の距離(cm)を測る
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long echoUs = pulseIn(ECHO_PIN, HIGH, 25000);   // 最大25ms待つ
  if (echoUs == 0) return 999;                    // 反応なし＝障害物なし
  return (int)(echoUs / 58);
}

bool is_FrontBlocked() {         // 前方の障害物（2回続けて検知したら確定）
  if (watch() <= DISTANCE_LIMIT) {
    delay(30);
    return watch() <= DISTANCE_LIMIT;
  }
  return false;
}

bool is_BackIrOn() {
  return digitalRead(BACK_IR_L_PIN) == LOW || digitalRead(BACK_IR_R_PIN) == LOW;
}

bool is_BackBlocked() {          // 後方の障害物（2回続けて検知したら確定）
  if (is_BackIrOn()) {
    delay(20);
    return is_BackIrOn();
  }
  return false;
}

// =====================================================
// 判断：センサーの優先度判断（優先度2：ユーザー指示より優先）
// =====================================================
void start_Avoid(DriveState act) {     // 回避動作を始める
  Drive_Num = act;             // 状態を自動的に上書き
  lastDriveCmd = GO_STOP;
  do_Drive_Tick();             // 先にモーターを動かし
  isAvoiding = true;
  avoidStartMs = millis();     // 駆動開始直後から回避時間を測る
  warning();                   // 動かしながら警告音を鳴らす
}

void end_Avoid() {             // 回避動作を終えて停止
  isAvoiding = false;
  Drive_Num = GO_STOP;
  go_Stop();
}

void update_Avoid() {          // 回避動作中：1回だけ終了条件を判定する
  if (millis() - avoidStartMs >= AVOID_MS) { end_Avoid(); return; }

  // 行ったり来たりを防ぐため、進行先が塞がっていれば切り替えず停止
  bool blocked = false;
  if (Drive_Num == GO_BACK || Drive_Num == GO_BACK_LEFT || Drive_Num == GO_BACK_RIGHT)
    blocked = is_BackBlocked();
  else if (Drive_Num == GO_ADVANCE || Drive_Num == GO_FORWARD_LEFT || Drive_Num == GO_FORWARD_RIGHT)
    blocked = is_FrontBlocked();

  // センサー測定にも時間がかかるため、測定直後に500msを再確認する
  if (blocked || millis() - avoidStartMs >= AVOID_MS) end_Avoid();
}

bool is_CheckTime() {          // 障害物を調べる時刻か（前進中・後退中だけ）
  if (Drive_Num != GO_ADVANCE && Drive_Num != GO_BACK &&
      Drive_Num != GO_FORWARD_LEFT && Drive_Num != GO_FORWARD_RIGHT &&
      Drive_Num != GO_BACK_LEFT && Drive_Num != GO_BACK_RIGHT) return false;
  return isCheckRequested || millis() - lastCheckMs >= CHECK_INTERVAL_MS;
}

void mark_Checked() {          // 調べた時刻を記録する
  isCheckRequested = false;
  lastCheckMs = millis();
}

void update_ObstacleFlags() {  // front と back を更新する
  front = is_FrontBlocked() ? 1 : 0;
  back  = is_BackBlocked()  ? 1 : 0;
}

DriveState decide_AvoidAction() {   // 回避動作を決める（なければ DEF）
  if (front && back)                    return GO_RIGHT;     // 前後両方：回転
  if (front && (Drive_Num == GO_ADVANCE || Drive_Num == GO_FORWARD_LEFT || Drive_Num == GO_FORWARD_RIGHT))
    return GO_BACK;          // 前進系の方向で前方障害物：後退
  if (back && (Drive_Num == GO_BACK || Drive_Num == GO_BACK_LEFT || Drive_Num == GO_BACK_RIGHT))
    return GO_ADVANCE;       // 後退系の方向で後方障害物：前進
  return DEF;
}

void checkSensorsAndObstacles() {
  if (isAvoiding) { update_Avoid(); return; }
  if (isDancing) return;     // ダンス時は do_Dance_Tick が安全確認する
  if (!is_CheckTime()) return;
  mark_Checked();
  update_ObstacleFlags();
  DriveState action = decide_AvoidAction();
  if (action != DEF) start_Avoid(action);
}

// =====================================================
// ダンス：0ボタンで開始（方向はステップごとに変更）
// =====================================================
void stop_Dance() {
  isDancing = false;
  Drive_Num = GO_STOP;
  go_Stop();
}

DriveState dance_Action(uint8_t step) {
  switch (step) {
    case 0: return GO_LEFT;            // 左に回転
    case 1: return GO_RIGHT;           // 右に回転
    case 2: return GO_FORWARD_LEFT;    // 前進しながら左へ
    case 3: return GO_FORWARD_RIGHT;   // 前進しながら右へ
    case 4: return GO_STOP;            // 一拍休む
    case 5: return GO_BACK_LEFT;       // 後退しながら左へ
    case 6: return GO_BACK_RIGHT;      // 後退しながら右へ
    case 7: return GO_RIGHT;           // 右に回転
    default: return GO_STOP;           // 終了時は停止
  }
}

unsigned int dance_Duration(uint8_t step) {
  switch (step) {
    case 0: case 1: return 800;    // 左右旋回
    case 2: case 3: return 900;    // 前進カーブ
    case 4: return 450;            // 一拍休み
    case 5: case 6: return 850;    // 後退カーブ
    case 7: return 1000;           // 最後の旋回
    default: return 400;           // ループ間の停止
  }
}

void start_Dance() {
  if (isAvoiding) return;
  isDancing = true;
  danceStep = 0;
  danceStepStartMs = millis();
  lastDanceCheckMs = 0;       // 開始直後にセンサー判定
  lastDriveCmd = GO_STOP;
  pendingSongNum = 0;         // 未開始の音楽予約だけ解除
  Drive_Num = dance_Action(danceStep);
  // 最初のモーター出力はloop内でセンサーを確認した後に行う
}

void do_Dance_Tick() {
  if (!isDancing) return;
  unsigned long now = millis();

  // ダンス中は前後の安全確認を定期的に行い、障害物があれば直ちに中止
  if (lastDanceCheckMs == 0 || now - lastDanceCheckMs >= CHECK_INTERVAL_MS) {
    lastDanceCheckMs = now;
    if (is_FrontBlocked() || is_BackBlocked()) {
      stop_Dance();
      return;
    }
    now = millis();
  }

  // millis()に基づく非ブロッキングなステップ更新
  if (now - danceStepStartMs < dance_Duration(danceStep)) return;
  danceStep++;
  if (danceStep >= DANCE_STEPS) {
    danceStep = 0;               // 0に戻してOKまでダンスを繰り返す
  }
  danceStepStartMs = now;
  Drive_Num = dance_Action(danceStep);
}

// =====================================================
// 入力：リモコン入力受付（優先度3：ユーザーの指示）
// =====================================================
bool is_OppositeDrive(DriveState a, DriveState b) {
  return (a == GO_ADVANCE && b == GO_BACK) || (a == GO_BACK && b == GO_ADVANCE) ||
         (a == GO_LEFT && b == GO_RIGHT)   || (a == GO_RIGHT && b == GO_LEFT);
}

// 一方向（↑↓）と左右（←→）が短時間で続いた場合に斜め走行へ変更
DriveState get_DiagonalDrive(DriveState a, DriveState b) {
  if ((a == GO_ADVANCE && b == GO_LEFT) || (a == GO_LEFT && b == GO_ADVANCE))
    return GO_FORWARD_LEFT;
  if ((a == GO_ADVANCE && b == GO_RIGHT) || (a == GO_RIGHT && b == GO_ADVANCE))
    return GO_FORWARD_RIGHT;
  if ((a == GO_BACK && b == GO_LEFT) || (a == GO_LEFT && b == GO_BACK))
    return GO_BACK_LEFT;
  if ((a == GO_BACK && b == GO_RIGHT) || (a == GO_RIGHT && b == GO_BACK))
    return GO_BACK_RIGHT;
  return DEF;
}

void set_Drive(DriveState cmd) {
  unsigned long now = millis();
  bool withinWindow = lastDriveCmd != GO_STOP && (now - lastDriveCmdMs <= CONFLICT_MS);

  // 前後や左右の反対入力が0.3秒以内に続いた場合は従来どおり停止
  if (withinWindow && is_OppositeDrive(lastDriveCmd, cmd)) {
    Drive_Num = GO_STOP;
    lastDriveCmd = GO_STOP;
    lastDriveCmdMs = now;
    return;
  }

  // 斜め入力は到着順に依存しない（物理同時押しの専用IRコードには非対応）
  DriveState diagonal = withinWindow ? get_DiagonalDrive(lastDriveCmd, cmd) : DEF;
  Drive_Num = (diagonal != DEF) ? diagonal : cmd;
  lastDriveCmd = cmd;
  lastDriveCmdMs = now;
  isCheckRequested = true;
}

int read_IR_Command() {        // 受信コードを返す。受信なし・リピート信号は NO_COMMAND
  if (!IrReceiver.decode()) return NO_COMMAND;
  int command = IrReceiver.decodedIRData.command;
  bool isRepeat = IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT;
  IrReceiver.resume();
  return isRepeat ? NO_COMMAND : command;
}

void handle_StopButton() {     // OK：停止状態にする
  isAvoiding = false;
  isDancing = false;
  stop_Music();               // OKで走行と音楽を一緒に止める
  Drive_Num = GO_STOP;
  lastDriveCmd = GO_STOP;      // モーターは出力層 do_Drive_Tick が止める
}

void handle_DriveButton(int command) {    // ↑↓←→：走行の指示
  if      (command == IR_ADVANCE) set_Drive(GO_ADVANCE);
  else if (command == IR_BACK)    set_Drive(GO_BACK);
  else if (command == IR_LEFT)    set_Drive(GO_LEFT);
  else if (command == IR_RIGHT)   set_Drive(GO_RIGHT);
}

int get_SongNum(int command) {            // ボタンのコードから曲番号(1〜9)を返す。数字ボタンでなければ0
  for (int i = 0; i < SONG_COUNT; i++) {
    if (command == NUM_CODES[i]) return i + 1;
  }
  return 0;
}

bool is_NumberConflict(int songNum) {     // 依頼中の曲と別の数字か（同時押し）
  return pendingSongNum != 0 && pendingSongNum != songNum &&
         millis() - pendingSongMs < CONFLICT_MS;
}

void handle_NumberButton(int command) {   // 1〜9：曲を依頼する（0.3秒待ってから再生）
  int songNum = get_SongNum(command);
  if (songNum == 0) return;
  if (is_NumberConflict(songNum)) { pendingSongNum = 0; return; }   // 同時押し：どの曲も鳴らさない
  if (pendingSongNum == songNum && millis() - pendingSongMs < CONFLICT_MS) return;                            // 同じ数字は1回だけ
  pendingSongNum = songNum;
  pendingSongMs = millis();
}

void do_IR_Tick() {            // リモコン入力の受付
  int command = read_IR_Command();
  if (command == NO_COMMAND) return;
  if (command == IR_STOP) { handle_StopButton(); return; }
  if (isAvoiding) return;
  if (command == IR_DANCE) { start_Dance(); return; }
  if (isDancing) return;      // ダンス中はOKと0のみを受け付ける
  handle_DriveButton(command);
  handle_NumberButton(command);
}

// =====================================================
// 初期設定とメインループ
// =====================================================
void init_MotorPins() {
  pinMode(SPEED_PIN_R, OUTPUT);  pinMode(RIGHT_DIR_PIN1, OUTPUT);  pinMode(RIGHT_DIR_PIN2, OUTPUT);
  pinMode(SPEED_PIN_L, OUTPUT);  pinMode(LEFT_DIR_PIN1, OUTPUT);   pinMode(LEFT_DIR_PIN2, OUTPUT);
  go_Stop();                   // 電源投入直後は必ず停止から始める
}

void init_BuzzerPin() {
  digitalWrite(BUZZ_PIN, HIGH);   // 出力へ切り替える前に停止値を用意
  pinMode(BUZZ_PIN, OUTPUT);
  digitalWrite(BUZZ_PIN, HIGH);   // ブザー停止（LOWで鳴るため）
}

void init_SensorPins() {
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BACK_IR_L_PIN, INPUT);
  pinMode(BACK_IR_R_PIN, INPUT);
}

void init_IrReceiver() {       // D13をブザーに使うため、受信時のLED点滅は無効にする
  IrReceiver.begin(IR_RECEIVE_PIN, DISABLE_LED_FEEDBACK);
}

void setup() {
  init_MotorPins();
  init_BuzzerPin();
  init_SensorPins();
  init_IrReceiver();
}

void loop() {
  do_IR_Tick();                 // ① 入力：リモコンの入力受付
  do_Dance_Tick();             // ダンス中は時間と障害物を確認
  checkSensorsAndObstacles();   // ② 判断：センサーの優先度判断（必要なら状態を上書き）
  do_Drive_Tick();              // ③ 出力：状態に基づいてモーターを実行
  do_Music_Tick();              // ④ 出力：走行を止めず音楽・警告音を更新

  if (IS_IR) delayMicroseconds(100);
  else       delayMicroseconds(20);
}
