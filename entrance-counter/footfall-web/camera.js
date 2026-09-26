import {MjpegParser} from '/mjpeg.mjs';
const el=id=>document.getElementById(id);
let pending=false;
let previousTotal=null;
async function poll(){
  if(pending)return;pending=true;
  try{
    const [response,liveResponse]=await Promise.all([
      fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(2500)}),
      fetch('/api/live-status',{cache:'no-store',signal:AbortSignal.timeout(2500)})]);
    if(!response.ok||!liveResponse.ok)throw Error('Status unavailable');
    const status=await response.json(),live=await liveResponse.json();
    el('liveArrivals').textContent=status.counter?.entries_today ?? '—';
    if(status.counter?.entries_today!==previousTotal){previousTotal=status.counter?.entries_today;window.dispatchEvent(new Event('arrival-updated'));}
    el('detectorName').textContent=live.backend;
    el('visiblePeople').textContent=live.persons;
    el('livePeople').textContent=`${live.persons} PERSON${live.persons===1?'':'S'} VISIBLE`;
    if(!live.healthy)el('cameraState').textContent='Waiting for laptop processing';
  }catch(error){el('cameraState').textContent='Status disconnected';}
  finally{pending=false;}
}
async function stream(){
  const controller=new AbortController();let watchdog;
  try{
    const response=await fetch('/api/live.mjpg',{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('Camera unavailable');
    const parser=new MjpegParser(),reader=response.body.getReader();
    while(true){
      clearTimeout(watchdog);watchdog=setTimeout(()=>controller.abort(),3000);
      const {value,done}=await reader.read();if(done)break;
      const frame=parser.push(value).at(-1);if(!frame)continue;
      const bitmap=await createImageBitmap(new Blob([frame.jpeg],{type:'image/jpeg'}));
      const canvas=el('liveCamera');canvas.width=bitmap.width;canvas.height=bitmap.height;
      canvas.getContext('2d').drawImage(bitmap,0,0);bitmap.close();
      el('cameraState').textContent='● Live laptop-annotated camera';
    }
  }catch(error){el('cameraState').textContent='Camera disconnected — retrying';}
  finally{
    clearTimeout(watchdog);controller.abort();
    const canvas=el('liveCamera');canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
    el('visiblePeople').textContent='—';el('livePeople').textContent='CAMERA DISCONNECTED';
    setTimeout(stream,1000);
  }
}
poll();stream();setInterval(poll,300);
