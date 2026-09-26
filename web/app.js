import { personOverlayModel, personDetectionCopy } from './person-overlay.mjs';
import { MjpegParser } from './mjpeg.mjs';
import { PersonBoxTracker } from './person-tracker.mjs';

const byId = (id) => document.getElementById(id);

let latestStatus = null;
let streamActive = false;
let liveMetadata = null;
let statusPending = false;
const personTracker = new PersonBoxTracker();
const trackingCanvas = document.createElement('canvas');
trackingCanvas.width = 160; trackingCanvas.height = 90;
const trackingContext = trackingCanvas.getContext('2d', {willReadFrequently: true});
window.retailLiveMetrics = {frames: 0, trackingMs: 0, boxes: 0};

function renderPersonBoxes(data) {
  const layer = byId('personBoxLayer');
  layer.replaceChildren();
  if (!data) return;
  personTracker.accept(data);
  const boxes = liveMetadata ? personTracker.boxes(liveMetadata.capturedAt + (performance.now() - liveMetadata.receivedAt)/1000) : [];
  window.retailLiveMetrics.boxes = boxes.length;
  for (const box of boxes) {
    const marker = document.createElement('div');
    marker.className = `person-box${box.top < 5 ? ' near-top' : ''}`;
    marker.style.left = `${box.left}%`;
    marker.style.top = `${box.top}%`;
    marker.style.width = `${box.width}%`;
    marker.style.height = `${box.height}%`;
    const label = document.createElement('span');
    label.textContent = box.label;
    marker.append(label);
    layer.append(marker);
  }
}

const formatNumber = (value, digits = 1) => {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
};

const setBadge = (element, state, text) => {
  element.className = `badge badge-${state}`;
  element.innerHTML = `<span class="dot"></span>${text}`;
};

function render(data) {
  latestStatus = data;
  renderPersonBoxes(data);
  const counter = data.counter || {};
  const performance = data.performance || {};
  const inference = data.inference || {};
  const model = data.model || {};
  const detection = data.detection || {};

  byId("entries").textContent = counter.entries_today ?? 0;
  byId("personsDetected").textContent = detection.persons ?? 0;
  byId("confidence").textContent = detection.confidence == null ? "—" : `${formatNumber(detection.confidence * 100, 0)}%`;
  byId("visibleTracks").textContent = performance.visible_tracks ?? 0;
  byId("fps").textContent = performance.processed_fps == null ? "—" : formatNumber(performance.processed_fps, 2);
  byId("latency").textContent = performance.inference_ms_p95 == null ? "—" : `${formatNumber(performance.inference_ms_p95, 0)} ms`;
  byId("rss").textContent = performance.rss_mb == null ? "—" : `${formatNumber(performance.rss_mb, 0)} MB`;
  byId("availableRam").textContent = performance.available_memory_mb == null ? "—" : `${formatNumber(performance.available_memory_mb, 0)} MB`;
  byId("droppedFrames").textContent = performance.dropped_frames ?? "—";
  byId("temperature").textContent = performance.temperature_c == null ? "—" : `${formatNumber(performance.temperature_c, 1)} °C`;
  byId("modelId").textContent = model.model_id || "person-detection-euioa/1";
  byId("modelType").textContent = model.model_type || "Roboflow 3.0 Object Detection (Fast)";
  byId("modelRuntime").textContent = model.backend || 'Local inference';

  setBadge(byId("inferenceBadge"), inference.healthy ? "ok" : "error", inference.healthy ? "Model online" : "Model offline");
  setBadge(byId("systemBadge"), data.counter_running ? "ok" : inference.healthy ? "waiting" : "error", data.counter_running ? "Counting live" : inference.healthy ? "Inference ready" : "System offline");
  setBadge(byId("streamBadge"), data.stream_available && data.counter_running ? "ok" : "waiting", data.stream_available && data.counter_running ? "Camera live" : "Waiting for camera");
  byId("livePill").hidden = !data.stream_available;
  const personSeen = data.counter_running && Number(detection.persons || 0) > 0;
  const detectionCopy = personDetectionCopy(personSeen ? detection.persons : 0);
  byId("detectionPill").textContent = detectionCopy.pill;
  byId("detectionPill").classList.toggle("detected", personSeen);
  byId("lastDetection").textContent = detection.last_detected_at ? `Last person detected ${new Date(detection.last_detected_at).toLocaleTimeString()}` : "No person detected yet";
  if (data.detection_frame_available && byId("detectionFrame").closest("details").open) {
    byId("detectionFrame").src = `/api/detection.jpg?t=${Date.now()}`;
    byId("detectionFrame").hidden = false;
  }

  const notice = byId("notice");
  if (data.counter_running) {
    notice.classList.add("ready");
    byId("noticeTitle").textContent = detectionCopy.notice;
    byId("noticeText").textContent = "An arrival is counted only when a complete person is visible after the camera view has been clear. Model results update at the measured inference rate.";
  } else if (inference.healthy) {
    notice.classList.remove("ready");
    byId("noticeTitle").textContent = "Counter is starting";
    byId("noticeText").textContent = "The detector is online; waiting for the first camera result.";
  } else {
    notice.classList.remove("ready");
    byId("noticeTitle").textContent = "Inference service unavailable";
    byId("noticeText").textContent = "Check the local PC detector and its SSH connection to the UNO Q.";
  }
  byId("lastUpdated").textContent = `Updated ${new Date(data.updated_at).toLocaleTimeString()}`;
}

