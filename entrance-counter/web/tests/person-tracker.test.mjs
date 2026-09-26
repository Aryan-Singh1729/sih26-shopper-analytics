import test from 'node:test';
import assert from 'node:assert/strict';
import {PersonBoxTracker, matchBody} from '../person-tracker.mjs';

function frame(sequence, capturedAt, dx=0, brightness=0, blank=false) {
  const width=160, height=90, gray=new Uint8Array(width*height).fill(20+brightness);
  if (!blank) for(let y=15;y<75;y++) for(let x=50;x<75;x++) {
    gray[y*width+x+dx]=40+((x*13+y*17)%150)+brightness;
  }
  return {sequence,capturedAt,width,height,gray};
}
const status = (sequence=1,time=100) => ({counter_running:true,stream_available:true,detection:{
  frame_sequence:sequence,captured_at:time,image_size:[160,90],
  boxes:[{class:'person',xyxy:[50,15,75,75],confidence:.9}],
}});

test('tracks a translated full-body region with brightness changes',()=>{
  const box=matchBody(frame(1,100),frame(2,100.07,4,10),[50,15,75,75]);
  assert.deepEqual(box,[54,15,79,75]);
});
test('replays delayed detection onto the latest frame, never creates a track alone',()=>{
  const tracker=new PersonBoxTracker();
  tracker.push(frame(1,100)); tracker.push(frame(2,100.07,4));
  assert.equal(tracker.boxes(100.07).length,0);
  tracker.accept(status());
  assert.equal(tracker.boxes(100.07)[0].left,54/160*100);
  tracker.push(frame(3,100.14,8));
  assert.equal(tracker.boxes(100.14)[0].left,58/160*100);
});
test('clears when visual match fails, stream freezes, anchor expires or source restarts',()=>{
  const tracker=new PersonBoxTracker(); tracker.push(frame(1,100)); tracker.accept(status());
  assert.equal(tracker.boxes(100.4).length,0);
  assert.equal(tracker.boxes(102).length,0);
  tracker.push(frame(2,100.07,0,0,true)); assert.equal(tracker.boxes(100.07).length,0);
  tracker.push(frame(1,101)); assert.equal(tracker.boxes(101).length,0);
});
test('rejected partial person clears immediately and persistent no-person clears',()=>{
  const tracker=new PersonBoxTracker(); tracker.push(frame(1,100)); tracker.accept(status());
  tracker.push(frame(2,100.07));
  tracker.accept({...status(2,100.07),detection:{...status(2,100.07).detection,boxes:[],ignored_outside_area:1}});
  assert.equal(tracker.boxes(100.07).length,0);
});
