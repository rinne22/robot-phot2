// 後方赤外線センサー単独診断：Arduino Uno、左OUT=A0、右OUT=D2。
// モーターを動かさず、USBシリアルモニタ115200bpsで左右を確認する。
// 検知LEDとraw値を照合し、検知時HIGHの機種はACTIVE_LEVELをHIGHへ。
#define BACK_IR_L_PIN A0
#define BACK_IR_R_PIN 2
#define BACK_IR_L_ACTIVE_LEVEL LOW
#define BACK_IR_R_ACTIVE_LEVEL LOW
const uint8_t MOTOR_PINS[] = {9, 12, 11, 6, 7, 8};
unsigned long lastReportMs = 0;

void setup() {
  for (uint8_t pin : MOTOR_PINS) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  digitalWrite(13, HIGH);
  pinMode(13, OUTPUT);
  pinMode(BACK_IR_L_PIN, INPUT_PULLUP);
  pinMode(BACK_IR_R_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.println(F("Rear IR diagnostic: left=A0, right=D2, motors OFF"));
  Serial.println(F("No object: default raw=1. Object: default raw=0."));
}

void loop() {
  unsigned long now = millis();
  if (now - lastReportMs < 200) return;
  lastReportMs = now;
  int left = digitalRead(BACK_IR_L_PIN);
  int right = digitalRead(BACK_IR_R_PIN);
  Serial.print(F("L raw=")); Serial.print(left);
  Serial.print(F(" detected=")); Serial.print(left == BACK_IR_L_ACTIVE_LEVEL);
  Serial.print(F(" | R raw=")); Serial.print(right);
  Serial.print(F(" detected=")); Serial.println(right == BACK_IR_R_ACTIVE_LEVEL);
}
