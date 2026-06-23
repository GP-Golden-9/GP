/*
 * ROBOT 1 "ALPHA" — MOTOR CONTROLLER v3
 * Arduino Mega 2560 · 4WD · no encoders used (SLAM localizes by scan match)
 *
 * v3 professionalizes v2 without changing the wire protocol:
 *   · NON-BLOCKING line parser — v2's single-char reads worked, but P<pwm>
 *     parsing used delay(10) inside the loop and readSpeed could shear a
 *     "P1" / "80" split across packets. Bytes now accumulate into a line
 *     buffer; nothing in loop() ever blocks.
 *   · WATCHDOG HONESTY — in v2 *every* byte (including the bridge's 1 Hz
 *     '?' status poll) reset the watchdog, so the safety stop could never
 *     fire while the bridge process was alive. Diagnostics no longer feed
 *     the watchdog; only motion/config commands do. The deadman chain
 *     (console 10 Hz → gateway 0.6 s → bridge 0.8 s → THIS 2 s) is now
 *     real on robot1 too.
 *   · Consistent OK:/ERR: replies for every command (machine-parseable).
 *
 * v3.1 (2026-06-23): WATER PUMP relocated from Beta to Alpha. Alpha now
 *   carries the 1-ch relay + pump and runs the "go to fire -> pump -> return"
 *   action (it has lidar, so it navigates far better than Beta). Same U1/U0
 *   wire protocol Beta's v5 firmware used, so the gateway/bridge are unchanged.
 *   10 s hard auto-off (even if the Pi/console dies mid-spray), 1 s cooldown,
 *   forced OFF by e-stop and at boot.
 *
 * Commands: F B L R S · E/X e-stop · P<80-255> speed · U1/U0 pump · ? status
 * Status reply: STS:<IDLE|MOVING|ESTOP>,SPD:<current>
 */

// ── Pins (unchanged from the working v2 build) ──────────────────────────
const int RL_PWM = 4,  RL_IN1 = 22, RL_IN2 = 23;
const int RR_PWM = 5,  RR_IN1 = 24, RR_IN2 = 25;
const int FR_PWM = 6,  FR_IN1 = 27, FR_IN2 = 26;
const int FL_PWM = 7,  FL_IN1 = 29, FL_IN2 = 28;

// ── Water pump (v3.1) — 1-ch relay module on a free digital pin ─────────
#define PUMP_RELAY_PIN     34    // free pin (motors use 4-7 + 22-29)
#define RELAY_ACTIVE_LOW   0     // trigger polarity: 0 = HIGH switches pump ON,
                                 // 1 = LOW switches it ON. Set to 0 because the
                                 // module ran the pump at boot with 1 (active-HIGH
                                 // board). If it now runs at boot with 0, your
                                 // module is active-LOW — set this back to 1.
#define PUMP_MAX_RUN_MS    10000UL  // hard auto-off (the fire action pumps 10 s)
#define PUMP_COOLDOWN_MS   1000UL   // minimum off-time between runs

// ── Tuning ──────────────────────────────────────────────────────────────
const int DEFAULT_SPEED = 180;
const int MIN_SPEED = 80;
const int MAX_SPEED = 255;
const unsigned long TIMEOUT_MS = 2000;   // watchdog: stop if no command
const int RAMP_UP_STEP = 15;             // soft start
const int RAMP_DOWN_STEP = 30;           // firmer stop

// ── State ───────────────────────────────────────────────────────────────
int targetSpeed = DEFAULT_SPEED;
int currentSpeed = 0;
char currentCommand = 'S';
bool emergencyStop = false;
unsigned long lastCommandTime = 0;

// ── Pump state (v3.1) ───────────────────────────────────────────────────
bool pumpOn = false;
unsigned long pumpOnSince = 0;
unsigned long pumpCooldownUntil = 0;

