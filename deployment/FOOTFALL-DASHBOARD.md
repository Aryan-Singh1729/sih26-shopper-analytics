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
One visible person counts once. A missed detector result does not re-arm a visit:
fresh detector results must report an empty view for two seconds.
Returning after that clear view counts again. Separate
people detected together create separate arrivals.
The PC and board must be reachable. History refreshes on count changes and every
five seconds, and retains visibly marked stale data
if the board is unreachable. The clock uses Asia/Calcutta.

Metrics: selected-date total arrivals, hourly buckets, all tied busiest hours,
current-hour arrivals (today only), and last arrival. Existing demo entries
are included. Old counting namespaces and exits are excluded.

The active detector is PC MediaPipe Object Detector / EfficientDet-Lite0 int8,
person-only, up to 30 detections. The laptop feed uses an internal 0.30 cutoff;
box labels show only PERSON, without confidence percentages. A zero-cutoff test
returned 30 false candidates in an empty room, so the filter remains enabled.
Loopback SSH forwarding uses board port 9011.
Anonymous per-person tracks count groups and additional arrivals; saved history
is preserved. The laptop dashboard now owns a separate MediaPipe detector and
burns fresh detector boxes into the exact JPEG frame that was analyzed.
There are no browser overlay timing gates or entrance ROI filters on these boxes.
Detections touching the frame margin are clipped to the image and displayed.
The former two-percent full-body margin is removed because it hid real people
whose detected feet reached the bottom of the frame. Entry detections now count
without requiring a whole body plus margin to fit in the image.
For this entrance camera, accepted bodies must occupy at least 25% of image
height and be at least 1.2 times taller than wide. This rejects the observed
lower-left bedding false detection, but can miss seated, crouching, or distant
people; revalidate these geometry limits before changing the camera placement.
The laptop captures the board's stream once, keeps only a bounded in-memory
history, and skips intermediate frames when inference is busy. The browser
discards queued old frames before decoding. No image tracker or predicted box
is used in the live renderer. An empty detection result clears all rectangles
immediately. Separate counting identities survive box dropouts until the
empty-view gate re-arms. This deliberately favors avoiding duplicate counts;
departures/re-entries while other people remain may be undercounted. A prolonged
detector miss can still be mistaken for an empty view. Live validation is needed;
continuous boxes cannot be guaranteed when the detector misses a person.
Preview is 640x360 to reduce network backlog; original capture remains 1280x720.
No face recognition or cloud inference. Reboots require starting the PC processes
and reconnecting the SSH tunnel. Real-world group/occlusion tests remain required;
anonymous tracking can switch IDs, and a fully-visible box does not prove feet
are unobscured. Counts are not unique identified customers.
