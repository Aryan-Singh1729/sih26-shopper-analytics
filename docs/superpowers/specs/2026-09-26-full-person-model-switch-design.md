# Full-person model switch

## Outcome

Replace the legacy head detector with the exact public Roboflow
Universe version `person-detection-euioa/1`. The detector must report the
`person` class and draw the full-person model box. Count one arrival only after
a complete person is visible inside the fixed EMEET camera frame. Keep the
5-FPS camera refresh and local-only self-hosted inference. Start the new model's
arrival total at zero. After the new model passes live validation, delete the
historical head-model events and old model cache, as explicitly requested.

This switch does not add continuous box tracking between model results. The
dashboard must distinguish the latest analyzed result from the faster camera
view and must not imply that a stale box is a fresh detection.

## Model validation before cutover

Use the existing board-local Roboflow Inference server and the API key from
`/home/arduino/.config/retail-edge/secrets.env`. Never print, copy into source,
or commit the key. Send a camera frame to the exact model ID, verify that its
weights cache on `/mnt/retail-data/roboflow-cache`, that inference loads, and
that the response contains a predictions list with class `person`. Benchmark
latency and effective FPS on the UNO Q. If loading fails, keep the old live
service unchanged and report the error.

## Application changes

- Generalize the existing detector adapter's configured model ID and expected
  class. Configure exactly `person-detection-euioa/1` and `person`; reject any
  other class in this deployment. Keep the adapter interface usable for a later
  ONNX or TensorRT backend.
- Replace the head-specific width/height heuristic with a full-person gate.
  An accepted person's box center must be inside the configured counting area, stay
  clear of all four image edges by an initial 2% normalized margin (calibrated
  with live frames), and differ from the
  fixed empty-scene reference. An edge-touching or clipped box may appear as a
  raw model result but must not increment arrivals or appear as an accepted
  dashboard box. A box inside the image is only an approximation of whole-body
  visibility; the live test must also visually confirm head-to-feet coverage.
- Keep arrival-on-presence behavior: one event after a valid full-person
  detection, then re-arm only after the fixed view has been clear for the
  existing duration. Use a new event camera ID suffix for this model so the
  dashboard starts at zero before historical rows are purged.
- Change status fields and dashboard consumers from head-specific counts and
  boxes to person-specific data. The model card must show the new exact model
  ID, expected class, and measured runtime. The preview image labels accepted
  full-person boxes as `PERSON`.

## Verification and cutover

Write tests for the exact model/class parser, full-person edge gate, empty
scene rejection, one-arrival/re-arm behavior, dashboard box mapping, and fresh
event namespace. Run the full local suite and configuration validation. On the
board, verify model cache/load and sample output before restarting the counter.
After cutover, test with the user in three states: empty view (zero accepted
boxes), partial body at an edge (no count), and complete head-to-feet body in
view (one full-body box and exactly one increment while present). Then confirm
the box clears after departure and the counter re-arms. Record FPS, latency,
memory, and any misses or false positives observed; do not claim perfect
accuracy.

Keep the old model cache and a temporary code/config backup until live checks
pass. If the new model cannot load, is too slow for arrivals, or fails the live
checks, restore the old service and report the unresolved issue. Only after the
new model passes, inspect the exact cache path and SQLite camera IDs, remove
old-model events, checkpoint and vacuum the database, remove the old model
cache and temporary backups, and verify no old model files or active references
remain. Do not remove unrelated caches, new-model events, or the generic
Inference server image. Deleted historical events and weights cannot be
recovered from this deployment. Do not silently swap in the generic Free
Person Detection API or another model.
