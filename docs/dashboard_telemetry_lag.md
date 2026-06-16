# Dashboard map / ultrasonic lag — but camera is smooth

## Symptom
The console's **map robot pose** and the **PROXIMITY (ultrasonic) readout**
trail real motion by seconds (up to ~10 s) and feel "wrong/delayed", **yet the
camera stream stays smooth and low-latency**. The lag often grows the more you
restart the dashboard during a session.

## Root cause: orphaned YOLO worker processes (laptop CPU starvation)
`dashboard_qt/main.py` runs YOLO in a **separate child process**
(`multiprocessing` `spawn`). If you stop the dashboard by killing only the
`main.py` process, the **YOLO worker is left orphaned and keeps spinning**.
Each relaunch leaves another zombie behind. After a dozen relaunches the
laptop CPU is saturated by zombie workers, which **starves the Qt UI thread**.

Why only telemetry lags and not video: the map / fleet cards / ultrasonic
readout are rendered on the **UI thread**, so they starve first. The camera
display path is **decoupled** (it blits the raw JPEG immediately), so it keeps
looking fine — which makes the problem masquerade as a telemetry-code bug that
"keeps coming back."

## Diagnosis (do this FIRST, before touching code)
Count the python processes — one running dashboard should be ~2 (main + one
YOLO worker):

```powershell
Get-Process python | Select-Object Id, CPU, @{n='Threads';e={$_.Threads.Count}}
```

Many python processes (10+), each with 30 threads and large CPU-seconds =
orphaned workers. That is the problem, not the telemetry pipeline.

## Fix
Kill the **whole** python tree, then launch ONE clean instance:

```powershell
Get-Process python | Stop-Process -Force
```
```bash
python dashboard_qt/main.py        # real robots
```

Confirm only ~2 python processes remain afterward. Map + ultrasonic track in
real time again.

## Prevention
- When relaunching the dashboard, **always kill the full python tree**, never
  just the `main.py` process — spawn children do not die with the parent.
- `--no-ai` avoids spawning the YOLO worker entirely (no zombie risk) if you
  don't need detection while debugging.

## Real rendering fixes that ARE in the code (keep them)
These are legitimate and unrelated to the zombies — they bound telemetry
latency under load:
- **Telemetry coalescing** — `dashboard_qt/transport/zmq_link.py`
  (`_drain_telemetry` emits only the newest pose per drain).
- **Latest-frame render timer** — `dashboard_qt/ui/main_window.py`
  (`_render_telemetry`, 30 Hz; telemetry is NOT rendered per-frame anymore).
- **Band-cached proximity restyle** — `dashboard_qt/ui/ops_panel.py`
  (`set_ultrasonic` only calls the expensive `setStyleSheet` on a colour-band
  change, not every frame).
