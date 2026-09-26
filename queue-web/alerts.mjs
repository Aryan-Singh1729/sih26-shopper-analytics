export function alertLevel(count){return count>2?'red':count===2?'brown':'normal';}
export function alertText(count){return count>2?`High queue alert · ${count} people waiting`:count===2?'Queue caution · 2 people waiting':`Live monitoring · ${count} ${count===1?'person':'people'} waiting`;}
export function waitValue(data){return data.queue_length>0?data.average_current_wait_seconds:data.average_wait_seconds;}
export function counterAlert(counters){
  const largest=Math.max(0,...counters.map(c=>c.waiting));
  const flagged=counters.filter(c=>c.waiting>=2);
  return {level:alertLevel(largest),text:flagged.length?`${largest>2?'High queue alert':'Queue caution'} · ${flagged.map(c=>`${c.id}: ${c.waiting} waiting`).join(' · ')}`:`Live monitoring · ${counters.map(c=>`${c.id}: ${c.waiting} waiting`).join(' · ')}`};
}
