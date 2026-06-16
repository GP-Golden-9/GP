// ═══════════════════════════════════════════════════════════════════════
//  ROBOT 3 "GAMMA" — flash-ready sketch (drive + dashboard + gas + sonar)
//  ─────────────────────────────────────────────────────────────────────
//  Self-contained: WiFi credentials are inline below (edit them once).
//  Speaks the SAME HTTP API the GP Fleet Console expects (config/robot3.yaml):
//    GET /control?dir=F|B|L|R|S   → drive
//    GET /telemetry               → {d,g,x,y,a,rssi,uptime,last_cmd_age}
//  Also serves a phone-friendly control page at  http://<ip>/  and
//  advertises  robot3.local  over mDNS. The board PRINTS ITS IP on serial.
//
//  Board (Arduino IDE): "ESP32 Dev Module" / DOIT ESP32 DEVKIT V1
//  Libraries: Adafruit MPU6050 (+ Adafruit Unified Sensor). WiFi/WebServer/
//             ESPmDNS/Wire ship with the ESP32 core.
//  Onboard USB-serial is dead on this unit → flash via FT232RL
//  (see docs/robot3_flashing.md); unplug the ULTRASONIC (G5) while flashing —
//  it sits on a strapping pin. (Buzzer is on G27 now, not a strapping pin.)
// ═══════════════════════════════════════════════════════════════════════

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "soc/soc.h"             // brownout-detector register
#include "soc/rtc_cntl_reg.h"

// ── EDIT THESE: your 2.4 GHz network (ESP32 has NO 5 GHz radio) ──────────
const char* WIFI_SSID     = "Sonnet";
const char* WIFI_PASSWORD = "Eng_Matouk_HelloSonnet";
#define HOSTNAME "robot3"          // → robot3.local

// ── Static IP — the dashboard always finds Gamma at one fixed address ───
// Must be on the router's subnet (gateway 192.168.1.1) and OUTSIDE its DHCP
// pool to avoid a clash. .202 is free (Alpha .200, Beta .203).
IPAddress STATIC_IP(192, 168, 1, 202);
IPAddress GATEWAY  (192, 168, 1, 1);
IPAddress SUBNET   (255, 255, 255, 0);
IPAddress DNS1     (192, 168, 1, 1);

// ── Pins ────────────────────────────────────────────────────────────────
// MOTORS ARE NOW ON THE ARDUINO (immune to ESP WiFi rail-sag). The ESP just
// sends F/B/L/R/S to the Arduino over Serial2 (TX=GPIO17 -> Arduino D10).
#define ARDUINO_TX 17   // ESP Serial2 TX -> Arduino SoftwareSerial RX (D10)
#define TRIG_PIN 18     // HC-SR04 trigger
#define ECHO_PIN 5      // HC-SR04 echo  (via 1k/2k divider → 3.3 V)
#define GAS_PIN 34      // MQ-5 AO       (via 1k/2k divider → 3.3 V, ADC in)
#define BUZZER_PIN 27   // active buzzer (via NPN transistor); G27 free now
                        // that motors moved to the Arduino — and not a
                        // strapping pin, so it won't disturb flashing

// ── Tuning ──────────────────────────────────────────────────────────────
#define DRIVE_SPEED          230      // 0..255 PWM duty
#define CMD_WATCHDOG_MS      1800UL   // stop motors if no /control this long
                                      // (raised from 800 so brief WiFi gaps
                                      // don't chop the motor into a twitch)
#define SENSOR_PERIOD_MS     250UL    // sensor + telemetry refresh
#define WIFI_RETRY_MS        5000UL
#define GAS_ALARM_THRESHOLD  3000     // raw ADC: gas present  (matches config)
#define GAS_CLEAR_THRESHOLD  2000     // raw ADC: hysteresis clear point
#define GAS_ALARM_MIN_MS     10000UL  // alarm latches at least this long

WebServer server(80);
Adafruit_MPU6050 mpu;

float dist_cm = 0;
int   gas_val = 0;
float ax = 0, ay = 0;
bool  mpu_ok = false;

