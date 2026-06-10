# Incident Log

One entry per failure observed during testing or demos. Newest on top.
Pull logs with `python tools/collect_logs.py <robot>` and reference the bundle path.

Template:

```markdown
## YYYY-MM-DD HH:MM — <one-line symptom>
- **Robot / component:** robot1 | robot2 | robot3 | dashboard | network
- **run_id:** (from dashboard header or ~/gp_logs/<run_id>/)
- **What was happening:** (teleop / autonomous / idle, who was driving)
- **Observed:** (exact symptom, duration, what recovered it)
- **Log bundle:** incidents/<timestamp>/ (from collect_logs.py)
- **Suspected cause:**
- **Follow-up:** (fix landed? issue #? retest date?)
```

---

(no incidents recorded yet)
