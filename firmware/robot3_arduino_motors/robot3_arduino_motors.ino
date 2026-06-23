// ═══════════════════════════════════════════════════════════════════════
//  ROBOT 3 "GAMMA" — ARDUINO MOTOR DRIVER
//  ─────────────────────────────────────────────────────────────────────
//  The Arduino drives the L298N. It receives a single direction character
//  (F/B/L/R/S) from the ESP32 over a serial wire and moves the motors.
//
//  WHY: the ESP32's WiFi transmit spikes were sagging its 3.3 V rail and
//  drooping the motor-enable GPIOs (the vibration). The Arduino is a
//  separate 5 V chip with no WiFi, so its outputs never droop — motors run
//  smooth. This mirrors how Alpha/Beta work (Pi = WiFi, Mega = motors).
//
//  Board: Arduino Uno/Nano.  Enables are PWM'd (analogWrite) for SPEED control;
//  a digit '0'..'9' from the ESP sets the duty. (2026-06-23: ENA moved D8->D6.)
// ═══════════════════════════════════════════════════════════════════════

#include <SoftwareSerial.h>

// Link from the ESP32: ESP GPIO17 (Serial2 TX) -> Arduino D10 (RX here).
// D11 (TX) is unused. Using SoftwareSerial keeps USB (D0/D1) free for the
// Serial Monitor and for uploading without unplugging the ESP wire.
SoftwareSerial espLink(10, 11);     // RX, TX

// L298N control pins. The ENABLES are PWM'd for SPEED control, so both must be
// on PWM pins. ENA MOVED D8 -> D6 (D8 is not a PWM pin on the Uno/Nano; D10/D11
// are taken by the SoftwareSerial link, leaving D6 as the only free PWM pin).
//   >>> REWIRE: move the L298N ENA wire from Arduino D8 to D6 <<<
#define ENA 6        // PWM (was 8)
#define IN1 2
#define IN2 3
#define ENB 9        // PWM
#define IN3 4
#define IN4 5

// Motor speed (PWM duty 0..255). Set by a single digit '0'..'9' from the ESP
// (which relays the console's speed slider). Starts mid so it isn't flat-out.
int spd = 150;

#define WATCHDOG_MS 1500UL          // stop if no char from ESP for this long
                                    // (wider so a single missed char on the
                                    // 3.3 V link doesn't chop the motor)

char dir = 'S';
unsigned long lastCmd = 0;
int sCount = 0;   // consecutive 'S' chars — debounces a garbled 'S' on the link

void apply(int en, int i1, int i2, int i3, int i4) {
  analogWrite(ENA, en ? spd : 0);   // PWM the enables → speed control
  analogWrite(ENB, en ? spd : 0);
  digitalWrite(IN1, i1); digitalWrite(IN2, i2);
  digitalWrite(IN3, i3); digitalWrite(IN4, i4);
}
void mstop() { apply(LOW, LOW, LOW, LOW, LOW); }

void setDir(char d) {
  lastCmd = millis();
  if (d != dir) { Serial.print("RX dir="); Serial.println(d); }  // link debug
  dir = d;
  switch (d) {
    case 'F': apply(HIGH, HIGH, LOW, HIGH, LOW); break;  // forward
    case 'B': apply(HIGH, LOW, HIGH, LOW, HIGH); break;  // backward
    case 'L': apply(HIGH, LOW, HIGH, HIGH, LOW); break;  // left
    case 'R': apply(HIGH, HIGH, LOW, LOW, HIGH); break;  // right
    default:  dir = 'S'; mstop(); break;                 // stop
  }
}

void setup() {
  Serial.begin(115200);
  espLink.begin(1200);             // must match the ESP's Serial2 baud
                                   // 1200 = very tolerant of the 3.3V link
  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  mstop();
  Serial.println("Arduino motor driver ready (waiting for ESP chars)");
}

void loop() {
  while (espLink.available()) {
    char c = espLink.read();
    if (c >= '0' && c <= '9') {               // speed level 0..9 → PWM 90..255
      spd = map(c - '0', 0, 9, 90, 255);
      lastCmd = millis();
      if (dir != 'S') setDir(dir);            // re-apply current dir at new speed
    } else if (c == 'F' || c == 'B' || c == 'L' || c == 'R') {
      lastCmd = millis(); sCount = 0;        // movement: act immediately
      if (c != dir) setDir(c);
    } else if (c == 'S') {
      lastCmd = millis();
      if (++sCount >= 3 && dir != 'S') setDir('S');  // stop only on 3 'S' in a row
    }
  }
  // Safety: if the ESP stops talking entirely (link/power lost), stop.
  if (dir != 'S' && millis() - lastCmd > WATCHDOG_MS) { mstop(); dir = 'S'; }
}
