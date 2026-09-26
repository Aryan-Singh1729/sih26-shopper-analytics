export class MjpegParser {
  constructor() { this.buffer = new Uint8Array(); }
  push(chunk) {
    const joined = new Uint8Array(this.buffer.length + chunk.length);
    joined.set(this.buffer); joined.set(chunk, this.buffer.length);
    this.buffer = joined;
    if (joined.length > 4_000_000) throw new Error('Stream frame exceeds limit');
    const frames = [];
    while (true) {
      let end = -1;
      for (let i = 0; i < this.buffer.length - 3; i++) {
        if (this.buffer[i] === 13 && this.buffer[i+1] === 10 && this.buffer[i+2] === 13 && this.buffer[i+3] === 10) { end = i; break; }
      }
      if (end < 0) break;
      const header = new TextDecoder().decode(this.buffer.slice(0, end));
      const length = Number(header.match(/Content-Length:\s*(\d+)/i)?.[1]);
      if (!Number.isInteger(length) || length < 1 || length > 2_000_000) throw new Error('Invalid stream length');
      if (this.buffer.length < end + 4 + length) break;
      frames.push({
        sequence: Number(header.match(/X-Frame-Sequence:\s*(\d+)/i)?.[1]),
        capturedAt: Number(header.match(/X-Captured-At:\s*([\d.]+)/i)?.[1]),
        jpeg: this.buffer.slice(end + 4, end + 4 + length),
      });
      this.buffer = this.buffer.slice(end + 4 + length);
    }
    return frames;
  }
}
