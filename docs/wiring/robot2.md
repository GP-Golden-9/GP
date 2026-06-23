# Robot 2 "Beta" — Intervener · Circuit Manual

**Brain:** Raspberry Pi 3B+ + Arduino Mega 2560 (`firmware/robot2_controller_v5`)
**Drive:** 4 × 25GA370 12 V encoder motors on ONE L298N (paired per side)
**Payload:** USB camera · GY-87 10-DOF IMU · water pump (relay) · arm servo ·
2 front HC-SR04 ultrasonics (added 2026-06-13)

## 1. Power tree (12 V battery → 5 V / 6 V)

```
12 V battery ─[master switch]─[10 A fuse]─┬─→ L298N VS (4 motors, paired)
                                          ├─→ LM2596S #1 ─[5.10 V]─→ Pi 3B+ (GPIO 5V)
                                          │                          └─ LED voltmeter
                                          └─→ LM2596S #2 / BEC ─[5.5–6.0 V]─→ servo + (470–1000 µF across it)
Pi USB ──→ Mega (power + serial, /dev/mega)        Pi USB ──→ camera
GND: ALL of the above to battery −  (servo GND must also reach Mega GND)
```

(Pump + relay moved to Alpha 2026-06-23 — see `docs/wiring/robot1.md`.)
⚠ **Servo on its own buck/BEC** — a stalling servo on the Pi's rail caused
brown-outs in bench tests (see docs/bench_robot2_v5.md §0).

## 2. L298N (jumpers: ENA/ENB removed, 12 V jumper ON)

Each output channel drives TWO motors in parallel (left pair / right pair).
25GA370 stall ≈ 2 A each — avoid stalling both wheels of a side at once.

| Mega pin | → | L298N | Function |
|---|---|---|---|
| D10 (PWM) | → | ENA | left pair speed |
| D8 / D9 | → | IN1 / IN2 | left direction |
| D11 (PWM) | → | ENB | right pair speed |
| D12 / D13 | → | IN3 / IN4 | right direction |

## 3. Wheel encoders (quadrature, 6-pin motor pigtail)

Encoder VCC → Mega 5 V · encoder GND → GND. Signals:

| Motor | A (interrupt) | B |
|---|---|---|
| Front-Left (M1) | D2 | D22 |
| Rear-Left (M2) | D3 | D24 |
| Front-Right (M3) | D18 | D26 |
| Rear-Right (M4) | D19 | D28 |

Drive forward (`F`): all four counts must INCREASE in the `D:` stream. A
decreasing pair → swap that motor's A and B wires.

## 4. GY-87 IMU (I2C)

| GY-87 | → | Mega |
|---|---|---|
| VCC | → | 5 V (module has onboard regulator) |
| GND | → | GND |
| SDA | → | D20 (SDA) |
| SCL | → | D21 (SCL) |

Boot banner must show `MPU6050 OK`, magnetometer `OK (HMC…/QMC…)`,
`BMP180 OK`. Keep the module away from motor wires (magnetometer).

## 5. Intervention tools (firmware v5)

> **2026-06-23: the WATER PUMP + relay were RELOCATED to Alpha (robot1).** Beta
> keeps only the arm servo. Remove Beta's relay + pump and the D7 signal wire;
> see `docs/wiring/robot1.md` §2b for the pump's new home. The `U1/U0` command
> is gone from Beta's firmware.

| Item | Mega pin | Wiring |
|---|---|---|
| Servo signal | **D5** | servo + → 6 V buck (§1), servo − → common GND |
| Buzzer | **D34** | buzzer **+** → D34, buzzer **−** → common GND (active buzzer module, HIGH = sound) |

Firmware safety: servo clamped 10–170°, slew-limited. Buzzer beeps on a camera
detection (the console sends `N<n>`; firmware beeps non-blocking, default twice).
If your buzzer is **passive** (needs a tone, not just DC), drive it with
`tone()/noTone()` in `buzzerTick()` instead of `digitalWrite`.
Complete `docs/bench_robot2_v5.md` before first powered test.

## 6. Front ultrasonics (HC-SR04 ×2, firmware v5)

Two forward-facing HC-SR04 — Beta has no lidar, so these are its only
real-time obstacle sense (forward-collision guard + goto slow-down). Read
round-robin (~16 Hz each). The Mega is 5 V logic, so ECHO needs **no
divider** (unlike the ESP32 on Gamma).

| HC-SR04 | → | Mega | Function |
|---|---|---|---|
| LEFT  TRIG | → | **D30** | trigger |
| LEFT  ECHO | → | **D31** | echo (5 V OK on Mega) |
| RIGHT TRIG | → | **D32** | trigger |
| RIGHT ECHO | → | **D33** | echo |
| both VCC | → | **5 V** | |
| both GND | → | GND | |

Mount at the front edge (offsets in `config/robot2.yaml`: left +x0.15/+y0.07,
right +x0.15/-y0.07). Thresholds: stop < 25 cm, clear > 40 cm, goto slows
< 60 cm. A disconnected sensor reads `US_MAX_CM` (150 = "clear").

## 7. Bring-up checklist

- [ ] Both bucks set (5.10 V / 6.0 V) BEFORE connecting Pi & servo
- [ ] Boot banner `v5.0`, `[INIT] Pump relay : OK (OFF)` — pump must NOT twitch at power-on
- [ ] `F` → all wheels forward, all 4 encoder counts increasing
- [ ] `U1` → pump runs; wait 5 s → auto-off; `U1` again → `ERR:PUMP_COOLDOWN`
- [ ] USB yank mid-`U1` → pump stops ≤ 1 s (the critical drill)
- [ ] `A30`/`A150` → smooth sweep, no Mega reset (banner doesn't reprint)
- [ ] `sudo systemctl start gp-robot2 gp-camera` → video + telemetry in console

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| Mega resets when servo moves | servo on Pi's buck → move to its own; add the capacitor |
| Pump ON at boot | relay jumper vs `RELAY_ACTIVE_LOW` mismatch |
| Encoders count wrong direction | swap A/B of that motor |
| IMU FAIL at boot | SDA/SCL swapped, or 3.3 V module variant — check `[SCAN] I2C devices` line |
| Robot pulls to one side | pairs share a channel — check one motor of the pair isn't dead |