char  currentDir = 'S';
unsigned long lastCmdTime = 0, lastSensor = 0, lastWifiAttempt = 0, bootMillis = 0;
bool  alarmActive = false;
unsigned long alarmSince = 0;

// ── Motor commands → Arduino over Serial2 ───────────────────────────────
// The ESP never touches the L298N now; it just sends a direction char and
// the Arduino (separate 5 V chip) drives the motors — immune to WiFi sag.
void sendDir(char d) { Serial2.write(d); }

void setDirection(char d) {
  if (d != 'F' && d != 'B' && d != 'L' && d != 'R') d = 'S';
  currentDir = d;
  lastCmdTime = millis();
  sendDir(d);
}

void chirp(int n, int ms) {
  for (int i = 0; i < n; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(ms);
    digitalWrite(BUZZER_PIN, LOW);  delay(ms);
  }
}

// ── Phone control page (hold-to-drive, auto-stop via watchdog) ──────────
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html><head><title>Gamma</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:sans-serif;background:#121212;color:#eee;text-align:center}
 .card{background:#1e1e1e;padding:16px;border-radius:12px;margin:12px auto;max-width:340px;border:1px solid #333}
 .v{font-size:26px;color:#00ffcc;font-weight:bold}
 .alarm{color:#ff3e3e;font-weight:bold}
 .btn{background:#007bff;border:0;color:#fff;padding:16px;font-size:18px;border-radius:10px;margin:6px;width:100px}
 .stop{background:#dc3545}
</style></head><body>
<h2>GAMMA INSPECTOR</h2>
<div class="card">
 <p>Distance: <span id="d" class="v">0</span> cm</p>
 <p>Gas: <span id="g" class="v">0</span> <span id="w"></span></p>
 <p style="font-size:12px;color:#888">RSSI <span id="r">?</span> dBm · up <span id="u">?</span> s</p>
</div>
<div class="card">
 <button class="btn" onmousedown="c('F')" onmouseup="c('S')" ontouchstart="c('F')" ontouchend="c('S')">UP</button><br>
 <button class="btn" onmousedown="c('L')" onmouseup="c('S')" ontouchstart="c('L')" ontouchend="c('S')">LEFT</button>
 <button class="btn stop" onclick="c('S')">STOP</button>
 <button class="btn" onmousedown="c('R')" onmouseup="c('S')" ontouchstart="c('R')" ontouchend="c('S')">RIGHT</button><br>
 <button class="btn" onmousedown="c('B')" onmouseup="c('S')" ontouchstart="c('B')" ontouchend="c('S')">DOWN</button>
</div>
<script>
 let held=null;
 setInterval(()=>{fetch('/telemetry').then(r=>r.json()).then(t=>{
   d.innerText=t.d; g.innerText=t.g; r2.innerText=t.rssi; u.innerText=t.uptime;
   w.innerText=t.a?' (DANGER!)':' (OK)'; w.className=t.a?'alarm':'';
 }).catch(()=>{}); if(held) fetch('/control?dir='+held).catch(()=>{});},400);
 function c(dir){held=(dir==='S')?null:dir; fetch('/control?dir='+dir).catch(()=>{});}
 var r2=document.getElementById('r');
</script></body></html>
)rawliteral";

// ── WiFi ────────────────────────────────────────────────────────────────
void wifiConnectBlocking() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  // Kill modem-sleep: its periodic wake bursts sag the 3.3 V rail ~10x/s,
  // which droops the motor-enable GPIOs and makes the motors vibrate.
  // Keeping the radio steady removes those current spikes.
  WiFi.setSleep(false);
  // FULL TX power → reliable command delivery. (The old min-power setting
  // was to fight motor-pin sag, but motors are on the Arduino now, so that
  // sag is gone — weak TX only dropped command packets and made the ESP
  // watchdog flip to 'S', which is what caused the S/F vibration.)
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  if (!WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS1))   // static IP .202
    Serial.println("WARN: static IP config failed");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500); Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi UP — IP address: ");
    Serial.println(WiFi.localIP());        // ← the IP for the dashboard
    if (MDNS.begin(HOSTNAME))
      Serial.println("mDNS: " HOSTNAME ".local");
  } else {
    Serial.println("\nWiFi FAILED — retrying in loop()");
  }
}

