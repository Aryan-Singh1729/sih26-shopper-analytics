# SDD ledger — plan: docs/superpowers/plans/2026-09-26-full-person-model-switch.md

Status: resumed at the user's request on 2026-09-26. Live cutover is active; final re-arm test and legacy cleanup remain.

Ruling: This checkout has no Git repository, so implementation is in-place and no worktree, commits, or Git-dependent SDD scripts are available. Cost if wrong: changes lack Git rollback; preserve remote service and backup before cutover.

Task 1: Local probe tests passed (3/3). Exact `person-detection-euioa/1` returned HTTP 200 with a predictions list on the UNO Q. Empty frame returned 0 boxes (first load 25,969.8 ms); user-in-view frame returned one `person` box (2,608.3 ms). The old counter service was active before probing and was not restarted. Model cache path and sustained benchmark remain to verify.

Task 2: Local detector tests passed (5/5), and `--check-config` passed. Adapter and example config now target exact new model/class. Not deployed.

Task 3: Local person gate/presence tests passed (7/7). New event namespace is `:presence-person-v1`. Not deployed. Full suite still needs rerun after subsequent edits.

Task 4: Browser overlay tests passed (3/3). Dashboard now reads `detection.persons` and `person` boxes. Python frontend tests and full suite still need rerun. README, legacy probe script, and verification JSON still contain old-model references. Not deployed.

Task 5: Not started. Before cutover, make exact remote backup, sync tested files, verify services/status/camera, benchmark, then ask user for empty, partial, full, departure, and second-arrival live states. User cannot perform tests now.

Task 6: Not started. Do not delete old event rows, weights cache, or backups until Task 5 live validation succeeds. User explicitly authorized deletion afterward.

Current remote state: only `deployment/probe_person_model.py` was copied to the board and run. No production file was replaced, no service was restarted, and no old event/cache data was deleted in this execution turn.

Task 5: Deployed exact `person-detection-euioa/1` (cached model metadata `yolov8n`, class `person`). Rollback archive: `/home/arduino/retail-entrance-counter/backups/person-model-precutover-20260926.tar.gz`, sha256 `280f02ff895d864db5a292ad1390bc10189b5bca9a506ac81b95a238b3c65da7`. Empty and partial-body checks produced no accepted box/count. Two full-body entries at the brown door produced accepted full-body boxes and count 0→1→2. A third event at 07:18:41 UTC was confirmed by the user as another actual entry. Measured post-warmup about 0.478 FPS, p50 2029 ms, p95 2469 ms, counter RSS 68.7 MiB. Current count 3.

Task 5: Ruling: Calibrated `scene_threshold` from 0.025 to 0.16 because the fixed doorway empty frame scored about 0.13 and the person frame about 0.21 — enables re-arm in this scene — cost if wrong: a low-contrast person may not register as occupied.

Task 5: Ruling: A later empty frame scored above 0.16 without camera movement (user confirmed), so added a relative clear condition after sustained absence of accepted detections; test `test_rearms_after_sustained_relative_scene_clear_when_baseline_drifts` failed then passed — cost if wrong: prolonged model dropout during large within-frame motion could re-arm too early. Final live re-arm test pending.

Task 6: Inventory found old cache exactly `/mnt/retail-data/roboflow-cache/person-count-d4jyl/9` (12 MiB), new cache `/mnt/retail-data/roboflow-cache/person-detection-euioa/1` (12 MiB). SQLite has old IDs `entrance-1` (3), `entrance-1:presence-v2` (1), `entrance-1:presence-v3` (5), `entrance-1:presence-v4` (5), `entrance-fixed-2:presence-v4` (36), plus new `entrance-fixed-2:presence-person-v1` (3). No deletion yet. Purge helper tests passed 3/3; full local suite 36/36 Python and 3/3 browser before deployment of relative-clear code.
