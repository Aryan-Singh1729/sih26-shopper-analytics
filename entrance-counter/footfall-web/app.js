const el=id=>document.getElementById(id);
const zone='Asia/Calcutta';
let pending=false, lastData=null;
const dateInZone=()=>new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const hourLabel=hour=>`${String(hour).padStart(2,'0')}:00`;
function tick(){
  el('clock').textContent=new Intl.DateTimeFormat('en-IN',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());
  el('clockDate').textContent=new Intl.DateTimeFormat('en-IN',{timeZone:zone,weekday:'long',day:'numeric',month:'short',year:'numeric'}).format(new Date());
  if(lastData) renderCurrent(lastData);
}
function renderCurrent(data){
  const today=data.date===dateInZone();
  const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',hourCycle:'h23'}).format(new Date()));
  el('current').textContent=today ? data.hourly[hour].arrivals : '—';
  el('currentDetail').textContent=today ? `${hourLabel(hour)}–${hourLabel((hour+1)%24)} today` : 'Select today to see the current hour';
}
function render(data){
  lastData=data;
  el('total').textContent=data.total_arrivals;
  const peaks=data.peak_hours;
  el('peak').textContent=peaks.length ? `${hourLabel(peaks[0])}–${hourLabel((peaks[0]+1)%24)}` : 'No arrivals';
  el('peakDetail').textContent=peaks.length ? `${data.peak_count} arrivals${peaks.length>1 ? ` · ${peaks.length} hours tied` : ''}` : 'No events for this date';
  el('last').textContent=data.last_arrival ? new Intl.DateTimeFormat('en-IN',{timeZone:zone,hour:'2-digit',minute:'2-digit'}).format(new Date(data.last_arrival)) : '—';
  el('chartDate').textContent=data.date;
  const chart=el('chart'); chart.replaceChildren();
  for(const bucket of data.hourly){
    const slot=document.createElement('div');slot.className='bar-slot';
    const count=document.createElement('small');count.textContent=bucket.arrivals||'';
    const bar=document.createElement('button');bar.className=`bar${bucket.arrivals&&bucket.arrivals===data.peak_count?' peak':''}`;
    bar.style.height=`${bucket.arrivals/Math.max(1,data.peak_count)*88}%`;
    const label=`${hourLabel(bucket.hour)}–${hourLabel((bucket.hour+1)%24)}: ${bucket.arrivals} arrivals`;
    bar.title=label;bar.setAttribute('aria-label',label);bar.onclick=()=>el('insight').textContent=label;
    slot.append(count,bar);chart.append(slot);
  }
  el('insight').textContent=peaks.length ? `Peak footfall: ${data.peak_count} arrivals per hour at ${peaks.map(hourLabel).join(', ')}. Total recorded arrivals: ${data.total_arrivals}.` : 'No arrivals recorded for this date. The dashboard does not invent missing data.';
  renderCurrent(data);
  el('updated').textContent=`Updated ${new Intl.DateTimeFormat('en-IN',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date())} · Refreshes every 5 seconds`;
}
async function refresh(){
  if(pending)return;pending=true;
  const requestedDay=el('day').value;
  try{
    const response=await fetch(`/api/footfall?date=${encodeURIComponent(requestedDay)}`,{cache:'no-store',signal:AbortSignal.timeout(6000)});
    if(!response.ok)throw Error('History unavailable');
    const data=await response.json();
    if(requestedDay!==el('day').value)return;
    render(data);el('status').textContent='● Entrance history connected';el('status').classList.remove('offline');document.body.classList.remove('stale');
  }catch(error){el('status').textContent='Disconnected — showing last received data';el('status').classList.add('offline');document.body.classList.add('stale');}
  finally{pending=false;}
}
el('day').value=dateInZone();el('day').max=dateInZone();
el('day').onchange=refresh;el('today').onclick=()=>{el('day').value=dateInZone();refresh();};
window.addEventListener('arrival-updated',refresh);
tick();refresh();setInterval(tick,1000);setInterval(refresh,5000);
