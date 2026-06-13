// ═══════════════════════════════════════════════════════════════════════
//  ROBOT 3 "GAMMA" — INSPECTOR NODE  v2.0  (ESP32)
//  ─────────────────────────────────────────────────────────────────────
//  v2 fixes the field-safety gaps of v1:
//    · COMMAND WATCHDOG: motors stop 800 ms after the last /control hit —
//      v1 drove until impact if WiFi dropped mid-command
//    · WiFi RECONNECT: drops are detected, motors stop, the link rejoins
//      automatically (v1 never re-checked WiFi.status())
//    · mDNS: advertises robot3.local (the dashboard's configured hostname)
//    · GAS ALARM LATCH: alarm holds ≥10 s with hysteresis — a single dip
//      below threshold no longer silences a real leak; buzzer pulses
//    · /telemetry adds rssi, uptime, last_cmd_age for the health panel
//    · WiFi credentials moved to config_secrets.h (gitignored; template
//      committed) — they were hardcoded in the repo
//    · SERVO added (2026-06-13): one slew-limited servo on GPIO19 with a
//      /servo?deg= endpoint, telemetry field, and a web-UI slider. Mount
//      the ultrasonic on it for a scanning sonar, or use as a pointer/arm.
//  Hardware: 4 motors (two L298N channels, pairs), 1 ultrasonic, 1 servo,
//  MQ gas sensor, MPU6050 IMU. NO wheel encoders (heading is IMU-only).
//  Motor/sensor pins unchanged from v1 (verified working on the build).
// ═══════════════════════════════════════════════════════════════════════

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <ESP32Servo.h>          // Library Manager: "ESP32Servo" by K. Harrington

#include "config_secrets.h"   // WIFI_SSID / WIFI_PASSWORD — see .template

#ifndef OTA_PASSWORD
#define OTA_PASSWORD "gp-inspector"   // override in config_secrets.h
#endif

// ── Pins (verified working, unchanged from v1) ──────────────────────────
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
// Servo signal pin. GPIO19 is free, output-capable, and NOT a strapping
// pin (unlike 0/2/5/12/15) so it can't disturb the FTDI flash sequence.
#define SERVO_PIN 19

// ── Tuning ──────────────────────────────────────────────────────────────
#define DRIVE_SPEED          230
#define CMD_WATCHDOG_MS      800UL    // stop if no /control for this long
#define SENSOR_PERIOD_MS     250UL
#define WIFI_RETRY_MS        5000UL
#define GAS_ALARM_THRESHOLD  3000     // raw ADC — field-tuned value from v1
#define GAS_CLEAR_THRESHOLD  2000     // hysteresis: must drop below to clear
#define GAS_ALARM_MIN_MS     10000UL  // alarm latches at least this long
#define HOSTNAME             "robot3"

// Servo: clamp to a safe arc, home centered, and SLEW toward the target a
// few degrees at a time instead of snapping — a full-swing jump is a
// current spike, and this build has a brownout history.
#define SERVO_MIN_DEG        0
#define SERVO_MAX_DEG        180
#define SERVO_HOME_DEG       90
#define SERVO_SLEW_MS        20       // step interval
#define SERVO_STEP_DEG       3        // ~150 deg/s — smooth, low inrush

WebServer server(80);
Adafruit_MPU6050 mpu;
Servo armServo;

float dist_cm = 0;
int   gas_val = 0;
float ax = 0, ay = 0;
bool  mpu_ok = false;

int   servo_deg = SERVO_HOME_DEG;     // current (slewed) angle
int   servo_target = SERVO_HOME_DEG;  // commanded angle
unsigned long lastServoMove = 0;

char  currentDir = 'S';
unsigned long lastCmdTime = 0;
unsigned long lastSensor = 0;
unsigned long lastWifiAttempt = 0;
unsigned long bootMillis = 0;

bool  alarmActive = false;
unsigned long alarmSince = 0;

// ── Motors ──────────────────────────────────────────────────────────────
void applyDrive(int l1, int l2, int r1, int r2, int spd) {
  analogWrite(ENA, spd); analogWrite(ENB, spd);
  digitalWrite(IN1, l1); digitalWrite(IN2, l2);
  digitalWrite(IN3, r1); digitalWrite(IN4, r2);
}

void motorStop()  { applyDrive(LOW, LOW, LOW, LOW, 0); }
void forward()    { applyDrive(HIGH, LOW, HIGH, LOW, DRIVE_SPEED); }
void backward()   { applyDrive(LOW, HIGH, LOW, HIGH, DRIVE_SPEED); }
void leftTurn()   { applyDrive(LOW, HIGH, HIGH, LOW, DRIVE_SPEED); }
void rightTurn()  { applyDrive(HIGH, LOW, LOW, HIGH, DRIVE_SPEED); }

