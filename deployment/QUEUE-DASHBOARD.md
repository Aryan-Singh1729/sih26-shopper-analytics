# Queue management

Current demo mode is `whole_frame`: every detected person is waiting, with two
full-height left/right counter display areas. Brief lost detections receive a
two-second grace. Departures produce observed waiting-duration samples, not
billing-service samples. Individual current timers update while people remain
visible; the completed average updates only when an observed wait ends.
Combined waiting is summed person-time, not elapsed wall-clock time. The four
main cards show Counter 1 waiting, mean completed observed waiting time,
Counter 2 waiting, and the longest current wait. The average excludes people
still waiting and shows no value until a wait completes; in whole-frame mode,
completion means that person left the camera view. Service timing remains
disabled until genuine service zones are enabled.
The live banner uses the busiest individual counter: 0–1 normal, 2 brown, 3+ red.
Two left and one right is brown, never red. Individual cards use their own counts.
Displayed occupancy excludes missing tracks immediately; the two-second grace
preserves visit timing only and does not add phantom waiting people.
Forecasts do not change these live alert colors. Refresh the browser after updates.

Open http://localhost:8082. Start with `python deployment/queue_dashboard.py`.
The footfall video server on localhost:8081 must also be running. Both dashboards
share the current EMEET annotated video and detector; there is no extra inference
worker and queue analytics never writes to the entrance event database.

Configure two counters (or up to eight through the settings API), open/closed
status, and rectangular waiting/service zones using percentages of the image.
The defaults are placeholders. For a sideways camera, draw the waiting zones
along each line and service zones around customers at each checkout. Keep staff
and unrelated walking paths outside them. Assignment uses the lower-center of
each detected box; service zones take precedence. Avoid overlapping counters.
Uncalibrated defaults disable service zones and extend waiting zones to the
floor. Enable service zones only after marking the billing locations. The live
longest-wait timer advances while people wait; the completed average changes
only when an observed wait ends.
Zone changes require 0.75 seconds of stable observation to reject box jitter.
If you move this single camera to checkout, the entrance dashboard no longer
has a dedicated entrance view. Monitoring both locations needs another camera.

Queue length is current waiting-zone occupancy, not a cumulative arrival count.
Service-zone occupancy is separate. Open/closed is manually configured, not
automatically inferred from seeing a person. Queue-to-service identity transitions
provide observed waits; service-to-outside transitions provide observed service
dwell. Missing identities do not generate completed-service samples. Someone
already waiting/being served when observation starts has a partial observed
duration, not their full historical wait. Occlusions and identity switches can
invalidate timing, so these are approximate visual measurements, not POS records.

A two-minute fluid forecast uses the trailing 60-second observed queue-entry
rate and open counters / mean service duration. Forecast starts after 30 seconds.
Until service samples exist, it uses the explicitly configured assumption (45s).
Staffing recommendation uses incoming workload plus clearance of the current
backlog within the target wait; it cannot recommend more counters than configured.
No trained congestion predictor is claimed. Disconnect pauses metrics and resets
the arrival-rate window. Config is saved in data/queue-config.json; timing samples
are bounded, session-only and reset on configuration save or restart.

Live verification: first configure zones for the fixed camera. Two people in the
waiting zone should show 2 continuously, not increase while standing. Move one
into service: waiting becomes 1 and a wait sample appears. Move that same person
visibly outside service: a service sample appears. Empty view should show 0.
