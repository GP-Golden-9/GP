// ═══════════════════════════════════════════════════════════════════════
//  ROBOT 3 "GAMMA" — DECISIVE DIAGNOSTIC
//  ─────────────────────────────────────────────────────────────────────
//  Drives the motors FORWARD continuously, forever, with NO commands and
//  NO watchdog — exactly like the working motor-test — BUT it also runs the
//  full WiFi + web server + sensor reads that the dashboard firmware runs.
//
//  This isolates the cause:
//   • If the motor VIBRATES here  -> WiFi/sensor activity is electrically
//        disturbing the motor (power/decoupling/wiring) — NOT the command
//        logic. Fix = isolate ESP power (separate 5 V) / 3.3 V cap.
//   • If the motor is SMOOTH here -> the problem is the command/watchdog
//        path in the dashboard firmware, and I'll fix that in software.
//
//  Board: ESP32 Dev Module. Serial @ 115200.
// ═══════════════════════════════════════════════════════════════════════

#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

const char* WIFI_SSID     = "Sonnet";
const char* WIFI_PASSWORD = "Eng_Matouk_HelloSonnet";

#define ENA 13
#define IN1 32
#define IN2 33
#define ENB 25
#define IN3 27
#define IN4 26
#define TRIG_PIN 18
#define ECHO_PIN 5
#define GAS_PIN 34
#define BUZZER_PIN 15

IPAddress STATIC_IP(192, 168, 1, 202);
IPAddress GATEWAY  (192, 168, 1, 1);
IPAddress SUBNET   (255, 255, 255, 0);
IPAddress DNS1     (192, 168, 1, 1);

WebServer server(80);
Adafruit_MPU6050 mpu;
bool mpu_ok = false;
float dist_cm = 0; int gas_val = 0; float ax = 0, ay = 0;
unsigned long lastSensor = 0, bootMillis = 0;

void driveForward() {                 // forced, never stops
  digitalWrite(ENA, HIGH); digitalWrite(ENB, HIGH);
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  bootMillis = millis();

  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);

  driveForward();                     // START DRIVING IMMEDIATELY

  Wire.begin(21, 22);
  mpu_ok = mpu.begin();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_2dBm);
  WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS1);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) {
    delay(500); driveForward();       // keep driving while connecting
  }
  Serial.print("WiFi: "); Serial.println(WiFi.localIP());

  server.on("/", []() { server.send(200, "text/plain", "DIAG: driving forward"); });
  server.on("/telemetry", []() {
    String j = "{\"d\":" + String(dist_cm, 1) + ",\"g\":" + String(gas_val) +
               ",\"x\":" + String(ax, 2) + ",\"y\":" + String(ay, 2) +
               ",\"a\":0,\"rssi\":" + String(WiFi.RSSI()) +
               ",\"uptime\":" + String((millis() - bootMillis) / 1000) +
               ",\"last_cmd_age\":0}";
    server.send(200, "application/json", j);
  });
  server.begin();
  Serial.println("DIAG ready — motor should run forward NON-STOP");
}

void loop() {
  driveForward();                     // re-assert every loop, never stop

  if (WiFi.status() == WL_CONNECTED) server.handleClient();

  if (millis() - lastSensor > 250) {
    lastSensor = millis();
    digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    long us = pulseIn(ECHO_PIN, HIGH, 8000);
    dist_cm = (us > 0) ? us * 0.034 / 2.0 : 0;
    gas_val = analogRead(GAS_PIN);
    if (mpu_ok) {
      sensors_event_t a, g, t; mpu.getEvent(&a, &g, &t);
      ax = a.acceleration.x; ay = a.acceleration.y;
    }
  }
}