// ── Setup ───────────────────────────────────────────────────────────────
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);   // ride through motor-inrush dips
  Serial.begin(115200);
  bootMillis = millis();

  Serial2.begin(1200, SERIAL_8N1, 16, ARDUINO_TX);  // link to Arduino (TX=17)
  // 1200 baud on purpose: long bit time is very tolerant of the ESP's 3.3 V
  // signal driving the Arduino's 5 V SoftwareSerial input. Command chars are
  // tiny, so speed doesn't matter — reliability does.
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
  sendDir('S');
  chirp(2, 150);                        // boot beep

  Wire.begin(21, 22);                   // I2C: SDA 21, SCL 22
  mpu_ok = mpu.begin();
  Serial.println(mpu_ok ? "MPU6050 OK" : "MPU6050 not found (continuing)");

  wifiConnectBlocking();

  server.on("/", []() { server.send_P(200, "text/html", INDEX_HTML); });

  // Telemetry — keys must match config/robot3.yaml / the dashboard parser
  server.on("/telemetry", []() {
    String j = "{\"d\":" + String(dist_cm, 1) +
               ",\"g\":" + String(gas_val) +
               ",\"x\":" + String(ax, 2) +
               ",\"y\":" + String(ay, 2) +
               ",\"a\":" + String(alarmActive ? 1 : 0) +
               ",\"rssi\":" + String(WiFi.RSSI()) +
               ",\"uptime\":" + String((millis() - bootMillis) / 1000) +
               ",\"last_cmd_age\":" + String(millis() - lastCmdTime) + "}";
    server.send(200, "application/json", j);
  });

  server.on("/control", []() {
    String d = server.arg("dir");
    setDirection(d.length() ? d[0] : 'S');
    server.send(200, "text/plain", "OK");
  });

  server.begin();
  Serial.println("Gamma ready");
}

// ── Loop ────────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. WiFi self-heal — but DO NOT stop the motor on a brief blip. Motor
  // noise can flap WiFi.status() for a moment; stopping here is what made
  // the car twitch (stop->reconnect->command->run->blip->stop...). The
  // command watchdog below is the single, debounced motor-stop authority.
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastWifiAttempt > WIFI_RETRY_MS) {
      lastWifiAttempt = now;
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  } else {
    server.handleClient();
  }

  // 2. Command watchdog + keepalive to the Arduino.
  if (currentDir != 'S' && now - lastCmdTime > CMD_WATCHDOG_MS) {
    currentDir = 'S'; sendDir('S');
  }
  // Re-send the held direction every 200 ms so the Arduino's own watchdog
  // stays fed even between dashboard/phone command keepalives.
  static unsigned long lastRelay = 0;
  if (now - lastRelay > 200) { lastRelay = now; sendDir(currentDir); }

  // 3. Sensors + latched gas alarm
  if (now - lastSensor > SENSOR_PERIOD_MS) {
    lastSensor = now;

    // Ultrasonic distance
    digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    // 8 ms timeout (~1.3 m). Short on purpose: if the sensor is UNPLUGGED,
    // ECHO never goes HIGH and pulseIn blocks for the FULL timeout every
    // cycle, stalling the web server / command loop. Keep it small.
    long us = pulseIn(ECHO_PIN, HIGH, 8000);
    dist_cm = (us > 0) ? us * 0.034 / 2.0 : 0;  // 0 = nothing in range / unplugged

    // Gas — latched alarm with hysteresis
    gas_val = analogRead(GAS_PIN);
    if (gas_val > GAS_ALARM_THRESHOLD) {
      alarmActive = true; alarmSince = now;
    } else if (alarmActive && now - alarmSince > GAS_ALARM_MIN_MS
                            && gas_val < GAS_CLEAR_THRESHOLD) {
      alarmActive = false;
    }
    digitalWrite(BUZZER_PIN, (alarmActive && (now / 250) % 2) ? HIGH : LOW);

    // IMU tilt (optional — telemetry x/y)
    if (mpu_ok) {
      sensors_event_t a, g, t;
      mpu.getEvent(&a, &g, &t);
      ax = a.acceleration.x; ay = a.acceleration.y;
    }
  }
}
