# Low-Latency Person Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Native execution only: the user asked this agent to implement it, and this workspace has no Git repository.

**Goal:** Show a prompt, aligned full-person box on the upper live feed and count a normal walking entry once, with a low-delay camera stream.

**Architecture:** Keep one EMEET camera owner and the `Detector` adapter. Benchmark Arduino's UNO Q `yolox-object-detection` COCO-person candidate before replacing the running backend. Send latest camera frames continuously; drop stale frames and associate detector boxes with capture sequence/time so the upper overlay never presents old results as current.

**Tech Stack:** Python 3.11, Arduino UNO Q/EMEET MJPEG, Arduino App Lab/Edge Impulse YOLOX-Nano candidate, `ThreadingHTTPServer`, browser ES modules, SQLite, pytest, Node tests.

**Spec:** `docs/superpowers/specs/2026-09-26-low-latency-person-dashboard-design.md`

## Global Constraints

- Keep the working Roboflow dashboard running until the candidate is validated and rollback files are prepared.
- Only a `person` detection with a full-body box inside the existing edge gate may count; empty and partial-edge cases must not count.
- No cloud inference or camera-frame upload. Keep all model assets and temporary test frames on the UNO Q or attached drive.
- Targets are ≥10 displayed camera FPS, <300 ms browser frame age, box visible within 0.5 s, box alignment within 10% of person size while walking, count within 1 s. Report measured results rather than claiming unsupported targets.
- The upper feed is the primary box display. A box older than 0.5 s must disappear, and a slow browser client must not cause frame backlog.
- Do not remove the active model or its service until the replacement passes the user-cued walk. Audit exact legacy database/cache targets again before previously authorized deletion.
- No Git repository exists here; record verification in the progress ledger and keep an exact remote rollback archive instead of Git commits.

## Review Focus

- A browser tab paused for seconds reconnects to the newest frame, never replays backlog: Task 2 test.
- The camera restarts or has no frame: stream returns a waiting state and resumes without serving stale JPEG: Task 2 test.
- A person leaves during an inference gap: upper-feed box expires within 0.5 s: Task 4 test.
- A full person appears at the frame edge but not fully visible: no accepted box/event: Task 3 test.
- Two normal walking entries separated by a clear view: count rises twice, not once or three times: Task 5 live test.

---

### Task 1: Benchmark a real person-capable local candidate

**Files:** Create `deployment/benchmark_yolox_person.py`; test `tests/test_benchmark_yolox_person.py`; update `deployment/unoq-verification.json` only after measured success.

**Interfaces:** `summarize_candidate(samples: list[dict]) -> dict` returns p50/p95 latency, effective FPS, detected class set, peak RSS, and box count; the probe's CLI prints only anonymous boxes and numeric metrics. No camera frames or secrets are persisted.

- [ ] **Step 1: Write failing tests** for an empty sample list, person-class detection, percentile calculation, and rejecting output without `bounding_box_xyxy` or equivalent source geometry.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_benchmark_yolox_person.py`; expect a failure from missing implementation.
- [ ] **Step 3: Implement** the small summarizer and a read-only probe against the UNO Q App Lab `yolox-object-detection` model (catalog says UNO Q supported, model path `/models/ootb/ei/yolo-x-nano.eim`). Inspect the actual installed runtime/model API and available root/USB storage before downloading or launching anything. Use a saved anonymous frame from the live `/dev/shm` buffer; do not compete for `/dev/video0`.
- [ ] **Step 4: Run tests and board benchmark** on ≥20 warmed frames, measure p50/p95 and person boxes, and compare with the 0.49 FPS/2.0 s p50 baseline. If candidate cannot produce full-person boxes materially faster, stop the detector cutover and report the measured limit; do not substitute a motion rectangle.

### Task 2: Continuous latest-frame stream

**Files:** Modify `src/retail_counter/camera.py`, `src/retail_counter/web_server.py`, `config.example.json`; test `tests/test_camera.py`, `tests/test_web_server.py`.

**Interfaces:** The camera owner atomically publishes `/dev/shm/retail-edge-live.jpg` plus a `live-meta.json` sidecar with `sequence`, `captured_at`, and JPEG file mtime. `read_live_snapshot(jpeg_path: Path, metadata_path: Path) -> tuple[bytes, dict] | None` in the separate web process returns a consistent pair or `None` when stale/mismatched. `/api/live.mjpg` emits multipart JPEG frames with `X-Frame-Sequence` and `X-Captured-At` part headers; each client always gets the newest frame.

- [ ] **Step 1: Add failing tests** for sequence monotonicity, late client receiving the latest JPEG, no stale frame after camera timeout, and clean disconnect.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_camera.py tests/test_web_server.py`; expect targeted failures.
- [ ] **Step 3: Implement** a 15-FPS live-file publisher, atomic sidecar, consistent file-pair reader, and streaming handler. Preserve `/api/frame.jpg` as rollback path. Bound per-client waiting and never queue multiple old frames. The web server must not open `/dev/video0` or rely on an in-process camera object.
- [ ] **Step 4: Run tests** and locally probe multipart headers and 10-second byte/sequence cadence without changing the browser yet.

