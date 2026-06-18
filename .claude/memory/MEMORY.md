# Memory index (redacted snapshot)

This is a git-committed, **redacted** copy of the Claude Code auto-memory for
this project. Access secrets (passwords, OTA keys, passwordless-sudo specifics)
are stripped — see CLAUDE.md and the gitignored `config_secrets.h` for the
real ones. The live, unredacted memory lives on the operator's machine under
`~/.claude/projects/<project-hash>/memory/`.

- [Fleet ops & hardware tickets](fleet-ops-and-hardware-tickets.md) — the DDS
  LOCALHOST_ONLY/WiFi root cause + transport-whitelist fix, power-delivery
  findings, robot2/robot3 hardware, console fleet ops, open hardware tickets,
  current state (through 2026-06-18: serial-lag, yaw, stall-disarm, FIRE TEST,
  IMU dropout).

Team-facing runbook + every error→fix (not a memory file, but the place to
start): **`docs/field_fixes_and_runbook_2026-06-18.md`**.
