# Using Claude Code on another device (context sync)

Goal: open this project's Claude on a different computer and have it already
understand the whole system — no re-explaining.

## How it actually works

Claude Code does **not** sync your chat history between devices. Logging in on
a new machine authenticates the API; it does not download past conversations
(transcripts are local files on the machine where they happened).

What *is* portable is **`CLAUDE.md`** at the repo root. Claude Code loads it
automatically whenever you open the project, on any device. That file is the
project's durable memory — architecture, conventions, deploy steps, current
hardware state, open tickets. It travels with the repo through git.

## Steps on the other device

1. Install Claude Code and sign in:
   ```
   npm install -g @anthropic-ai/claude-code     # or the platform installer
   claude login
   ```
2. Clone the repo and enter it:
   ```
   git clone <your-repo-url> GP
   cd GP
   ```
3. Start Claude:
   ```
   claude
   ```
   `CLAUDE.md` loads automatically — Claude now knows the fleet, the transport
   fix, the deploy procedure, and the open tickets. Just tell it what you want
   to do next.
4. (Optional) Run the console with no robots attached to verify the checkout:
   ```
   python dashboard_qt/main.py --sim
   ```

## Keeping it current

`CLAUDE.md` is just a tracked file — when the project's durable state changes,
edit it and `git push`. Every device that pulls gets the update.

## What is deliberately NOT synced (and why)

- **Chat transcripts** — they contain passwords typed during sessions (SSH,
  WiFi). They stay local; never commit them.
- **Raw auto-memory files** (`~/.claude/.../memory/`) — these include access
  details (SSH user, OTA password, robot IPs). Committing them would publish
  recon info. `CLAUDE.md` carries the same *technical* knowledge with the
  secrets stripped out, which is what you actually need on another device.
- **`.claude/settings.local.json`** — machine-local permission rules and
  paths; gitignored.

If you specifically want the raw memory files on GitHub too, only do it on a
PRIVATE repo, and prefer a redacted copy.
