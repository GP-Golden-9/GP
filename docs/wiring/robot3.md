# Robot 3 "Gamma" — Inspector · Circuit Manual

**Brain:** ESP32 DevKit (3.3 V logic!) — `firmware/robot3_controller_v2`
**Drive:** 4 × 12 V DC motors (no encoders) on ONE L298N (paired per side)
**Payload:** MQ-5 gas sensor · HC-SR04 ultrasonic · GY-87 IMU · buzzer

## 1. Power tree (12 V battery → 5 V → 3.3 V)

```
12 V battery ─[master switch]─[7.5 A fuse]─┬─→ L298N VS (4 motors, paired)
                                           └─→ LM2596S ─[5.10 V]─→ ESP32 5V/VIN pin
                                                                  ├─→ MQ-5 VCC (heater ~150 mA)
                                                                  ├─→ HC-SR04 VCC
                                                                  └─→ buzzer + (via transistor, §5)
ESP32 onboard 3V3 ─→ GY-87 VCC   (keeps I2C at 3.3 V — NEVER 5 V here)
GND: battery − = buck − = L298N = ESP32 = every sensor  (one node)
```

⚠ The ESP32 is **3.3 V logic**. Anything that OUTPUTS 5 V toward an ESP32
pin needs a divider (§4). Powering the board: 5 V on the 5V/VIN pin is
fine (onboard regulator).

## 2. L298N (ENA/ENB jumpers removed)

| ESP32 GPIO | → | L298N | Function |
|---|---|---|---|
| 13 (PWM) | → | ENA | left pair speed |
| 32 / 33 | → | IN1 / IN2 | left direction |
| 25 (PWM) | → | ENB | right pair speed |
| 27 / 26 | → | IN3 / IN4 | right direction |

L298N inputs accept 3.3 V highs — no level shifting needed in this
direction.

## 3. MQ-5 gas sensor

| MQ-5 module | → | ESP32 |
|---|---|---|
| VCC | → | 5 V (heater needs 5 V) |
| GND | → | GND |
| **AO** | → | **GPIO 34** through a divider: AO ─ 1 kΩ ─ GPIO34 ─ 2 kΩ ─ GND |

GPIO 34 is input-only ADC — correct choice. The divider keeps a full-scale
5 V AO below the ADC's 3.3 V limit. **Thresholds (alarm 3000 / clear 2000)
were tuned on the existing build — if you change the divider, re-tune them
in the firmware + `config/robot3.yaml`.** MQ-5 needs ~2–3 min warm-up
after power-on before readings are meaningful.

## 4. HC-SR04 ultrasonic

| HC-SR04 | → | ESP32 |
|---|---|---|
| VCC | → | 5 V |
| GND | → | GND |
| TRIG | → | GPIO 18 (3.3 V trigger works) |
| **ECHO** | → | **GPIO 5** through a divider: ECHO ─ 1 kΩ ─ GPIO5 ─ 2 kΩ ─ GND |

ECHO is a **5 V output** — the divider protects the ESP32 pin.

## 5. Buzzer + IMU

| Item | Wiring |
|---|---|
| Active buzzer | GPIO 15 → 1 kΩ → NPN base (2N2222); emitter → GND; buzzer between 5 V and collector. (Direct GPIO drive exceeds the 12 mA pin budget on most buzzers.) |
| GY-87 | VCC → **3V3** · GND → GND · SDA → GPIO 21 · SCL → GPIO 22 |

## 6. Firmware & network

1. Copy `config_secrets.h.template` → `config_secrets.h`, set WiFi (and an
   OTA password). 2. Flash over USB once. 3. After that, updates go **over
   the air**: Arduino IDE → Tools → Port → network port `robot3`.

## 7. Bring-up checklist

- [ ] Buck at 5.10 V before connecting ESP32
- [ ] Boot: two chirps, serial shows `WiFi up: <ip>`, `mDNS: robot3.local`, `OTA ready`
- [ ] `http://robot3.local/` → control page; hold UP → drives, release → stops
- [ ] Kill WiFi mid-drive → stops ≤ 1 s + chirp (watchdog)
- [ ] Console fleet card shows `gas <value> · <rssi> dBm` live
- [ ] Unlit-lighter gas near MQ-5 (after warm-up) → buzzer pulses + GAS banner in console

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| Gas reading pegged ~4095 | divider missing on AO |
| Distance always 0 | ECHO divider wiring; sensor needs 5 V VCC |
| Brown-out resets when motors start | buck current limit / thin 12 V wires; never feed motors from 5 V |
| Won't join WiFi | 2.4 GHz network only (ESP32 has no 5 GHz!) — give it the router's 2.4 GHz SSID |
| IMU dead | GY-87 on 3V3? SDA 21 / SCL 22 swapped? |
