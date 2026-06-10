# Circuit & Wiring Manuals

One manual per robot — every pin, every connection, the full power tree:

| Robot | Manual | Controller | Power |
|---|---|---|---|
| Alpha · robot1 (Mapper) | [robot1.md](robot1.md) | Pi 4 + Arduino Mega 2560 | 12 V battery → LM2596S → 5 V |
| Beta · robot2 (Intervener) | [robot2.md](robot2.md) | Pi 3B+ + Arduino Mega 2560 | 12 V battery → 2× buck → 5 V / 6 V |
| Gamma · robot3 (Inspector) | [robot3.md](robot3.md) | ESP32 DevKit | 12 V battery → LM2596S → 5 V |

**Pin numbers come from the firmware** (`firmware/…`), which is the source
of truth — if you rewire, change the `#define` and reflash, never the other
way around.

## Rules that apply to every robot (read before wiring anything)

1. **ONE common ground.** Battery −, every buck converter −, motor driver
   GND, controller GND, every sensor GND: all tied together. 90 % of
   "random resets / garbage sensor data / motors twitch" is a missing
   ground bond.
2. **Master switch + fuse first.** Battery + → toggle switch → blade fuse →
   everything else. Fuse sizes are listed per robot. The team has burned
   parts before; the fuse is what burns instead from now on.
3. **Set the buck converter BEFORE connecting the load.** Power the
   LM2596S from the battery, turn the trimpot until the multimeter reads
   **5.10 V**, *then* connect the Pi/ESP32. A mis-set buck at 12 V kills a
   Pi instantly.
4. **Never feed motors from the 5 V rail.** Motors, pump: 12 V side only.
   The 5 V rail is for computers and sensors.
5. **Power-on order:** battery switch → wait for controller boot banner →
   then drive. Power-off: stop robot → switch off.
6. **Undervoltage is visible:** the Pi robots log `vcgencmd get_throttled`
   every minute (`~/gp_logs/throttled.log`) and the console's health panel
   shows the flags — `0x0` is healthy; anything else = fix power before
   driving.
7. Battery: 12 V class pack (3S LiPo 11.1–12.6 V or 12 V NiMH/SLA), charged
   with its matching charger. The LED voltmeter on the buck shows pack
   voltage — below 10.5 V (3S), land the robot and swap.

## Standard wire colors (used in all three manuals)

| Color | Meaning |
|---|---|
| red | +12 V battery |
| orange | +5 V rail |
| yellow | +3.3 V rail |
| black | GND |
| green/blue | signals (PWM, IN1…) |
| white/gray | encoder / I2C signals |
