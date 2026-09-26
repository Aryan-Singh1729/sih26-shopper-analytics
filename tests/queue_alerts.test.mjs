import test from 'node:test';
import assert from 'node:assert/strict';
import {alertLevel,alertText,waitValue,currentWaitingSeconds,counterWaiting,counterAlert} from '../queue-web/alerts.mjs';
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
test('waiting average uses completed visits even while people are still waiting',()=>{
  assert.equal(waitValue({queue_length:2,average_current_wait_seconds:12,average_wait_seconds:5}),5);
  assert.equal(waitValue({queue_length:0,average_current_wait_seconds:null,average_wait_seconds:5}),5);
  assert.equal(waitValue({queue_length:1,average_current_wait_seconds:12,average_wait_seconds:null}),null);
});
test('current waiting card follows the longest active wait and clears with the queue',()=>{
  assert.equal(currentWaitingSeconds({queue_length:1,longest_wait_seconds:4.2}),4.2);
  assert.equal(currentWaitingSeconds({queue_length:2,longest_wait_seconds:17.5}),17.5);
  assert.equal(currentWaitingSeconds({queue_length:0,longest_wait_seconds:17.5}),0);
});
test('side cards show each counter independently',()=>{
  const counters=[{id:'Counter 1',waiting:2},{id:'Counter 2',waiting:1}];
  assert.equal(counterWaiting(counters,0),2);
  assert.equal(counterWaiting(counters,1),1);
  assert.equal(counterWaiting(counters,2),0);
});
