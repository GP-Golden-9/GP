# Robot3 "Gamma" (ESP32) — flashing over FTDI

The inspector node's **onboard USB-serial is broken**, so firmware is flashed
through an **FT232RL USB-to-TTL** adapter. This is the confirmed-working
procedure (verified 2026-06-13: full 1 MB sketch written + hash-verified on an
ESP32-D0WD-V3).

Firmware: `firmware/robot3_controller_v2/robot3_controller_v2.ino`
Board (Arduino IDE): **ESP32 Dev Module** (a.k.a. DOIT ESP32 DEVKIT V1)

---

## ⚠️ Two things that will bite you

1. **FT232RL voltage jumper → 3.3 V.** This sets the TX/RX logic level. The
   ESP32's RX is *not* 5 V-tolerant — flashing at 5 V logic slowly damages the
   chip. Set it before wiring anything.

2. **Power the ESP32 separately; let the FTDI do data only.** The FT232RL's
   onboard 3.3 V regulator (~50 mA) browns out during the bootloader sync,
   which shows up as `Failed to connect: No serial data received`. Powering the
   ESP32 from its own USB/5 V source (FTDI = TX/RX/GND only, grounds common)
   is what made the flash connect first try.

---

## Wiring: FT232RL → ESP32

| FT232RL | ESP32        | Purpose                                   |
|---------|--------------|-------------------------------------------|
| **TXD** | **RX0** (GPIO3) | FTDI transmit → ESP receive            |
| **RXD** | **TX0** (GPIO1) | FTDI receive → ESP transmit            |
| **GND** | **GND**      | common ground — mandatory                 |

TX↔RX is **crossed**. If you get `No serial data received`, swap these two
first — it's the most common mistake and gives that exact error.

Leave **DTR / RTS / CTS unconnected** — they're only for the auto-reset
circuit; the manual boot sequence below is more reliable with loose wires.

Power: ESP32 from a separate verified 5 V into **VIN** (or its own USB).
Do **not** also feed 3V3 from the FTDI at the same time.

---

## Boot mode (the strapping pins)

The ESP32 reads its **strapping pins** the instant `EN` rises out of reset —
before your sketch runs:

- **GPIO0 (BOOT)** — internal pull-up = HIGH = normal boot. Pull **LOW at
  reset → serial download (flash) mode.** This is the "G0 to GND" step.
- **EN (RST / CHIP_PU)** — a LOW pulse resets the chip; GPIO0 is sampled on
  its rising edge. So: **GPIO0 must already be LOW when EN goes high.**

### Confirmed sequence
1. **GPIO0 → GND** (jumper, hold it).
2. **Press RST** (or pulse EN → GND).
3. Click **Upload**.
4. Keep GPIO0 grounded through the `Connecting....` dots; release once it
   prints `Chip is ESP32...`. (Releasing too early is the usual cause of a
   failed sync — the chip falls through to normal boot before esptool syncs.)
5. On `Hash of data verified` → **press RST** to run. You'll hear the **two
   boot beeps** (`chirp(2, 150)`) and see `WiFi connecting...` at 115200 —
   that's your success signal.

### Gotcha specific to THIS firmware
The pinout puts two peripherals on strapping pins:
- **ECHO_PIN = GPIO5** (strapping, must be HIGH at reset) — the HC-SR04 echo
  idles LOW and can fight the pull-up, disturbing download mode.
- **BUZZER_PIN = GPIO15** (strapping) — LOW at reset just mutes the boot log,
  mostly harmless.

**Flash with the ultrasonic and buzzer disconnected.** If a flash fails with
the sensor wired in, GPIO5 is the first suspect. (GPIO2 and GPIO12 — the other
two strapping pins — are unused here, so they're not a concern. Don't ever pull
GPIO12 high: it selects 1.8 V flash and bricks the boot.)

---

## Upload settings
- **Board:** ESP32 Dev Module / DOIT ESP32 DEVKIT V1
- **Port:** the FTDI's COM port (needs FTDI VCP driver installed)
- **Upload Speed:** 115200 if a flaky FT232RL clone fails at higher speeds;
  a genuine module negotiates up to 921600 fine (the verified flash did).

---

## After the first wired flash: use OTA, skip all of the above

This firmware runs **ArduinoOTA** (`robot3_controller_v2.ino` setup()):
- Arduino IDE → **Port → Network Ports → `robot3`**
- Password: `gp-inspector` (`OTA_PASSWORD`, override in `config_secrets.h`)
- Motors are stopped automatically during an update.

So the FTDI/strapping-pin ritual is a **one-time** cost — every later upload
goes over WiFi, no crawling to the robot.

---

## Troubleshooting `No serial data received` (COM port opens, chip won't sync)
In order, cheapest first:
1. **Boot timing** — hold GPIO0 low *through* `Connecting....`, not just during reset.
2. **Swap TX/RX** — 50/50 chance they're backwards.
3. **Common ground** — FTDI GND ↔ ESP GND.
4. **Strapping pins** — unplug ultrasonic (GPIO5) / buzzer (GPIO15).
5. **Brownout** — power ESP32 from a separate 5 V; FTDI does data only.
6. If a plain serial monitor on the port shows **nothing** when you tap RST
   (no `rst:0x... ets ...` ROM banner), the chip itself is unresponsive
   (dead or TX-line broken) — not a timing problem.
