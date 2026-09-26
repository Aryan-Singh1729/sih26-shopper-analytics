import {MjpegParser} from '/mjpeg.mjs';
import {alertLevel,counterAlert,waitValue} from './alerts.mjs';
const el=id=>document.getElementById(id);let config,polling=false;
const duration=value=>value==null?'—':value<60?`${Math.round(value)} sec`:`${(value/60).toFixed(1)} min`;
function zones(){
  const svg=el('zones');svg.replaceChildren();
  config.counters.forEach((c,i)=>['queue','service'].forEach(kind=>{
    if(kind==='service'&&c.service_enabled===false)return;
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');const [x,y,w,h]=c[kind].map(n=>n*100);
    for(const [key,value] of Object.entries({x,y,width:w,height:h,fill:kind==='queue'?'#4ebaff':'#ffbf55','fill-opacity':.08,stroke:kind==='queue'?'#4ebaff':'#ffbf55','stroke-width':.25}))rect.setAttribute(key,value);
    svg.append(rect);
    const text=document.createElementNS('http://www.w3.org/2000/svg','text');text.setAttribute('x',x+1);text.setAttribute('y',y+3);text.setAttribute('fill',kind==='queue'?'#7cd0ff':'#ffd07c');text.setAttribute('font-size','2.3');text.textContent=`C${i+1} ${kind==='queue'?'WAITING':'SERVICE'}`;svg.append(text);
  }));
}
async function settings(){
  const response=await fetch('/api/config');if(!response.ok)throw Error('Settings unavailable');config=await response.json();
  el('zoneSettings').replaceChildren();
  const modeLabel=document.createElement('label');modeLabel.textContent='Count everyone visible as waiting (demo without checkout setup)';const modeInput=document.createElement('input');modeInput.type='checkbox';modeInput.id='wholeFrameMode';modeInput.checked=config.mode==='whole_frame';modeLabel.append(modeInput);el('zoneSettings').append(modeLabel);
  config.counters.forEach((c,i)=>{
    const field=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=c.id;field.append(legend);
    const open=document.createElement('label');open.textContent='Counter open (manual status)';const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=c.open;checkbox.id=`open${i}`;open.append(checkbox);field.append(open);
    const serviceLabel=document.createElement('label');serviceLabel.textContent='Enable service zone after marking the actual billing spot';const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=c.service_enabled!==false;enabled.id=`serviceEnabled${i}`;serviceLabel.append(enabled);field.append(serviceLabel);
    ['queue','service'].forEach(kind=>{const group=document.createElement('div');group.className='fields';
      c[kind].forEach((value,j)=>{const label=document.createElement('label');label.textContent=`${kind} · ${['x','y','width','height'][j]} %`;const input=document.createElement('input');input.type='number';input.min='0';input.max='100';input.step='.1';input.required=true;input.value=+(value*100).toFixed(2);input.id=`${kind}${i}_${j}`;label.append(input);group.append(label)});field.append(group)});el('zoneSettings').append(field);
  });el('assumption').value=config.fallback_service_seconds;el('target').value=config.target_wait_seconds;el('limit').value=config.congestion_queue_length;zones();
}
el('settings').onsubmit=async event=>{
  event.preventDefault();const next=structuredClone(config);
  next.mode=el('wholeFrameMode').checked?'whole_frame':'zones';
  next.counters.forEach((c,i)=>{c.open=el(`open${i}`).checked;c.service_enabled=el(`serviceEnabled${i}`).checked;['queue','service'].forEach(kind=>c[kind]=[0,1,2,3].map(j=>Number(el(`${kind}${i}_${j}`).value)/100))});
  next.fallback_service_seconds=Number(el('assumption').value);next.target_wait_seconds=Number(el('target').value);next.congestion_queue_length=Number(el('limit').value);
  try{const response=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(next)});if(!response.ok)throw Error('Zones must fit within the image');config=next;zones();el('saved').textContent='Saved · timing session restarted'}catch(error){el('saved').textContent=error.message}
};
async function poll(){
  if(polling)return;polling=true;
  try{const response=await fetch('/api/queue',{signal:AbortSignal.timeout(2500)});if(!response.ok)throw Error('Unavailable');const data=await response.json();
    if(!data.healthy)throw Error(data.message||'Camera unavailable · occupancy and timing paused');
    el('waiting').textContent=data.queue_length;el('wait').textContent=duration(waitValue(data)??0);el('service').textContent=data.service_calibrated?duration(data.average_service_seconds??0):'Not configured';
    el('waitLabel').textContent=data.queue_length>0?'Average current wait':'Average completed wait';
    el('waitSamples').textContent=data.queue_length>0?`Live average across ${data.queue_length} people · ${data.wait_samples} completed visits`:data.mode==='whole_frame'?`${data.wait_samples} completed waiting visits (person left view)`:`${data.wait_samples} observed queue → service transitions`;el('serviceSamples').textContent=data.mode==='whole_frame'?'Disabled · no checkout/service setup':`${data.service_samples} observed service → outside transitions`;
    el('forecast').textContent=data.forecast_queue_2min??'Warming up';el('basis').textContent=data.service_basis;
    el('liveWait').textContent=data.queue_length?`Longest current wait: ${duration(data.longest_wait_seconds)}`:'No one in the waiting zones';
    el('assignment').textContent=data.mode==='whole_frame'?`${data.visible_people} detected · ${data.queue_length} waiting. Occupancy uses visible tracks only; a 2-second grace preserves timing through short dropouts. Completed average updates when someone leaves.`:`${data.visible_people} detected · ${data.queue_length} waiting · ${data.in_service} in service · ${data.outside_people} outside zones. ${data.service_calibrated?'Completed averages update only after zone transitions.':'Service timing disabled until actual billing spots are marked and enabled.'}`;
    el('waitTotal').textContent=data.mode==='whole_frame'?`Total combined waiting: ${duration(data.total_wait_seconds)} · Average current wait: ${duration(data.average_current_wait_seconds)}`:'';
    el('peopleTimers').replaceChildren();(data.people||[]).forEach(person=>{const item=document.createElement('span');item.textContent=`Person ${person.id}: ${duration(person.wait_seconds)}`;el('peopleTimers').append(item)});
    el('recommendation').textContent=data.recommendation;el('rates').textContent=`Recent arrivals: ${data.arrival_rate_per_minute}/min · ${data.in_service} people in service · Forecast needs 30 seconds of observation`;
    const alert=counterAlert(data.counters);
    el('status').textContent=data.stale?data.message:alert.text;el('status').classList.toggle('warning',data.stale||alert.level==='brown');el('status').classList.toggle('critical',!data.stale&&alert.level==='red');
    el('counters').replaceChildren();data.counters.forEach(c=>{const article=document.createElement('article');article.classList.add(`queue-${alertLevel(c.waiting)}`);const title=document.createElement('span');title.textContent=`${c.id} · ${c.open?'OPEN':'CLOSED'}`;const count=document.createElement('strong');count.textContent=`${c.waiting} waiting`;const detail=document.createElement('small');detail.textContent=`${c.in_service} in service · longest current wait ${duration(c.longest_wait_seconds)}`;article.append(title,count,detail);el('counters').append(article)});
  }catch(error){el('status').textContent=error.message;el('status').classList.add('warning');el('status').classList.remove('critical');['waiting','wait','service','forecast'].forEach(id=>el(id).textContent='—');['waitSamples','serviceSamples','basis','rates','assignment'].forEach(id=>el(id).textContent='Waiting for fresh measurements');el('waitTotal').textContent='';el('peopleTimers').replaceChildren();el('liveWait').textContent='Live waiting timer paused';el('recommendation').textContent='Waiting for live measurements';el('counters').replaceChildren();}
  finally{polling=false;}
}
async function stream(){const controller=new AbortController();let watchdog;
  try{const response=await fetch('/api/live.mjpg',{signal:controller.signal});if(!response.ok)throw Error('Camera unavailable');const reader=response.body.getReader(),parser=new MjpegParser();
    while(true){clearTimeout(watchdog);watchdog=setTimeout(()=>controller.abort(),4000);const {value,done}=await reader.read();if(done)break;const frame=parser.push(value).at(-1);if(!frame)continue;
      const bitmap=await createImageBitmap(new Blob([frame.jpeg],{type:'image/jpeg'}));const canvas=el('camera');canvas.width=bitmap.width;canvas.height=bitmap.height;canvas.getContext('2d').drawImage(bitmap,0,0);bitmap.close();el('cameraState').textContent=`● Live person boxes · frame ${frame.sequence}`;}
  }catch(error){el('cameraState').textContent='Camera disconnected · reconnecting';}
  finally{clearTimeout(watchdog);controller.abort();const canvas=el('camera');canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);setTimeout(stream,1000)}
}
settings().catch(error=>el('saved').textContent=error.message);poll();stream();setInterval(poll,500);setInterval(()=>el('clock').textContent=new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Calcutta'}),1000);
