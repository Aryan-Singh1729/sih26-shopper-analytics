# Queue and Footfall Management

A local retail analytics prototype with live person detection, entrance footfall
tracking, and checkout queue monitoring. An EMEET camera connected to an Arduino
UNO Q supplies video; the laptop runs person detection and serves the dashboards.

## Dashboards

- **Store footfall — `http://localhost:8081`**: live camera feed with person boxes,
  arrival counts, hourly arrivals, and busiest-hour reporting.
- **Checkout queues — `http://localhost:8082`**: the shared live feed, waiting
  counts for two counters, individual waiting timers, average waiting times,
  congestion estimates, and staffing suggestions.

The two dashboards have different counting rules. Footfall counts an appearance
once and counts a later return again. Queue monitoring shows people currently
visible, not a running total of everyone who has appeared.

## Queue alerts

Alerts are evaluated **per counter**, not by combining separate queues:

- **0–1 people:** no congestion alert.
- **2 people:** brown caution.
- **3 or more people:** red alert.

Two people at the left counter and one at the right therefore produce a brown
alert, not a red one. The banner names the counter needing attention.

## Current implementation

The active laptop detector is **MediaPipe Object Detector with EfficientDet-Lite0
int8**. OpenCV KCF trackers keep person boxes moving between detector results.
Older detector adapters remain in the source, but they are not the current
laptop dashboard detector.

The queue demo currently treats everyone visible as waiting and divides the
image into left and right counter areas. A brief tracking grace preserves
waiting-time continuity without counting missing tracks as visible people.
Current average waiting time updates while people remain in view; completed
waiting visits contribute to the completed average when they leave.

Service timing is **not configured** in this demo. Actual waiting and service
zones can be enabled once a real checkout layout is available. Congestion
forecasts use an explicitly configured service-time assumption until measured
service samples exist; they are estimates, not guaranteed predictions.

## Run the prepared deployment

Requirements: Python 3.11+, MediaPipe, OpenCV with contrib trackers, NumPy,
Pillow, the local detector model, and a reachable board camera service. Model
files and the local Python runtime are intentionally excluded from Git.

From the repository root, start the footfall dashboard:

```powershell
python deployment/footfall_dashboard.py --port 8081
```

In another terminal, from the repository root, start queue monitoring:

```powershell
python deployment/queue_dashboard.py --port 8082
```

The expected model location is `models/person/efficientdet_lite0.tflite`.
The board's default camera/history address is `http://10.143.116.243:8080`;
the footfall server accepts `--board` to use a different address. Queue monitoring
depends on the footfall server's shared video and person-track feed.

See [footfall deployment notes](deployment/FOOTFALL-DASHBOARD.md)
and [queue deployment notes](deployment/QUEUE-DASHBOARD.md)
for configuration and live-verification details. Both dashboards currently
share one camera; monitoring separate entrance and checkout locations requires
another camera.

## Tests

From the repository root, with the required Python dependencies installed:

```powershell
python -m pytest tests -q
node --test tests/queue_alerts.test.mjs
```

## Privacy and limitations

Processing is local, with no face recognition or identity matching. Video is
not recorded. Footfall events are stored locally; queue timing samples are
session-only. Secrets, runtime databases, model files, and local repair archives
are excluded from version control. Legacy Roboflow components read credentials
from `ROBOFLOW_API_KEY`; credentials must never be committed.

This is a prototype: lighting, occlusion, camera movement, and tracking errors
can affect counts and waiting-time measurements. Live tests are required for
the intended camera angle and checkout layout.
