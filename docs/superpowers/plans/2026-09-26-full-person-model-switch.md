# Full-Person Model Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the live head detector with exact `person-detection-euioa/1`, count only complete people inside the image, and show full-person boxes; purge old-model events and cache after validation.

**Architecture:** Keep the existing camera, self-hosted Roboflow Inference server, detector adapter interface, presence counter, SQLite store, and dashboard. Make model ID/class configurable within the adapter, replace head acceptance with a full-person gate, and give new person events their own camera ID suffix. Validate the model on the board before cutting over; restore the old service if live checks fail.

**Tech Stack:** Python 3, Pillow, NumPy, pytest, browser JavaScript modules, Node test runner, systemd, Roboflow Inference on Arduino UNO Q.

**Spec:** `docs/superpowers/specs/2026-09-26-full-person-model-switch-design.md`

## Global Constraints

- Exact model ID: `person-detection-euioa/1`; exact expected response class: `person`.
- Use self-hosted Inference at `127.0.0.1:9001`; do not use the generic Free Person Detection API or another model.
- Read `ROBOFLOW_API_KEY` only from `/home/arduino/.config/retail-edge/secrets.env` on the board. Never print or commit it.
- Cache models on `/mnt/retail-data/roboflow-cache`; leave the old cache intact through verification.
- Count only a complete person wholly inside the fixed 1280×720 image; start new-model arrivals at zero and purge old-model events after live validation.
- Keep the independent 5-FPS camera refresh. Continuous tracking between model results is out of scope.
- This checkout has no `.git`; replace planned commit steps with a local file inventory and test evidence, without initializing a repository.

## Review Focus

- Empty predictions: parser returns `[]`, and no arrival is recorded (Tasks 2 and 3).
- Unexpected `head` or other class: adapter rejects it rather than counting it as `person` (Task 2).
- A box touching only one image edge: full-person gate rejects it (Task 3).
- A model dropout while the person remains in the scene: presence counter must not re-arm or double-count (Task 3).
- A stale status or camera disconnect: browser overlay clears instead of showing a previous person box (Task 4).

---

### Task 1: Validate exact model on UNO Q without cutover

**Files:**
- Create: `deployment/probe_person_model.py`
- Test: `tests/test_probe_person_model.py`

**Interfaces:**
- Produces: `probe_model(jpeg: bytes, base_url: str, model_id: str, api_key: str) -> dict` in `deployment/probe_person_model.py`; its CLI reads the key from the environment and logs only model ID, HTTP status, class names, box count, and latency.

- [ ] **Step 1: Write the failing test** for a successful predictions payload, an unavailable server, and no API key; assert that output and errors never contain the key.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_probe_person_model.py`; confirm the missing probe function fails.
- [ ] **Step 3: Implement the probe** using base64 JPEG and board-local HTTP, with the key read from the environment and never passed as a command-line argument. Never log the request URL.
- [ ] **Step 4: Run** `python -m pytest -q tests/test_probe_person_model.py`; confirm all cases pass.
- [ ] **Step 5: Run the probe on the board** against exact `person-detection-euioa/1` while the old counter stays live. Confirm a successful predictions list, cache directory on the USB drive, model load, and measured latency. Use a person-in-view frame to confirm class `person`; an empty frame alone is insufficient. If loading fails, stop without cutover.

### Task 2: Generalize detector adapter for the new model

**Files:**
- Modify: `src/retail_counter/detector.py`
- Modify: `config.example.json`
- Modify: `tests/test_detector.py`

**Interfaces:**
- Consumes: Roboflow HTTP predictions list verified in Task 1.
- Produces: `RoboflowInferenceDetector` with configured `model_id="person-detection-euioa/1"` and `expected_class="person"`; `infer_jpeg(jpeg: bytes, width: int, height: int) -> list[Detection]` remains the adapter interface.

- [ ] **Step 1: Write failing tests** for exact model metadata, one `person` prediction converted to clipped XYXY, empty predictions, and rejection of `head`-only output.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_detector.py`; confirm the old hard-coded model/class fails the new cases.
- [ ] **Step 3: Make model ID and expected class explicit settings** in the adapter; set their configured values to the exact new model/class. Preserve environment-only credentials and generic detector interface.
- [ ] **Step 4: Run** `python -m pytest -q tests/test_detector.py` and `PYTHONPATH=src python3 -m retail_counter --config config.example.json --check-config`; confirm pass.

### Task 3: Accept complete people and create a fresh counter namespace

**Files:**
- Modify: `src/retail_counter/app.py`
- Modify: `src/retail_counter/presence.py`
- Modify: `src/retail_counter/scene.py` only if the existing empty-scene region misses the verified path
- Modify: `tests/test_head_boxes.py` into person-gate tests
- Modify: `tests/test_presence.py`

**Interfaces:**
- Consumes: Task 2 `Detection` boxes for class `person`.
- Produces: `filter_person_detections(raw_detections: list[Detection], jpeg: bytes, frame_width: int, frame_height: int, detection_roi: tuple[float,float,float,float], scene: SceneMonitor, edge_margin: float) -> list[Detection]`; status `detection.persons`, `detection.boxes` with `class: "person"`.

