# Low-latency person dashboard design

Date: 2026-09-26. Status: awaiting user review. This workspace has no Git repository, so the spec cannot be committed here.

## Goal and acceptance

The upper, primary dashboard camera view should show a smooth, low-delay EMEET feed with a clearly visible box covering the whole person while they walk through, plus exactly one new arrival for each fully visible pass. The box's speed, alignment, and persistence during motion are the highest-priority acceptance criteria; a fast camera image with a delayed, frozen, or hidden box is a failure. Model identity is not a requirement; processing should remain local to the UNO Q if it can meet the targets. Partial people and empty scenery must not count. Camera position stays fixed during calibration and tests.

Measured starting point: MJPEG capture is 1280×720 at 30 FPS, but dashboard delivery is repeated JPEG polling nominally at 5 FPS. Self-hosted `person-detection-euioa/1` processes about 0.49 FPS, p50 inference near 2.0 seconds and p95 end-to-end near 4.9 seconds. A person can cross between analyzed frames. Browser box data is polled every 2 seconds. These measurements, not camera capture rate, explain the delay.

Targets to verify on the actual board: at least 10 displayed camera FPS, less than 300 ms camera age at the browser, a full-person box in the upper feed within 0.5 seconds of a fully visible person, box alignment within 10% of person width/height while walking, and one count within 1 second during a normal walking pass. Box state must expire within 0.5 seconds of a confirmed departure. These are targets, not promised results; the UI must show measured latency and must never claim “real time” if they are not met. Test empty, partial-edge, full-body walking, departure, and second arrival with the user. Ask the user whether the moving box looks aligned and prompt on each test transition.

## Considered approaches

1. Retune or buffer the current Roboflow model: smallest change, but its measured 2-second inference cannot provide prompt boxes for a quick pass. Buffering can produce a delayed count, not an immediate one. Reject as the primary path.
2. Use a lightweight, pre-trained local COCO person detector (Arduino's UNO Q live object-detection stack is the first candidate), benchmark it before cutover, then adapt its boxes to the existing `Detector` interface. Chosen. Reject candidates that lack box coordinates, fail on a whole person at the door, or do not materially improve latency.
3. Offload inference to another computer or cloud accelerator: possible speed fallback, but changes privacy, reliability, and deployment scope. Do not take this path without a separate user decision if local benchmarks miss targets.

## Components and data flow

One camera owner captures EMEET frames and timestamps them with a monotonically increasing sequence. Avoid competing processes opening `/dev/video0`. The dashboard receives a continuous multipart MJPEG stream (or an equivalent continuous browser transport if MJPEG proves incompatible) from a latest-frame buffer; slow clients drop old frames instead of building a backlog. Do not expose the stream publicly beyond the current LAN binding.

The detector remains behind `Detector.infer`/`infer_jpeg`, returning `Detection` objects in original camera coordinates. A candidate benchmark runs on the board without disturbing the running Roboflow service. Once a person-capable candidate is validated, the counter consumes its per-frame results and retains the full-body edge gate, empty-scene rejection, and one-arrival-until-clear rule. Detector output records frame sequence and capture time. The upper-feed overlay associates boxes with that sequence and tracks between detector results for at most 0.5 seconds; stale boxes disappear rather than sticking to doors or people who have left. The dashboard displays capture age, detector age, effective inference FPS, and current count. The expandable analyzed image remains optional and is not the primary box display.

The stream and detection workers must share the camera buffer. A fast camera path must not wait on inference; inference takes the newest eligible frame and discards stale queued work. Events remain in SQLite under a fresh detector-version namespace only if a backend switch changes counting semantics. Historical new-model events remain untouched unless the user explicitly asks to reset them. Credentials never enter client code, logs, or model metadata.

## Rollout and failure handling

First benchmark candidate model startup, memory, p50/p95 latency, person-class output, and boxes on empty/occupied frames. If no local candidate is sufficiently faster, keep the current dashboard and report the hardware limit; do not switch to a motion rectangle mislabeled as person detection. Implement the continuous stream and time-aligned overlay behind existing HTTP endpoints so the live dashboard has a reversible fallback. Run unit tests for frame dropping, box-to-frame mapping, stale-box expiry, and count re-arm. Deploy a backup of changed files, smoke-test the stream and counter, then perform user-cued live walking tests. Restore the prior service and web files if the feed or counter regresses.

The previously approved legacy Roboflow cache/event cleanup is separate. Finish only after the active detector is verified and exact deletion targets have been audited again.