void setup() {
    Serial.begin(115200);

    const int pins[] = {FR_PWM, FR_IN1, FR_IN2, FL_PWM, FL_IN1, FL_IN2,
                        RR_PWM, RR_IN1, RR_IN2, RL_PWM, RL_IN1, RL_IN2};
    for (int i = 0; i < 12; i++) pinMode(pins[i], OUTPUT);

    stopAllMotors();

    // Pump relay: preload the OFF level BEFORE the pin becomes an OUTPUT so an
    // active-low relay never glitches ON during boot.
#if RELAY_ACTIVE_LOW
    digitalWrite(PUMP_RELAY_PIN, HIGH);
#else
    digitalWrite(PUMP_RELAY_PIN, LOW);
#endif
    pinMode(PUMP_RELAY_PIN, OUTPUT);
    pumpWrite(false);

    Serial.println(F("ROBOT1 CONTROLLER v3.1"));
    Serial.println(F("OK:READY"));
    lastCommandTime = millis();
}

void loop() {
    pollSerial();

    // Watchdog — only meaningful commands refresh it (see header)
    if (currentCommand != 'S' && !emergencyStop
            && millis() - lastCommandTime > TIMEOUT_MS) {
        currentCommand = 'S';
        Serial.println(F("WARN:WATCHDOG_TIMEOUT"));
    }

    updateSpeed();
    executeMovement();
    pumpSafetyTick();          // hard auto-off no matter what the Pi is doing
    delay(10);
}

// ── Non-blocking line parser ────────────────────────────────────────────
void pollSerial() {
    static char buf[16];
    static uint8_t len = 0;
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (len > 0) { buf[len] = '\0'; processLine(buf); len = 0; }
        } else if (len < sizeof(buf) - 1) {
            buf[len++] = c;
        } else {
            len = 0;                          // garbage flood → drop line
        }
    }
}

void processLine(const char *line) {
    char cmd = toupper(line[0]);

    if (cmd != '?') lastCommandTime = millis();   // diagnostics don't feed it

    switch (cmd) {
        case 'F': case 'B': case 'L': case 'R':
            if (emergencyStop) { Serial.println(F("ERR:ESTOP")); return; }
            currentCommand = cmd;
            Serial.print(F("OK:")); Serial.println(cmd);
            break;
        case 'S':
            currentCommand = 'S';
            Serial.println(F("OK:STOP"));
            break;
        case 'U':   // water pump (NOT 'W'): U1 = on, U0 = off
            setPump(line[1] == '1');
            break;
        case 'E':
            emergencyStop = true;
            currentCommand = 'S';
            currentSpeed = 0;
            hardBrake();
            if (pumpOn) { pumpOn = false; pumpWrite(false);
                          pumpCooldownUntil = millis() + PUMP_COOLDOWN_MS; }
            Serial.println(F("OK:ESTOP"));
            break;
        case 'X':
            emergencyStop = false;
            Serial.println(F("OK:RELEASED"));
            break;
        case 'P': {
            int v = atoi(line + 1);
            if (v <= 0) { Serial.println(F("ERR:PWM_SYNTAX")); return; }
            targetSpeed = constrain(v, MIN_SPEED, MAX_SPEED);
            Serial.print(F("OK:SPD=")); Serial.println(targetSpeed);
            break;
        }
        case '?':
            Serial.print(F("STS:"));
            Serial.print(emergencyStop ? F("ESTOP")
                         : (currentCommand == 'S' ? F("IDLE") : F("MOVING")));
            Serial.print(F(",SPD:")); Serial.println(currentSpeed);
            break;
        default:
            Serial.print(F("ERR:UNKNOWN_CMD '"));
            Serial.print(cmd); Serial.println(F("'"));
            break;
    }
}

// ── Motion (unchanged geometry from v2 — verified on the robot) ────────
void updateSpeed() {
    int desired = (currentCommand == 'S' || emergencyStop) ? 0 : targetSpeed;
    if (currentSpeed < desired)      currentSpeed = min(currentSpeed + RAMP_UP_STEP, desired);
    else if (currentSpeed > desired) currentSpeed = max(currentSpeed - RAMP_DOWN_STEP, desired);
}