void setDirection(char d) {
  currentDir = d;
  lastCmdTime = millis();
  switch (d) {
    case 'F': forward();   break;
    case 'B': backward();  break;
    case 'L': leftTurn();  break;
    case 'R': rightTurn(); break;
    default:  currentDir = 'S'; motorStop(); break;
  }
}

void chirp(int n, int ms) {
  for (int i = 0; i < n; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(ms);
    digitalWrite(BUZZER_PIN, LOW);  delay(ms);
  }
}

// ── Web UI (v1 layout, watchdog-aware hold-to-drive already in the JS) ──
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <title>Inspector Node v2</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #eee; text-align: center; }
    .status-card { background: #1e1e1e; padding: 20px; border-radius: 15px; margin: 15px auto; width: 85%; max-width: 350px; border: 1px solid #333; }
    .val { font-size: 28px; color: #00ffcc; font-weight: bold; }
    .alarm { color: #ff3e3e; font-weight: bold; animation: blink 1s infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .btn { background: #007bff; border: none; color: #fff; padding: 18px; font-size: 20px; border-radius: 12px; margin: 8px; width: 110px; cursor: pointer; }
    .btn:active { background: #0056b3; transform: scale(0.95); }
    .stop-btn { background: #dc3545; width: 130px; }
  </style>
</head>
<body>
  <h1>🛰️ INSPECTOR NODE V2</h1>
  <div class="status-card">
    <p>Ultrasonic: <span id="dist" class="val">0</span> cm</p>
    <p>Gas Level: <span id="gas" class="val">0</span> <span id="warn"></span></p>
    <p>Tilt X: <span id="tx">0</span> | Y: <span id="ty">0</span></p>
    <p style="font-size:12px;color:#888">RSSI <span id="rssi">?</span> dBm ·
       up <span id="up">?</span> s · hold buttons to drive (auto-stop 0.8 s)</p>
  </div>
  <div class="status-card">
    <button class="btn" onmousedown="cmd('F')" onmouseup="cmd('S')" ontouchstart="cmd('F')" ontouchend="cmd('S')">UP</button><br>
    <button class="btn" onmousedown="cmd('L')" onmouseup="cmd('S')" ontouchstart="cmd('L')" ontouchend="cmd('S')">LEFT</button>
    <button class="btn stop-btn" onclick="cmd('S')">STOP</button>
    <button class="btn" onmousedown="cmd('R')" onmouseup="cmd('S')" ontouchstart="cmd('R')" ontouchend="cmd('S')">RIGHT</button><br>
    <button class="btn" onmousedown="cmd('B')" onmouseup="cmd('S')" ontouchstart="cmd('B')" ontouchend="cmd('S')">DOWN</button>
  </div>
  <div class="status-card">
    <p>Servo: <span id="sv" class="val">90</span>&deg;</p>
    <input type="range" min="0" max="180" value="90" style="width:90%"
           oninput="document.getElementById('sv').innerText=this.value"
           onchange="servo(this.value)">
  </div>
  <script>
    let held = null;
    setInterval(() => {
      fetch('/telemetry').then(r => r.json()).then(data => {
        document.getElementById('dist').innerText = data.d;
        document.getElementById('gas').innerText = data.g;
        document.getElementById('tx').innerText = data.x;
        document.getElementById('ty').innerText = data.y;
        document.getElementById('rssi').innerText = data.rssi;
        document.getElementById('up').innerText = data.uptime;
        document.getElementById('warn').innerText = data.a ? " (DANGER!)" : " (OK)";
        document.getElementById('warn').className = data.a ? "alarm" : "";
      }).catch(()=>{});
      if (held) fetch('/control?dir=' + held).catch(()=>{});   // keepalive
    }, 400);
    function cmd(dir) {
      held = (dir === 'S') ? null : dir;
      fetch('/control?dir=' + dir).catch(()=>{});
    }
    function servo(deg) { fetch('/servo?deg=' + deg).catch(()=>{}); }
  </script>
</body>
</html>
)rawliteral";

// ── WiFi ────────────────────────────────────────────────────────────────
void wifiConnectBlocking() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500); Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi up: " + WiFi.localIP().toString());
    if (MDNS.begin(HOSTNAME)) Serial.println("mDNS: " HOSTNAME ".local");
    // OTA: reflash over WiFi (Arduino IDE → network port "robot3") —
    // the inspector may be deployed somewhere you don't want to crawl to.
    // Motors are stopped during an update for safety.
    ArduinoOTA.setHostname(HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASSWORD);
    ArduinoOTA.onStart([]() { motorStop(); digitalWrite(BUZZER_PIN, LOW); });
    ArduinoOTA.begin();
    Serial.println("OTA ready (password protected)");
  } else {
    Serial.println("\nWiFi FAILED — will keep retrying in loop()");
  }
}

// ── Setup ───────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  bootMillis = millis();

  pinMode(ENA, OUTPUT); pinMode(ENB, OUTPUT);
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);

  // Servo FIRST — claim its LEDC timers before the motors' analogWrite()
  // touches LEDC, so the two PWM users don't fight over a timer. If motor
  // speed control ever misbehaves after a core update, that's the clash —
  // the fix is to move ENA/ENB to ledcWrite(); see docs/robot3_flashing.md.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  armServo.setPeriodHertz(50);                 // standard hobby servo
  armServo.attach(SERVO_PIN, 500, 2400);       // µs pulse range
  armServo.write(SERVO_HOME_DEG);

  motorStop();

  chirp(2, 150);                      // boot beep

  Wire.begin(21, 22);
  mpu_ok = mpu.begin();
  Serial.println(mpu_ok ? "MPU6050 OK" : "MPU6050 FAIL (continuing)");

  wifiConnectBlocking();

  server.on("/", []() { server.send_P(200, "text/html", INDEX_HTML); });

  server.on("/telemetry", []() {
    String json = "{\"d\":" + String(dist_cm, 1) +
                  ",\"g\":" + String(gas_val) +
                  ",\"x\":" + String(ax, 2) +
                  ",\"y\":" + String(ay, 2) +
                  ",\"a\":" + String(alarmActive ? 1 : 0) +
                  ",\"rssi\":" + String(WiFi.RSSI()) +
                  ",\"uptime\":" + String((millis() - bootMillis) / 1000) +
                  ",\"servo\":" + String(servo_deg) +
                  ",\"last_cmd_age\":" + String(millis() - lastCmdTime) + "}";
    server.send(200, "application/json", json);
  });

  server.on("/control", []() {
    String d = server.arg("dir");
    setDirection(d.length() ? d[0] : 'S');
    server.send(200, "text/plain", "OK");
  });

  server.on("/servo", []() {
    int deg = server.arg("deg").toInt();
    servo_target = constrain(deg, SERVO_MIN_DEG, SERVO_MAX_DEG);
    server.send(200, "text/plain", "OK:" + String(servo_target));
  });

  server.begin();
  Serial.println("Inspector v2 ready");
}

