// Short-lived image tracking only: new tracks always require a person detection.
// Work at 160x90, retain two seconds in memory, and never change arrival counts.
export class PersonBoxTracker {
  constructor() { this.reset(); }
  reset() { this.history = []; this.tracks = []; this.lastResult = null; }

  push(frame) {
    const previous = this.history.at(-1);
    if (previous && (frame.sequence <= previous.sequence || frame.capturedAt < previous.capturedAt)) this.reset();
    if (previous && frame.capturedAt - previous.capturedAt > .25) this.tracks = [];
    if (previous && this.tracks.length) this.advance(previous, frame);
    this.history.push(frame);
    this.history = this.history.filter(item => frame.capturedAt - item.capturedAt <= 2);
  }

  accept(status) {
    if (!status?.counter_running || !status?.stream_available) { this.tracks = []; return; }
    const detection = status.detection;
    const latest = this.history.at(-1);
    if (!latest || !detection || !Number.isFinite(detection.captured_at) || !Number.isFinite(detection.frame_sequence)) return;
    const key = `${detection.frame_sequence}:${detection.captured_at}`;
    if (key === this.lastResult || detection.frame_sequence > latest.sequence) return;
    this.lastResult = key;
    const age = latest.capturedAt - detection.captured_at;
    if (age < 0 || age > 1.5) { this.tracks = []; return; }
    const boxes = detection.boxes || [];
    if (!boxes.length) {
      // A cropped/rejected body is not a complete person. Clear immediately.
      if (detection.ignored_outside_area > 0) this.tracks = [];
      else this.tracks = this.tracks.filter(track => detection.captured_at - track.anchorAt <= .8);
      return;
    }
    const [width, height] = detection.image_size || [];
    if (!(width > 0 && height > 0)) { this.tracks = []; return; }
    let index = 0;
    for (let i = 1; i < this.history.length; i++) {
      if (Math.abs(this.history[i].capturedAt - detection.captured_at) < Math.abs(this.history[index].capturedAt - detection.captured_at)) index = i;
    }
    if (Math.abs(this.history[index].capturedAt - detection.captured_at) > .15) { this.tracks = []; return; }
    const seed = this.history[index];
    this.tracks = boxes.filter(box => box.class === 'person' && box.xyxy?.length === 4 &&
      box.xyxy.every(Number.isFinite) && Number.isFinite(box.confidence)).map(box => ({
      box: box.xyxy.map((v, i) => v * (i % 2 ? seed.height / height : seed.width / width)),
      confidence: box.confidence, anchorAt: detection.captured_at,
    })).filter(track => track.box[2] > track.box[0] && track.box[3] > track.box[1]);
    // Replay recent camera frames to bring a delayed model box into the present.
    for (let i = index + 1; i < this.history.length && this.tracks.length; i++) this.advance(this.history[i - 1], this.history[i]);
  }

  advance(previous, current) {
    this.tracks = this.tracks.flatMap(track => {
      if (current.capturedAt - track.anchorAt > 1.5) return [];
      const box = matchBody(previous, current, track.box);
      return box ? [{...track, box}] : [];
    });
  }

  boxes(now) {
    const frame = this.history.at(-1);
    if (!frame || now - frame.capturedAt > .3 || now < frame.capturedAt) return [];
    return this.tracks.filter(track => now - track.anchorAt <= 1.5).map(track => ({
      left: track.box[0] / frame.width * 100, top: track.box[1] / frame.height * 100,
      width: (track.box[2] - track.box[0]) / frame.width * 100,
      height: (track.box[3] - track.box[1]) / frame.height * 100,
      label: `PERSON ${Math.round(track.confidence * 100)}%`,
    }));
  }
}

export function matchBody(previous, current, box) {
  if (previous.width !== current.width || previous.height !== current.height) return null;
  const [x1, y1, x2, y2] = box;
  const bw = x2 - x1, bh = y2 - y1;
  if (bw < 6 || bh < 12) return null;
  const samples = [];
  for (let row = 0; row < 12; row++) for (let col = 0; col < 8; col++) {
    const u = .1 + col / 7 * .8, v = .08 + row / 11 * .84;
    const x = Math.round(x1 + bw*u), y = Math.round(y1 + bh*v);
    if (x < 0 || x >= previous.width || y < 0 || y >= previous.height) return null;
    samples.push({u, v, value: previous.gray[y*previous.width+x]});
  }
  const mean = samples.reduce((sum, s) => sum+s.value, 0)/samples.length;
  const variance = samples.reduce((sum, s) => sum+(s.value-mean)**2, 0)/samples.length;
  if (variance < 25) return null; // Do not invent motion in a textureless region.
  let best = Infinity, result = null;
  const radius = Math.min(12, Math.max(4, Math.ceil((current.capturedAt-previous.capturedAt)*100)));
  for (const scale of [1, .96, 1.04]) for (let dy = -radius; dy <= radius; dy++) for (let dx = -radius; dx <= radius; dx++) {
    const w = bw*scale, h = bh*scale;
    const left = x1 + dx + (bw-w)/2, top = y1 + dy + (bh-h)/2;
    if (left < 1 || top < 1 || left+w >= current.width-1 || top+h >= current.height-1) continue;
    let sum = 0, square = 0;
    for (const sample of samples) {
      const x = Math.round(left+w*sample.u), y = Math.round(top+h*sample.v);
      const delta = current.gray[y*current.width+x]-sample.value;
      sum += delta; square += delta*delta;
    }
    // Remove a global brightness shift; small motion/scale penalty breaks ties.
    const error = square/samples.length-(sum/samples.length)**2 + .03*(dx*dx+dy*dy)+Math.abs(scale-1);
    if (error < best) { best = error; result = [left, top, left+w, top+h]; }
  }
  return best < Math.min(900, variance*.75) ? result : null;
}