function refreshFrame() {
  if (streamActive) return;
  const frame = byId("liveFrame");
  frame.src = `/api/frame.jpg?t=${Date.now()}`;
}

byId("liveFrame").addEventListener("load", () => {
  if (streamActive) return;
  byId("liveFrame").hidden = false;
  byId("cameraPlaceholder").hidden = true;
  window.setTimeout(refreshFrame, 200);
});

byId("liveFrame").addEventListener("error", () => {
  byId("liveFrame").hidden = true;
  byId("cameraPlaceholder").hidden = false;
  window.setTimeout(refreshFrame, 1500);
});

async function refresh() {
  if (statusPending) return;
  statusPending = true;
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    latestStatus = null;
    renderPersonBoxes(null);
    setBadge(byId("systemBadge"), "error", "Dashboard disconnected");
    byId("lastUpdated").textContent = "Unable to reach the UNO Q";
  } finally {
    statusPending = false;
  }
}

async function continuousCamera() {
  const controller = new AbortController();
  let watchdog;
  try {
    const response = await fetch('/api/live.mjpg', { cache: 'no-store', signal: controller.signal });
    if (!response.ok || !response.headers.get('content-type')?.includes('multipart')) throw new Error('Stream unavailable');
    const reader = response.body.getReader();
    const parser = new MjpegParser();
    while (true) {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => controller.abort(), 3000);
      const {value, done} = await reader.read();
      if (done) break;
      const frames = parser.push(value);
      const frame = frames.at(-1);
      if (!frame) continue;
      const bitmap = await createImageBitmap(new Blob([frame.jpeg], {type: 'image/jpeg'}));
      const canvas = byId('liveCanvas');
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      canvas.getContext('2d').drawImage(bitmap, 0, 0);
      trackingContext.drawImage(bitmap, 0, 0, 160, 90);
      const rgba = trackingContext.getImageData(0, 0, 160, 90).data;
      const gray = new Uint8Array(160*90);
      for (let i=0; i<gray.length; i++) gray[i] = (rgba[i*4]*77+rgba[i*4+1]*150+rgba[i*4+2]*29)>>8;
      bitmap.close();
      liveMetadata = { sequence: frame.sequence, capturedAt: frame.capturedAt, receivedAt: performance.now() };
      const trackingStarted = performance.now();
      personTracker.push({sequence: frame.sequence, capturedAt: frame.capturedAt, width: 160, height: 90, gray});
      window.retailLiveMetrics.trackingMs = performance.now() - trackingStarted;
      window.retailLiveMetrics.frames++;
      streamActive = true;
      canvas.hidden = false;
      byId('liveFrame').hidden = true;
      byId('cameraPlaceholder').hidden = true;
      renderPersonBoxes(latestStatus);
    }
  } catch (error) {
    // Retain the simple JPEG endpoint as a recoverable fallback.
  } finally {
    clearTimeout(watchdog); controller.abort();
    streamActive = false; liveMetadata = null;
    personTracker.reset();
    byId('liveCanvas').hidden = true;
    refreshFrame();
    setTimeout(continuousCamera, 1500);
  }
}

refresh();
continuousCamera();
setInterval(refresh, 200);
setInterval(() => renderPersonBoxes(latestStatus), 100);