- [ ] **Step 1: Write failing tests** for a whole-person box away from all edges, each of four edge-touching boxes, a static-background proposal, empty detections, one arrival while present, no duplicate after model dropout, and re-arm after a clear view. Assert the new `:presence-person-v1` camera ID creates a zero snapshot without deleting old events.
- [ ] **Step 2: Run** `python -m pytest -q tests/test_head_boxes.py tests/test_presence.py`; confirm failures caused by old head filtering and camera ID.
- [ ] **Step 3: Implement the full-person gate** with `camera.full_person_edge_margin=0.02` as the initial normalized margin on all four image edges; apply the existing normalized ROI to the box center only. Calibrate the margin against live frames; remove the head width/height rule. Keep empty-scene comparison and arrival-on-presence semantics. Emit person-specific status and a new camera ID suffix.
- [ ] **Step 4: Run** the focused tests and then `python -m pytest -q`; confirm pass.

### Task 4: Show full-person results in dashboard and preview

**Files:**
- Modify: `web/head-overlay.mjs` (rename to `web/person-overlay.mjs` if imports/tests move together)
- Modify: `web/app.js`, `web/index.html`
- Modify: `src/retail_counter/preview.py`, `src/retail_counter/web_server.py`
- Modify: `web/tests/head-overlay.test.mjs`, `tests/test_preview_label.py`, `tests/test_web_server.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 3 `detection.persons` and `class: "person"` boxes.
- Produces: upper-feed overlay and exact analyzed-frame preview labeled `PERSON`; model card shows `person-detection-euioa/1` and class `person`.

- [ ] **Step 1: Write failing browser/Python tests** for accepted `person` box placement, rejection of non-person/stale boxes, zero/one/multiple-person badges, exact model metadata, and preview label.
- [ ] **Step 2: Run** `node --test web/tests/*.test.mjs` and `python -m pytest -q tests/test_preview_label.py tests/test_web_server.py`; confirm old `head` contracts fail.
- [ ] **Step 3: Update dashboard, preview, and documentation** to consume person-specific status and label full-body boxes. Do not change the camera refresh rate or misrepresent a stale box as live tracking.
- [ ] **Step 4: Run** all Node and Python tests and check that no user-visible head-model ID or class remains in the deployed page.

### Task 5: Deploy, benchmark, and live-verify with rollback ready

**Files:**
- Modify: `deployment/unoq-verification.json` with new measured results only after validation
- Deploy: tested project files to `/home/arduino/retail-entrance-counter`

**Interfaces:**
- Consumes: Tasks 1–4 and a camera view with a fixed empty-scene reference.
- Produces: running person-model counter, new count at zero, and recorded hardware results.

- [ ] **Step 1: Capture exact backup paths** for old project files/config and verify the existing service is active; do not delete the old model cache or database rows before live validation.
- [ ] **Step 2: Sync tested files and restart only the counter/web services needed.** Verify active services, exact model/class in `/api/status`, camera JPEG, and parsed boxes.
- [ ] **Step 3: Measure** at least ten post-warmup inferences: p50/p95 latency, effective FPS, memory, and detection classes. Record observed values, not advertised model metrics.
- [ ] **Step 4: Ask the user for live states in order:** empty view; partial body at one edge; complete head-to-feet person; sustained presence; departure; second arrival. Check accepted boxes and count at each state, including zero false positives in the observed empty interval.
- [ ] **Step 5: If any acceptance/counter requirement fails, restore the previous service files/config** from the verified backup and report the failure. Otherwise retain the new model and proceed to Task 6.

### Task 6: Purge the old model and its history after successful cutover

**Files:**
- Modify: `deployment/unoq-verification.json` to replace old-model verification data
- Create: `src/retail_counter/purge_legacy.py`, `tests/test_purge_legacy.py`
- Remove: old-model-only cache directory under `/mnt/retail-data/roboflow-cache` and temporary backups made in Task 5
- Modify: SQLite `crossing_events` rows whose inspected camera IDs belong to the old model
- Audit: `src/`, `web/`, `tests/`, `deployment/`, `README.md`, service units, and temporary probe files for old-model references

**Interfaces:**
- Consumes: Task 5 live validation and exact read-only inventory of cache paths and event camera IDs.
- Produces: `purge_legacy_events(connection: sqlite3.Connection, legacy_camera_ids: set[str]) -> int`; no old-model weights or events, a healthy new-model service, and unchanged new-model event rows.

- [ ] **Step 1: Inspect exact targets read-only.** Resolve the old cache directory under the mounted USB drive; enumerate SQLite camera IDs and counts; list temporary backups and old-model-only files. Confirm every deletion target is inside the intended directory and is not the new model cache.
- [ ] **Step 2: Write a failing database purge test** in `tests/test_purge_legacy.py` using a temporary SQLite fixture with old and new camera IDs; assert only old rows are removed and new rows remain. Run it red, implement the helper in `src/retail_counter/purge_legacy.py`, then run it green.
- [ ] **Step 3: Stop the counter briefly, purge only identified old-model rows, checkpoint/truncate WAL, and vacuum.** Verify old-row count zero and new-row count unchanged before restart.
- [ ] **Step 4: Remove the exact old-model cache path and old-only temporary artifacts.** Do not remove the generic Inference Docker image or unrelated model caches. Remove stale old-model IDs from active code, configuration, dashboard, documentation, tests, and verification output.
- [ ] **Step 5: Restart/verify the new service and dashboard**; check the exact new model/class, new count, camera frame, cache path, old-event count zero, and absence of old-model files/references. Report that deleted weights/events are not recoverable from this deployment.
