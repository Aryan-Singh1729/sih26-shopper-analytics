# Retail Entrance Counter

> Historical board-only guide. See [the current overview](../README.md) and
> [deployment notes](../deployment/FOOTFALL-DASHBOARD.md) for the active laptop dashboards.

An offline, anonymous entrance-counting service for the 2 GB Arduino UNO Q.

The application captures the EMEET UVC camera through the board's existing
FFmpeg/V4L2 stack, calls a self-hosted Roboflow Inference server for the exact
`person-detection-euioa/1` model, and records an arrival when a complete
person appears after the camera view has been clear. Anonymous arrival events
are stored in SQLite.

## Safety and privacy defaults

- No face recognition, embeddings, names, or persistent track IDs.
- Camera frames are processed locally. One live JPEG is kept in RAM and replaced
  as new camera frames arrive. No video is recorded.
- The dashboard displays arrivals, not doorway crossings or occupancy.
- The camera reader keeps only the newest frame, preventing latency buildup.

## Required deployment inputs

The self-hosted server must cache and load exact model version 1 before the
camera process starts. Both processes read `ROBOFLOW_API_KEY` from their
environment; the key is never stored in this repository. Do not substitute a
different detector.

The example configuration uses the external USB drive at `/mnt/retail-data` for
the model and test clips. SQLite remains on the internal ext4 home partition;
the attached FAT32 drive is not appropriate for durable SQLite WAL locking.
The exact model recognizes the `person` class, not faces specifically. Detection
depends on camera angle, lighting, and the model's training data.

## Live dashboard

The dependency-free dashboard is served by `retail-entrance-web.service` on
port 8080. It displays the current EMEET camera frame, arrivals, latest person
detections, model health, and edge performance. The browser refreshes the
camera image independently of the slower model inference. The camera also holds
one changed-scene frame while inference is busy so a short visit can be checked
by the model afterward. Green `PERSON` boxes on the live view show the latest
accepted model result and may briefly lag the current camera frame; the
expandable detection image shows the box on the exact analyzed frame. Arrival counting
uses a low-resolution reference of the empty, fixed camera view to decide when
someone has left; a brief missed model detection does not re-arm the counter.
Each proposed person box must stay clear of all four image edges, have its
center in the counting area, and differ from that empty reference. This is an
approximation of complete head-to-feet visibility and does not guarantee that
the model will never produce a false positive. The new model uses a separate
counter namespace, so historical arrivals do not affect its total.

Capture the empty-scene reference with nobody in view after fixing the camera
in its final position:

`PYTHONPATH=src python3 -m retail_counter.scene --source /dev/shm/retail-edge-live.jpg --output data/empty-scene.npy`

Recalibrate whenever the camera angle or surrounding scene changes. The saved
reference is a 160×90 grayscale array rather than a full camera image.

## Local verification

Run `pytest` from this directory. Configuration can be validated with:

`python -m retail_counter --config config.example.json --check-config`

The live process writes an atomic status JSON file, a single replace-on-write
RAM camera frame, and an SQLite WAL database. It does not record video.