// ── Loop ────────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. WiFi self-healing: stop first, then rejoin
  if (WiFi.status() != WL_CONNECTED) {
    if (currentDir != 'S') {
      motorStop(); currentDir = 'S';
      chirp(2, 80);                     // audible "link lost, stopping"
      Serial.println("WIFI LOST — motors stopped");
    }
    if (now - lastWifiAttempt > WIFI_RETRY_MS) {
      lastWifiAttempt = now;
      Serial.println("WiFi reconnect attempt…");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  } else {
    server.handleClient();
    ArduinoOTA.handle();
  }

  // 2. Command watchdog: the v1 drive-forever bug fix
  if (currentDir != 'S' && now - lastCmdTime > CMD_WATCHDOG_MS) {
    motorStop(); currentDir = 'S';
    chirp(1, 60);
    Serial.println("CMD WATCHDOG — motors stopped");
  }

  // 2b. Servo slew: step toward the target so a big move spreads its
  // current draw over time instead of one brown-out-inducing lunge. The
  // servo HOLDS position on WiFi loss (no watchdog) — unlike the motors,
  // a stuck arm angle is safe, and snapping it home could swing it into
  // something.
  if (now - lastServoMove > SERVO_SLEW_MS && servo_deg != servo_target) {
    lastServoMove = now;
    if (servo_deg < servo_target)
      servo_deg = min(servo_target, servo_deg + SERVO_STEP_DEG);
    else
      servo_deg = max(servo_target, servo_deg - SERVO_STEP_DEG);
    armServo.write(servo_deg);
  }

  // 3. Sensors + latched gas alarm
  if (now - lastSensor > SENSOR_PERIOD_MS) {
    lastSensor = now;

    digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    // 15 ms timeout = ~2.5 m max range; halves the worst-case time this
    // blocking read steals from the web server / watchdog loop
    dist_cm = pulseIn(ECHO_PIN, HIGH, 15000) * 0.034 / 2;

    gas_val = analogRead(GAS_PIN);
    if (gas_val > GAS_ALARM_THRESHOLD) {
      alarmActive = true;
      alarmSince = now;
    } else if (alarmActive
               && now - alarmSince > GAS_ALARM_MIN_MS
               && gas_val < GAS_CLEAR_THRESHOLD) {
      alarmActive = false;              // latched + hysteresis, never flickers
    }
    // pulsing buzzer (distinct from the watchdog chirp), works offline too
    digitalWrite(BUZZER_PIN, (alarmActive && (now / 250) % 2) ? HIGH : LOW);

    if (mpu_ok) {
      sensors_event_t a, g, t;
      mpu.getEvent(&a, &g, &t);
      ax = a.acceleration.x; ay = a.acceleration.y;
    }
  }
}
