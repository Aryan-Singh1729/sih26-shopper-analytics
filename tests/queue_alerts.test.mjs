import test from 'node:test';
import assert from 'node:assert/strict';
import {alertLevel,alertText,waitValue,counterAlert} from '../queue-web/alerts.mjs';
test('live alert switches up and down at exact occupancy thresholds',()=>{
  assert.deepEqual([0,1,2,3,4,2,1,0].map(alertLevel),['normal','normal','brown','red','red','brown','normal','normal']);
  assert.match(alertText(3),/High queue alert/);assert.match(alertText(2),/caution/);assert.doesNotMatch(alertText(1),/alert|caution/);
});
test('counter alerts never aggregate separate queues into red',()=>{
  const counters=(a,b)=>[{id:'Left',waiting:a},{id:'Right',waiting:b}];
  assert.equal(counterAlert(counters(2,1)).level,'brown');
  assert.equal(counterAlert(counters(2,2)).level,'brown');
  assert.equal(counterAlert(counters(1,1)).level,'normal');
  assert.equal(counterAlert(counters(3,0)).level,'red');
  assert.match(counterAlert(counters(2,1)).text,/Left: 2 waiting/);
});
test('waiting average uses ongoing timers then completed visits',()=>{
  assert.equal(waitValue({queue_length:2,average_current_wait_seconds:12,average_wait_seconds:5}),12);
  assert.equal(waitValue({queue_length:0,average_current_wait_seconds:null,average_wait_seconds:5}),5);
});
