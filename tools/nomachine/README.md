Remote access profiles for the robot Raspberry Pis (NoMachine).

- robot1.nxs / robot2.nxs — connection profiles; open with the NoMachine client.
- If a Pi's remote desktop is black/frozen, restart its display manager:
      ssh pi@robotN.local 'sudo systemctl restart lightdm'
