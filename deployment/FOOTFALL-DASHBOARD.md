# Separate footfall dashboard

Open http://localhost:8081 on this PC: camera, live full-person boxes, per-person
arrivals and hourly footfall now share this one dashboard. The board's port
8080 remains its internal camera/status/history source. Queue monitoring is on localhost:8082.

Run from the repository root:

```powershell
python deployment/footfall_dashboard.py --port 8081
```

The dashboard server binds to 127.0.0.1, reads the board's `/api/footfall`
endpoint for archived events. New arrivals are saved in the laptop's
`data/laptop-visual-arrivals.sqlite3` by the same tracks that draw the visible boxes.
The board must use `doorway.counting_mode: external_visual` to prevent double counting.
One visible person counts once; disappearance for at least one second after their
box clears re-arms that visit. Returning counts again, including the same person.
Short dropouts are tolerated. Multiple separate boxes create separate arrivals.
The PC and board must be reachable. History refreshes on count changes and every
five seconds, and retains visibly marked stale data
if the board is unreachable. The clock uses Asia/Calcutta.

Metrics: selected-date total arrivals, hourly buckets, all tied busiest hours,
current-hour arrivals (today only), and last arrival. Existing demo entries
are included. Old counting namespaces and exits are excluded.

The active detector is PC MediaPipe Object Detector / EfficientDet-Lite0 int8,
person-only, up to 30 detections. Loopback SSH forwarding uses board port 9011.
Anonymous per-person tracks count groups and additional arrivals; saved history
is preserved. The laptop dashboard now owns a separate MediaPipe detector and
OpenCV KCF trackers and burns boxes directly into the output JPEG frames.
There are no browser overlay timing gates or entrance ROI filters on these boxes.
The laptop captures the board's stream once, keeps only a bounded in-memory
history, and skips intermediate frames when inference is busy. Tracking never
creates new persons without a detector result; lost tracks expire after 1.2s.
Preview is 640x360 to reduce network backlog; original capture remains 1280x720.
No face recognition or cloud inference. Reboots require starting the PC processes
and reconnecting the SSH tunnel. Real-world group/occlusion tests remain required;
anonymous tracking can switch IDs, and a fully-visible box does not prove feet
are unobscured. Counts are not unique identified customers.
