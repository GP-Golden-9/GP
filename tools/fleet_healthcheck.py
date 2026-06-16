#!/usr/bin/env python3
"""Ad-hoc fleet health check over SSH (password auth).

Not committed config; uses team creds passed in-script for a one-off check.
Run: python tools/fleet_healthcheck.py
"""
import sys
import paramiko

ROBOTS = [
    {"id": "robot1", "name": "Alpha", "ip": "192.168.1.200", "unit": "gp-robot1",
     "devs": ["/dev/rplidar", "/dev/mega"]},
    {"id": "robot2", "name": "Beta", "ip": "192.168.1.203", "unit": "gp-robot2",
     "devs": ["/dev/mega"]},
]
USER, PASSWORD = "muc", "muc"

CHECKS = [
    ("uptime / load",        "uptime"),
    ("temp",                 "vcgencmd measure_temp 2>/dev/null || echo n/a"),
    ("throttled flags",      "vcgencmd get_throttled 2>/dev/null || echo n/a"),
    ("disk free /",          "df -Pm / | awk 'NR==2{print $4\" MB free\"}'"),
    ("serial devices",       "ls -l /dev/rplidar /dev/mega 2>&1"),
    ("service active?",      "systemctl is-active {unit}"),
    ("service enabled?",     "systemctl is-enabled {unit} 2>/dev/null"),
    ("discovery active?",    "systemctl is-active gp-discovery 2>/dev/null || echo n/a"),
    ("gateway ports LISTEN", "ss -ltn 2>/dev/null | grep -E ':(555[6-9]|5560)' || echo none"),
    ("ROS nodes (localhost)","source /opt/ros/humble/setup.bash 2>/dev/null; "
                             "timeout 6 ros2 node list 2>/dev/null | sort | tr '\\n' ' ' || echo 'n/a'"),
    ("recent unit log",      "journalctl -u {unit} -n 12 --no-pager 2>/dev/null | tail -12"),
]


def run(client, cmd, timeout=20):
    try:
        _in, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace").strip()
        e = err.read().decode("utf-8", "replace").strip()
        return o if o else (e if e else "")
    except Exception as ex:  # noqa
        return f"<exec error: {ex}>"


def check(robot):
    print("=" * 64)
    print(f"{robot['name']} ({robot['id']}) @ {robot['ip']}  unit={robot['unit']}")
    print("=" * 64)
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(robot["ip"], username=USER, password=PASSWORD,
                    timeout=10, allow_agent=False, look_for_keys=False)
    except Exception as ex:  # noqa
        print(f"  SSH CONNECT FAILED: {ex}\n")
        return
    for label, cmd in CHECKS:
        out = run(cli, cmd.replace("{unit}", robot["unit"]))
        first = out.splitlines() or [""]
        if len(first) <= 1:
            print(f"  {label:22}: {out}")
        else:
            print(f"  {label:22}:")
            for ln in first:
                print(f"      {ln}")
    cli.close()
    print()


if __name__ == "__main__":
    for r in ROBOTS:
        check(r)
