"""Spoken detection announcements via Windows SAPI (System.Speech).

No third-party TTS dependency: a single persistent PowerShell process holds
a SpeechSynthesizer and speaks each line it reads from stdin. Speaking from
that child keeps the UI thread free; a per-key cooldown stops a continuously
visible target from repeating "human detected" every frame.

Degrades silently to a no-op if PowerShell/SAPI is unavailable (e.g. a
non-Windows dev box) — callers never need to guard.
"""

from __future__ import annotations

import subprocess
import threading
import time

# Persistent speaker loop: read a line, speak it; blank line ignored, EOF ends.
_PS_SPEAKER = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Rate = 1;"
    "while ($true) {"
    "  $l = [Console]::In.ReadLine();"
    "  if ($l -eq $null) { break };"
    "  if ($l.Trim() -ne '') { $s.Speak($l) }"
    "}"
)


class Speaker:
    """Fire-and-forget TTS with a per-key cooldown."""

    def __init__(self, cooldown_s: float = 4.0, enabled: bool = True):
        self._cooldown = cooldown_s
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._ok = False
        self.muted = False
        if not enabled:
            return
        try:
            self._proc = subprocess.Popen(
                ['powershell', '-NoProfile', '-NonInteractive', '-Command',
                 _PS_SPEAKER],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True, bufsize=1,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self._ok = self._proc.stdin is not None
        except Exception:
            self._proc = None
            self._ok = False

    @property
    def available(self) -> bool:
        return self._ok

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)

    def announce(self, key: str, phrase: str) -> None:
        """Speak ``phrase`` unless muted or ``key`` spoke within the cooldown."""
        if self.muted:
            return
        now = time.monotonic()
        with self._lock:
            if not self._ok or self._proc is None or self._proc.stdin is None:
                return
            if now - self._last.get(key, 0.0) < self._cooldown:
                return
            self._last[key] = now
            try:
                self._proc.stdin.write(phrase + '\n')
                self._proc.stdin.flush()
            except Exception:
                self._ok = False                  # pipe died → go quiet

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.terminate()
        except Exception:
            pass
        self._proc = None
        self._ok = False