void motorSet(int pwm, int in1, int in2, int speed, bool fwd) {
    analogWrite(pwm, abs(speed));
    if (speed == 0)      { digitalWrite(in1, LOW);  digitalWrite(in2, LOW);  }
    else if (fwd)        { digitalWrite(in1, HIGH); digitalWrite(in2, LOW);  }
    else                 { digitalWrite(in1, LOW);  digitalWrite(in2, HIGH); }
}

void executeMovement() {
    switch (currentCommand) {
        case 'F': driveAll(true);  break;
        case 'B': driveAll(false); break;
        case 'L': spin(false);     break;
        case 'R': spin(true);      break;
        default:  stopAllMotors(); break;
    }
}

void driveAll(bool fwd) {
    motorSet(FR_PWM, FR_IN1, FR_IN2, currentSpeed, fwd);
    motorSet(FL_PWM, FL_IN1, FL_IN2, currentSpeed, fwd);
    motorSet(RR_PWM, RR_IN1, RR_IN2, currentSpeed, fwd);
    motorSet(RL_PWM, RL_IN1, RL_IN2, currentSpeed, fwd);
}

void spin(bool clockwise) {
    // turning needs torque: full PWM, sides opposed (as in v2)
    motorSet(FL_PWM, FL_IN1, FL_IN2, MAX_SPEED, clockwise);
    motorSet(RL_PWM, RL_IN1, RL_IN2, MAX_SPEED, clockwise);
    motorSet(FR_PWM, FR_IN1, FR_IN2, MAX_SPEED, !clockwise);
    motorSet(RR_PWM, RR_IN1, RR_IN2, MAX_SPEED, !clockwise);
}

void stopAllMotors() {
    motorSet(FR_PWM, FR_IN1, FR_IN2, 0, true);
    motorSet(FL_PWM, FL_IN1, FL_IN2, 0, true);
    motorSet(RR_PWM, RR_IN1, RR_IN2, 0, true);
    motorSet(RL_PWM, RL_IN1, RL_IN2, 0, true);
}

void hardBrake() {
    digitalWrite(FR_IN1, HIGH); digitalWrite(FR_IN2, HIGH);
    digitalWrite(FL_IN1, HIGH); digitalWrite(FL_IN2, HIGH);
    digitalWrite(RR_IN1, HIGH); digitalWrite(RR_IN2, HIGH);
    digitalWrite(RL_IN1, HIGH); digitalWrite(RL_IN2, HIGH);
    analogWrite(FR_PWM, 255); analogWrite(FL_PWM, 255);
    analogWrite(RR_PWM, 255); analogWrite(RL_PWM, 255);
    delay(100);                              // brief brake pulse is intended
    stopAllMotors();
}

// ── Water pump (v3.1) ───────────────────────────────────────────────────
void pumpWrite(bool on) {
#if RELAY_ACTIVE_LOW
    digitalWrite(PUMP_RELAY_PIN, on ? LOW : HIGH);
#else
    digitalWrite(PUMP_RELAY_PIN, on ? HIGH : LOW);
#endif
}

void setPump(bool on) {
    unsigned long now = millis();
    if (on) {
        if (emergencyStop)           { Serial.println(F("ERR:ESTOP"));         return; }
        if (now < pumpCooldownUntil) { Serial.println(F("ERR:PUMP_COOLDOWN")); return; }
        pumpOn = true;
        pumpOnSince = now;
        pumpWrite(true);
        Serial.println(F("OK:PUMP=ON"));
    } else {
        if (pumpOn) pumpCooldownUntil = now + PUMP_COOLDOWN_MS;
        pumpOn = false;
        pumpWrite(false);
        Serial.println(F("OK:PUMP=OFF"));
    }
}

// Hard auto-off after PUMP_MAX_RUN_MS — fires even if the Pi/console dies.
void pumpSafetyTick() {
    if (pumpOn && millis() - pumpOnSince >= PUMP_MAX_RUN_MS) {
        pumpOn = false;
        pumpWrite(false);
        pumpCooldownUntil = millis() + PUMP_COOLDOWN_MS;
        Serial.println(F("WARN:PUMP_MAX_RUN - auto off"));
    }
}
