import {displayClock, displaySummary, nextReportingDay} from './summary.mjs';
const el=id=>document.getElementById(id);
const zone='Asia/Calcutta';
let pending=false, lastData=null;
const dateInZone=()=>new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
let lastToday=dateInZone();
const hourLabel=hour=>`${String(hour).padStart(2,'0')}:00`;
if(new URLSearchParams(location.search).get('kiosk')==='1')document.documentElement.classList.add('kiosk');
function tick(){
  const today=dateInZone();
  if(today!==lastToday){
    el('day').value=nextReportingDay(lastToday,el('day').value,today);
    el('day').max=today;
    lastToday=today;
    refresh();
  }
  const clock=displayClock();
  el('clock').textContent=clock.time;
  el('clockDate').textContent=clock.date;
  if(lastData) renderCurrent(lastData);
}
function renderCurrent(data){
  const summary=displaySummary(data);
  el('current').textContent=summary.current;
  el('currentDetail').textContent=summary.currentDetail;
}
function render(data){
  lastData=data;
  const summary=displaySummary(data);
  el('total').textContent=summary.total;
  const peaks=data.peak_hours;
  el('peak').textContent=summary.peak;
  el('peakDetail').textContent=summary.peakDetail;
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
