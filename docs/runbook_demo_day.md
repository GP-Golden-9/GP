# Demo-Day Runbook

Print this. Assign names to roles before the demo. A dress rehearsal of
this entire document, executed by someone who did NOT write the code, is
the Phase-6 acceptance gate.

## Roles

| Role | Person | Owns |
|---|---|---|
| Operator | ______ | console, driving, narration to jury |
| Robot wrangler | ______ | physical robots, batteries, e-stop hands-on |
| Systems | ______ | SSH to Pis, restarts, log pulls |

## T-60 min checklist

- [ ] Batteries charged + ONE spare set; measure voltages: r1 ____ V, r2 ____ V
- [ ] Router on its own 5 GHz SSID; channel scan done (phone app), channel: ____
- [ ] Power both robots → systemd brings the stacks up; or `./rasp_cmd/robotN.sh`
- [ ] `ssh pi@robot.local  'systemctl is-active gp-robot1 gp-preflight'` → active
- [ ] `ssh pi@robot2.local 'systemctl is-active gp-robot2 gp-camera'` → active
- [ ] Preflight PASS on both (`journalctl -u gp-preflight -n 20`)
- [ ] `vcgencmd get_throttled` = `0x0` on BOTH Pis (else: fix power NOW)
- [ ] Console up (`python dashboard_qt/main.py`), all stream LEDs green
- [ ] 2-min soak: `python tools/soak_test.py --host robot2.local --minutes 2` → PASS

## T-30 min functional drills (every demo, no exceptions)

- [ ] Drive each robot 10 s continuous forward — no stalls
- [ ] Esc e-stop while driving → stops < 0.5 s, release works
- [ ] Map renders, click-to-goal on robot2 reaches a 1 m goal
- [ ] Fire model: lighter/printed flame in front of camera → detection box
- [ ] Pump: hold button → sprays, release → stops; auto-off works (hold > 5 s)
- [ ] Servo arm sweep from console
- [ ] Robot3: gas from a lighter (unlit!) near MQ-5 → buzzer + DANGER in UI

## If something breaks mid-demo (fastest lever first)

| Symptom | Lever (in order) |
|---|---|
| Video gone, control fine | wait 5 s (auto-reconnect) → `ssh robot2 'sudo systemctl restart gp-camera'` |
| One robot uncontrollable | hands-on e-stop → `sudo systemctl restart gp-robotN` (≈15 s) |
| Map frozen | drive 1 m (map updates need travel) → restart gp-robot1 |
| Console frozen/closed | relaunch `main.py` (robots unaffected — they stop via deadman) |
| AI badge says OFF | keep narrating on raw video; model selector → reselect model |
| Everything dead | router power-cycle (60 s); robots auto-rejoin; worst case: tmux fallback `./rasp_cmd/robotN.sh` |
| LiDAR not spinning | scan_watchdog recovers in ≤15 s; else replug USB → respawn picks it up |

## After ANY failure

```
python tools/collect_logs.py robot.local robot2.local
```
and add an entry to `docs/incident_log.md` while memory is fresh.

## Hard safety rules

1. The robot wrangler can ALWAYS reach the physical robots. Pump demos point
   away from electronics. Nobody steps in the arena while autonomous mode is on.
2. Esc is e-stop. It latches. Releasing it is a deliberate button click.
3. If `get_throttled` ≠ 0x0 at any check: swap battery before driving again.
