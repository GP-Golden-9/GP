# Using Claude Code on the GP project (team guide)

How to drive the Claude Code CLI to work on this robot fleet. New teammate?
Read this once and you can deploy, diagnose, and run the demo with Claude's
help. (Cross-device setup is in `docs/claude_context_sync.md`; what every fix
was is in `docs/field_fixes_and_runbook_2026-06-18.md`.)

---

## 1. Install & start

```
npm install -g @anthropic-ai/claude-code     # or the platform installer
claude login                                  # one-time auth
git clone <repo-url> GP && cd GP
claude                                         # start it INSIDE the repo
```

When you run `claude` inside the repo it **auto-loads `CLAUDE.md`** — so it
already knows the fleet (Alpha/Beta/Gamma), the architecture, the deploy
quirks, the current hardware state, and the open tickets. You don't have to
explain the project. Just tell it what you want.

- `claude --resume` reopens a **past session on this machine** (sessions are
  local; they don't sync between computers).
- `/help` lists CLI commands; `/clear` starts a fresh conversation.

---

## 2. What Claude can do here

Claude has the repo's tools and can, with your approval per action:
- **Read/search/edit** any code and run `python -m pytest tests -q`.
- **SSH to the robots** and deploy (it knows the bundle method for Beta).
- **Run the dashboard** (`python dashboard_qt/main.py`, `--sim` for no hardware).
- **Diagnose live** — read telemetry, watch logs, run `tools/*`.

It asks permission before running commands or editing files. **Read what it's
about to do before approving** — especially anything that restarts a robot,
deploys, or cuts power. The physical **e-stop and the console STOP are yours**,
not Claude's.

---

## 3. Good things to ask (copy/paste starters)

Claude works best with a clear goal. Examples that fit this project:

- "Run the dashboard in sim mode so I can see the UI with no robots."
- "Deploy the latest code to Beta and restart its stack, then confirm it came
  up clean." (It'll use the git-bundle method — Beta has no GitHub internet.)
- "Beta drives into walls after a minute — diagnose it." (It knows the
  serial-lag history; it'll check the live telemetry.)
- "The map arrow is static when I rotate Beta — why?" (It'll check if the
  GY-87 IMU dropped off — see the runbook.)
- "Calibrate Beta's gyro scale factor." (Uses `tools/yaw_calib.py`.)
- "Run the tests and tell me what fails."
- "Walk me through running the FIRE TEST demo."

Be specific about the **symptom** and the **robot**. Paste the console NAV LOG
or a `journalctl` snippet if you have one — Claude reads them.

---

## 4. Conventions Claude follows (and you should too)

- **Never commit secrets.** WiFi/SSH/OTA creds live in the gitignored
  `firmware/**/config_secrets.h`. Don't paste passwords into chat — they end
  up in the local transcript. If you must, rotate afterward.
- **Deploy to Beta = git bundle over the LAN** (no GitHub internet on Beta).
  Claude does this for you; the manual steps are in the runbook.
- **A systemd/unit change needs `install_systemd.sh`** (a plain `git pull`
  does NOT update `/etc/systemd/system`). Claude knows; if you do it by hand,
  run `tools/deploy_and_verify.sh robotN`.
- **Commits** end with a `Co-Authored-By: Claude …` line. Claude pushes only
  when you ask.
- **Keep tool output ASCII** on the Windows console (cp1252).
- **mDNS is flaky** — fall back to IPs (Alpha 192.168.1.200, Beta .203).

---

## 5. Safety & gotchas

- Approving a deploy/restart on Beta **mid-mapping clears the map** (Alpha) or
  briefly stops Beta. Don't restart during a live demo run.
- Claude can't press the physical e-stop. Keep it in reach during any drive
  test; **Esc** in the console is the software e-stop.
- If Claude proposes restarting a robot or cutting power, that's an
  outward/physical action — confirm it's what you want before approving.
- The **GY-87 IMU drops out** intermittently. If heading freezes mid-run,
  power-cycle the robot (and rewire it to 5 V before the demo).

---

## 6. Where to look

| You want… | File |
|---|---|
| Project overview (auto-loaded) | `CLAUDE.md` |
| Every error → fix + how to run the demo | `docs/field_fixes_and_runbook_2026-06-18.md` |
| Using Claude on another computer | `docs/claude_context_sync.md` |
| Flashing the ESP32 (Gamma) | `docs/robot3_flashing.md` |
| Calibrate yaw / health-check / deploy | `tools/yaw_calib.py`, `tools/fleet_healthcheck.py`, `tools/deploy_and_verify.sh` |
| Redacted memory snapshot | `.claude/memory/` |

When in doubt: open `claude` in the repo and ask. It has all of the above in
context already.
