# Robot 1 "Alpha" — Mapper + Extinguisher · Circuit Manual

**Brain:** Raspberry Pi 4 (8 GB) + Arduino Mega 2560 (`firmware/robot1_controller_v3`)
**Drive:** 4 × JGB37-520 12 V geared motors (Hall encoders on board, see §5)
**Sensor:** RPLidar A1M8 (USB)
**Payload (v3.1, 2026-06-23):** water pump on a 1-ch relay — Alpha now runs the
"go to fire → pump 10 s → return" action (relocated from Beta; Alpha has lidar
so it navigates there far better).

## 1. Power tree (12 V battery → 5 V)

```
12 V battery ─[master switch]─[10 A fuse]─┬─→ L298N #1 VS  (front motors)
                                          ├─→ L298N #2 VS  (rear motors)
                                          ├─→ relay COM ──(NO)── pump + ─ pump − → GND
                                          └─→ LM2596S buck ─[set 5.10 V]─→ Pi 4 (GPIO 5V pins 2&4 + GND 6)
                                                                            ├─ LED voltmeter shows pack V
                                                                            └─ relay module VCC (5 V coil)
Pi 4 USB ──→ Arduino Mega (power + serial, shows as /dev/mega)
Pi 4 USB ──→ RPLidar A1 adapter (power + serial, shows as /dev/rplidar)
GND: battery − = buck − = both L298N GND = Mega GND = relay GND = pump −  (one node!)
```

⚠ Pi 4 + LiDAR + Mega draw ≈ 1.5–2.5 A at 5 V. A bare LM2596S handles this
only with a heatsink and the output set to **5.10 V**; if
`vcgencmd get_throttled` ever ≠ `0x0`, upgrade to a 5 V/5 A buck (XL4015).

⚠ **Pump load NEVER through the 5 V rail** — the relay CONTACTS switch
battery-direct **12 V** (use the pump's rated voltage; most GP mini pumps are
12 V). Only the relay **coil** (module VCC + IN) is 5 V logic. Wire the pump on
the relay's **NO** (normally-open) contact so the pump is OFF whenever the relay
is unpowered or anything fails.

## 2. Motor drivers — 2 × L298N (one channel per motor)

Remove the ENA/ENB jumpers (we PWM them). 12 V jumper ON (5 V logic from VS).

| Mega pin | → | Module | Motor |
|---|---|---|---|
| D7 (PWM) | → | L298N #1 ENA | Front-Left |
| D29 / D28 | → | L298N #1 IN1 / IN2 | FL direction |
| D6 (PWM) | → | L298N #1 ENB | Front-Right |
| D27 / D26 | → | L298N #1 IN3 / IN4 | FR direction |
| D4 (PWM) | → | L298N #2 ENA | Rear-Left |
| D22 / D23 | → | L298N #2 IN1 / IN2 | RL direction |
| D5 (PWM) | → | L298N #2 ENB | Rear-Right |
| D24 / D25 | → | L298N #2 IN3 / IN4 | RR direction |

Motor outputs: OUT1/OUT2 → motor leads. If a wheel spins backwards on `F`,
swap that motor's two leads (don't edit code).

## 2b. Water pump — 1-channel relay (v3.1, 2026-06-23)

The relay is a logic-level **module** (opto-isolated, 5 V coil). The Mega drives
its **IN** pin; the relay's CONTACTS switch the 12 V pump.

```
 Mega D34 ───────────────► relay IN      (signal; LOW = ON, see jumper below)
 buck 5 V ───────────────► relay VCC     (coil supply)
 GND      ───────────────► relay GND
 12 V batt (fused) ──────► relay COM
 relay NO ───────────────► pump (+)
 pump (−) ───────────────► GND  (common node with battery −)
```

| Signal | Mega pin | Notes |
|---|---|---|
| Relay IN | **D34** | free pin (motors use D4–D7 + D22–D29). Mirrors `PUMP_RELAY_PIN 34` in the firmware. |
| Relay VCC / GND | 5 V / GND | coil power from the same buck as the Pi |
| Pump contacts | COM / **NO** | 12 V batt → COM, NO → pump+. **NO** (not NC) so the pump is OFF on any failure. |

Trigger polarity must match `RELAY_ACTIVE_LOW` in the firmware. This board is
**active-HIGH** (`RELAY_ACTIVE_LOW 0`) — it ran the pump at boot when set to
active-low. If yours instead runs the pump at boot with `0`, it's active-low —
set the define back to `1` and reflash. Firmware safety on top: **10 s** max
pump run, 1 s cooldown, pump OFF on e-stop and at boot.

## 3. LiDAR & serial identities

RPLidar A1 → its USB adapter → Pi USB port. Install
`systemd/99-gp-serial.rules` so it is ALWAYS `/dev/rplidar` and the Mega is
ALWAYS `/dev/mega` (this fixed the "LiDAR doesn't spin" failure — the two
devices used to swap names at boot).

## 4. Ultrasonic sensors (chassis-mounted, spec'd)

Not read by the current firmware. Leave them disconnected **or** wire and
label for future work — do not share pins from §2.

## 5. Wheel encoders (Hall, built into JGB37-520)

Present in hardware, **unused by current firmware** (robot1 localizes by
LiDAR scan-matching). Future odometry upgrade: encoder A channels would go
to interrupt pins D2/D3/D18/D19 — currently free on robot1. Until then,
insulate the encoder leads.

## 6. Bring-up checklist

- [ ] Buck set to 5.10 V with Pi disconnected; voltmeter reads pack voltage
- [ ] All grounds continuity-beep to battery −
- [ ] Power on → Mega serial monitor (115200): `ROBOT1 CONTROLLER v3.1` + `OK:READY`
- [ ] Pump must NOT twitch at power-on (relay jumper vs `RELAY_ACTIVE_LOW`)
- [ ] `F` → all 4 wheels forward (fix any reversed motor by swapping leads)
- [ ] Unplug USB mid-`F` → motors stop ≤ 2 s (watchdog)
- [ ] `U1` → pump runs → wait 10 s → auto-off (`WARN:PUMP_MAX_RUN`); `U1` again
      within 1 s → `ERR:PUMP_COOLDOWN`
- [ ] `U1` then `E` (e-stop) → pump stops immediately
- [ ] `ls -l /dev/rplidar /dev/mega` → both symlinks exist
- [ ] `sudo systemctl start gp-robot1` → preflight PASS, map appears in console
- [ ] `vcgencmd get_throttled` = `0x0` while driving

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| Pi reboots when motors start | undervoltage — buck too weak / thin wires; check throttled.log |
| One wheel reversed | swap that motor's OUT leads |
| LiDAR not spinning | `/dev/rplidar` exists? powered USB? console's scan watchdog recovers it |
| Garbage on serial | common ground missing between Mega and Pi (USB usually provides it) |
| Pump ON at boot / inverted | relay module jumper vs `RELAY_ACTIVE_LOW` mismatch — flip the jumper or the define |
| Pump won't run | check NO (not NC) contact; relay VCC on 5 V; D34 → IN; `U1` prints `OK:PUMP=ON` |
