const RESULT_TTL_MS = 5000;

export function personDetectionCopy(count) {
  const detected = Number(count) > 0;
  return {
    pill: detected ? `${count} PERSON${Number(count) === 1 ? '' : 'S'} DETECTED` : 'NO PERSON IN LATEST RESULT',
    notice: detected ? 'Person detected by the model' : 'Camera and counting are live',
  };
}

export function personOverlayModel(status, frameOrNow = Date.now(), currentNow = Date.now()) {
  const frame = typeof frameOrNow === 'object' ? frameOrNow : null;
  const now = frame ? currentNow : frameOrNow;
  const detection = status?.detection;
  if (!status?.counter_running || !status?.stream_available || !detection) return [];
  const resultTime = frame ? Number(detection.captured_at) * 1000 : Date.parse(detection.result_at);
  const ttl = frame ? 500 : RESULT_TTL_MS;
  if (!Number.isFinite(resultTime) || now - resultTime < 0 || now - resultTime > ttl) return [];
  if (frame && (!Number.isFinite(detection.frame_sequence) || frame.sequence < detection.frame_sequence || frame.capturedAt * 1000 - resultTime > ttl)) return [];
  const [imageWidth, imageHeight] = detection.image_size || [];
  if (!Number.isFinite(imageWidth) || !Number.isFinite(imageHeight) || imageWidth <= 0 || imageHeight <= 0) return [];
  return (Array.isArray(detection.boxes) ? detection.boxes : []).flatMap((box) => {
    if (box?.class !== 'person' || !Array.isArray(box.xyxy) || box.xyxy.length !== 4) return [];
    const [x1, y1, x2, y2] = box.xyxy.map(Number);
    const confidence = Number(box.confidence);
    if (![x1, y1, x2, y2, confidence].every(Number.isFinite) || confidence < 0 || confidence > 1) return [];
    const left = Math.max(0, Math.min(imageWidth, x1));
    const top = Math.max(0, Math.min(imageHeight, y1));
    const right = Math.max(0, Math.min(imageWidth, x2));
    const bottom = Math.max(0, Math.min(imageHeight, y2));
    if (right <= left || bottom <= top) return [];
    return [{
      left: left / imageWidth * 100,
      top: top / imageHeight * 100,
      width: (right - left) / imageWidth * 100,
      height: (bottom - top) / imageHeight * 100,
      label: `PERSON ${Math.round(confidence * 100)}%`,
    }];
  });
}