### Task 3: Adapt the faster detector and preserve full-body counting

**Files:** Create `src/retail_counter/yolox_detector.py`; modify `src/retail_counter/detector.py`, `src/retail_counter/app.py`, `config.example.json`; test `tests/test_detector.py`, `tests/test_presence.py`, `tests/test_person_gate.py`.

**Interfaces:** `YoloxPersonDetector(Detector)` converts candidate boxes to `Detection(xyxy, confidence, class_id=0)` in 1280×720 camera coordinates. `create_detector(settings)` accepts `backend="yolox_local"` only after Task 1 passes; other backends remain unchanged for rollback. App status includes `detection.frame_sequence` and `detection.captured_at`.

- [ ] **Step 1: Add failing tests** for person-only parsing, scaled box coordinates, missing/invalid coordinates, cropped body rejection, and one event despite repeated detections.
- [ ] **Step 2: Run** targeted pytest files; expect failures.
- [ ] **Step 3: Implement** the adapter for the verified candidate API, reusing the existing full-person gate and presence counter. Configure only the chosen local runtime; do not change the live service yet.
- [ ] **Step 4: Run** targeted tests and a shadow probe on the board. Confirm no camera resource conflict, healthy memory, and no extra event database writes.

### Task 4: Fast upper-feed boxes with freshness control

**Files:** Modify `web/app.js`, `web/person-overlay.mjs`, `web/index.html`, `web/styles.css`; test `web/tests/person-overlay.test.mjs`.

**Interfaces:** `personOverlayModel(status, frameMetadata, nowMs)` returns boxes only when their detection age is ≤500 ms and the image dimensions/sequence match the current stream epoch. Browser parses `/api/live.mjpg` part headers using a streaming `fetch`, draws each JPEG to a canvas, and associates its sequence/capture time with current boxes; JPEG polling remains an error fallback. The two most recent detector boxes may extrapolate motion only inside the 500-ms freshness window. Count updates as soon as fresh status arrives.

- [ ] **Step 1: Add failing Node tests** for moving box coordinates, stale-result expiry, wrong stream epoch, and no box on empty/partial result.
- [ ] **Step 2: Run** `node --test web/tests/person-overlay.test.mjs`; expect targeted failures.
- [ ] **Step 3: Implement** synchronized upper-feed overlay and continuous image parsing. Update UI copy to show measured camera/detector ages; the expandable analyzed still image is not treated as live.
- [ ] **Step 4: Run** Node tests and verify box-layer geometry against the actual 1280×720 stream in a browser.

### Task 5: Staged deployment and live walk verification

**Files:** Update `deployment/unoq-verification.json`, `README.md`, and `docs/superpowers/plans/2026-09-26-low-latency-person-dashboard-progress.md`.

**Interfaces:** Service configuration retains a rollback command/backup to the prior Roboflow backend. New event namespace is used if detector semantics change; old and current events are not silently reset.

- [ ] **Step 1: Run full local tests** (`python -m pytest -q` and `node --test web/tests/*.test.mjs`) and config check; inspect the exact diff since this is not a Git checkout.
- [ ] **Step 2: Back up exact remote files**, deploy the candidate and stream behind a reversible config switch, then measure camera FPS/age, detector p50/p95, and RSS/temperature on the board.
- [ ] **Step 3: Ask the user to keep the view empty, then walk normally through fully visible, leave, and enter once more. Verify box placement in the upper feed, count progression, no empty-scene boxes, and re-arm; ask for their direct visual confirmation.
- [ ] **Step 4: If any acceptance condition fails, restore the prior service and dashboard and report the shortfall. If it passes, update measured verification and then perform the separately approved exact-target legacy cache/event purge, preserving the new detector's events.
