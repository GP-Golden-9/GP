# Robot 2 firmware v5 — bench checklist (HIL)

Run this ENTIRE checklist on the bench (wheels off the ground, pump in a
bucket) before installing v5 on the robot. Rollback at any point = reflash
`arduino/robot2_controller_v4/robot2_controller_v4.ino` (kept untouched).

## 0. Power gate — MANDATORY before wiring the pump/servo

The team has burned components before; do not skip this.

1. Measure pump current at 12 V (stall it briefly): __________ A
2. Measure servo current while pushing a load: __________ A
3. The LM2596S 5 V rail powers the Pi-side electronics. The **relay coil**
   may sit on 5 V, but the **pump load must switch battery-direct 12 V**
   through the relay contacts — never through the 5 V rail.
4. If the servo browns out the Mega when slewing under load (watch for the
   v5 boot banner reprinting = reset detector), give the servo its own
   5–6 V BEC and add a 470–1000 µF electrolytic across its supply.
5. Relay jumper: confirm H/L trigger setting matches
   `RELAY_ACTIVE_LOW` in the sketch (default 1 = low-level trigger).

## 1. Flash & boot (Arduino IDE, board: Mega 2560)

- [ ] Sketch compiles with only `Wire.h` + `Servo.h`
- [ ] Boot banner says **v5.0**; `[INIT] Pump relay : OK (OFF)` — and the
      pump did NOT twitch at power-on (boot-glitch guard works)
- [ ] Servo moves smoothly to 90° home (no snap)

## 2. Serial monitor drills (115200 baud, send each line)

| Send | Expect |
|---|---|
| `?` | help text includes the Intervention section |
| `A30` then `A150` | `OK:SERVO=…`, arm sweeps SMOOTHLY (~1 s for 120°), never snaps |
| `A999` | `OK:SERVO=170` — clamped, arm never exceeds the mechanical limit |
| `U1` | `OK:PUMP=ON`, pump runs |
| wait 5 s | `WARN:PUMP_MAX_RUN — auto off` — pump stops by itself |
| `U1` immediately | `ERR:PUMP_COOLDOWN` |
| `U1` after 1 s, then `U0` | ON then `OK:PUMP=OFF` |
| `U1`, then unplug USB | pump stops within 1 s (watchdog) — **the critical drill** |
| `E` while driving `F` | `OK:ESTOP`, hard brake; then `F` → `ERR:ESTOP` |
| `U1` while e-stopped | `ERR:ESTOP` |
| `X` then `F` | `OK:RELEASED`, drives again |
| `W0`, drive `F`, wait 3 s | motors keep running (watchdog off is for bench only!) — then `W1` |

## 3. Telemetry format

- [ ] `D:` lines now have **17 fields**; last three are `pump,servo,estop`
- [ ] Old robot2_bridge still parses them (it indexes only fields 0–10)
- [ ] `pytest tests/test_mega_parser.py` passes (v5 line shape is covered)

## 4. Endurance

- [ ] 50× pump on/off cycles (script or by hand): zero Mega resets
      (no boot banner reprints), relay clicks clean every time
- [ ] 20× full servo sweeps under load: no brown-out, no I2C errors in `I`

## 5. Integration (after install, robot on blocks)

- [ ] Dashboard pump button: runs while held, stops on release
- [ ] Dashboard E-STOP (Esc): motors + pump dead < 300 ms, UI latches
- [ ] Yank the WiFi router mid-spray: pump off ≤ 1 s (gateway deadman +
      bridge deadman + firmware watchdog — three layers, all must exist)
- [ ] `/accessory_state` shows `OK:PUMP=…` / `OK:SERVO=…` ACKs in the console
