// ═══════════════════════════════════════════════════════════════════════
//  ROBOT 3 "GAMMA" — MOTOR TEST sketch (diagnostic only)
//  ─────────────────────────────────────────────────────────────────────
//  Purpose: prove the ESP32 GPIOs + L298N + motors work, with NO dashboard
//  and NO HTTP command path involved. It AUTO-CYCLES the four directions
//  on a loop and prints each phase + the expected pin states to Serial, so
//  you can (a) watch the motors move and (b) measure each ESP pin.
//
//  Enables (ENA/ENB) are driven with digitalWrite(HIGH) = FULL SPEED, so
//  this test does NOT depend on analogWrite/PWM. If motors move here but
//  not in the main firmware, the issue is analogWrite on your core (fix =
//  switch ENA/ENB to ledcWrite in the main sketch).
//
//  Board: "ESP32 Dev Module".  Open Serial Monitor @ 115200.
//  Power the ESP from a solid 5 V (not the USB-TTL regulator); L298N VS
//  from the LiPo; ALL grounds common.
// ═══════════════════════════════════════════════════════════════════════

#include <WiFi.h>

// ── WiFi (so the board still gets an IP; not needed for the motor test) ──
const char* WIFI_SSID     = "Sonnet";
const char* WIFI_PASSWORD = "Eng_Matouk_HelloSonnet";

// ── Motor pins (your wiring) ────────────────────────────────────────────
#define ENA 13   // left  enable  (full speed via digitalWrite here)
#define IN1 32   // left  dir
#define IN2 33
#define ENB 25   // right enable
#define IN3 27   // right dir
#define IN4 26

#define PHASE_MS 2500   // drive each direction this long
#define STOP_MS  1500   // pause between directions

void pins(int en_a, int i1, int i2, int en_b, int i3, int i4) {
  digitalWrite(ENA, en_a); digitalWrite(ENB, en_b);
  digitalWrite(IN1, i1); digitalWrite(IN2, i2);
  digitalWrite(IN3, i3); digitalWrite(IN4, i4);
}

void announce(const char* name, const char* expect) {
  Serial.println();
  Serial.print(">>> "); Serial.println(name);
  Serial.println(expect);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== GAMMA MOTOR TEST ===");

  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pins(LOW, LOW, LOW, LOW, LOW, LOW);     // all off

  // WiFi is optional for the test — try briefly, then run regardless.
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
    delay(500); Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nWiFi UP — IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi not connected (motor test still runs)");
  }
  Serial.println("Starting auto-cycle: FORWARD > BACK > LEFT > RIGHT ...");
}

void loop() {
  // FORWARD — both sides forward
  announce("FORWARD",
    "ENA(G13)=H ENB(G25)=H | IN1(G32)=H IN2(G33)=L | IN3(G27)=H IN4(G26)=L");
  pins(HIGH, HIGH, LOW, HIGH, HIGH, LOW);
  delay(PHASE_MS);

  announce("STOP", "all pins LOW");
  pins(LOW, LOW, LOW, LOW, LOW, LOW);
  delay(STOP_MS);

  // BACKWARD
  announce("BACKWARD",
    "ENA(G13)=H ENB(G25)=H | IN1(G32)=L IN2(G33)=H | IN3(G27)=L IN4(G26)=H");
  pins(HIGH, LOW, HIGH, HIGH, LOW, HIGH);
  delay(PHASE_MS);

  announce("STOP", "all pins LOW");
  pins(LOW, LOW, LOW, LOW, LOW, LOW);
  delay(STOP_MS);

  // LEFT — left side back, right side forward
  announce("LEFT",
    "ENA(G13)=H ENB(G25)=H | IN1(G32)=L IN2(G33)=H | IN3(G27)=H IN4(G26)=L");
  pins(HIGH, LOW, HIGH, HIGH, HIGH, LOW);
  delay(PHASE_MS);

  announce("STOP", "all pins LOW");
  pins(LOW, LOW, LOW, LOW, LOW, LOW);
  delay(STOP_MS);

  // RIGHT — left side forward, right side back
  announce("RIGHT",
    "ENA(G13)=H ENB(G25)=H | IN1(G32)=H IN2(G33)=L | IN3(G27)=L IN4(G26)=H");
  pins(HIGH, HIGH, LOW, HIGH, LOW, HIGH);
  delay(PHASE_MS);

  announce("STOP", "all pins LOW");
  pins(LOW, LOW, LOW, LOW, LOW, LOW);
  delay(STOP_MS);
}
