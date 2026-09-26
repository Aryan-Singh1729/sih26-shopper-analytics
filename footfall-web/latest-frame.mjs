export class LatestFrameSlot {
  #latest = null;

  push(frame) { this.#latest = frame; }

  take() {
    const frame = this.#latest;
    this.#latest = null;
    return frame;
  }
}
