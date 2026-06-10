#!/usr/bin/env python3
"""Incident bundle collector — pulls correlated logs from the robots and the
laptop into one folder, so a failure can be analyzed (or handed to someone
else) minutes after it happened.

    python tools/collect_logs.py robot.local robot2.local
    python tools/collect_logs.py robot2.local --user pi --since "2 hours ago"

Produces incidents/<UTC>/ containing, per robot:
    gp_logs/<latest run_id>/*.log      (structured JSON logs)
    journal.txt                        (journalctl -u 'gp-*')
    throttled.log                      (undervoltage history)
plus the laptop's newest ~/gp_logs/<run_id> (dashboard side, same run_id
correlation) and a MANIFEST.txt.

Requires ssh/scp in PATH (Windows 10 ships OpenSSH client) and key-based
auth to the Pis (ssh-copy-id pi@robot2.local once).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

SSH_OPTS = ['-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new']


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def collect_robot(host: str, user: str, since: str, dest: str, manifest: list):
    target = f'{user}@{host}'
    os.makedirs(dest, exist_ok=True)
    print(f'── {host}')

    rc, run_id = run(['ssh', *SSH_OPTS, target, 'ls -t ~/gp_logs | head -1'])
    run_id = run_id.strip().splitlines()[0] if rc == 0 and run_id.strip() else ''
    if run_id and not run_id.endswith('.log'):
        print(f'   latest run_id: {run_id}')
        rc2, out = run(['scp', *SSH_OPTS, '-r',
                        f'{target}:~/gp_logs/{run_id}', dest], timeout=120)
        manifest.append(f'{host}: gp_logs/{run_id} '
                        f'{"OK" if rc2 == 0 else "FAILED: " + out.strip()}')
    else:
        manifest.append(f'{host}: no run_id directory found ({run_id or "empty"})')

    rc3, _ = run(['ssh', *SSH_OPTS, target,
                  f"journalctl -u 'gp-*' --since '{since}' --no-pager "
                  f'> /tmp/gp_journal.txt 2>&1 || true'])
    run(['scp', *SSH_OPTS, f'{target}:/tmp/gp_journal.txt',
         os.path.join(dest, 'journal.txt')])
    run(['scp', *SSH_OPTS, f'{target}:~/gp_logs/throttled.log',
         os.path.join(dest, 'throttled.log')])
    manifest.append(f'{host}: journal + throttled.log '
                    f'{"OK" if rc3 == 0 else "(journalctl unavailable?)"}')


def collect_laptop(dest: str, manifest: list):
    local_logs = os.path.join(os.path.expanduser('~'), 'gp_logs')
    if not os.path.isdir(local_logs):
        manifest.append('laptop: no ~/gp_logs directory')
        return
    runs = sorted((d for d in os.listdir(local_logs)
                   if os.path.isdir(os.path.join(local_logs, d))), reverse=True)
    if not runs:
        manifest.append('laptop: gp_logs empty')
        return
    src = os.path.join(local_logs, runs[0])
    shutil.copytree(src, os.path.join(dest, runs[0]), dirs_exist_ok=True)
    manifest.append(f'laptop: copied run {runs[0]}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('hosts', nargs='+', help='robot hostnames (robot.local …)')
    ap.add_argument('--user', default='pi')
    ap.add_argument('--since', default='2 hours ago')
    ap.add_argument('--out', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'incidents'))
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    bundle = os.path.join(args.out, stamp)
    os.makedirs(bundle, exist_ok=True)
    manifest: list[str] = [f'collected {stamp} | hosts: {args.hosts} | since: {args.since}']

    for host in args.hosts:
        collect_robot(host, args.user, args.since,
                      os.path.join(bundle, host.replace('.', '_')), manifest)
    collect_laptop(os.path.join(bundle, 'laptop'), manifest)

    with open(os.path.join(bundle, 'MANIFEST.txt'), 'w') as f:
        f.write('\n'.join(manifest) + '\n')
    print('\n'.join(manifest))
    print(f'\nBundle: {bundle}')
    print('Attach this folder to the entry in docs/incident_log.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
