"""Bounded read-only live verification; no image storage."""
import argparse,json,time,threading,urllib.request

parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=25);args=parser.parse_args()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
started=time.monotonic();samples=[];sequences=[];error=[]
def stream():
    try:
        with opener.open('http://127.0.0.1:8082/api/live.mjpg',timeout=4) as response:
            buffer=b''
            while time.monotonic()-started<args.seconds:
                chunk=response.read1(65536)
                if not chunk:break
                buffer+=chunk
                while b'\r\n\r\n' in buffer:
                    header,body=buffer.split(b'\r\n\r\n',1)
                    fields=dict(line.split(': ',1) for line in header.decode('ascii').split('\r\n') if ': ' in line)
                    length=int(fields['Content-Length'])
                    if len(body)<length:break
                    samples.append(time.monotonic());sequences.append(int(fields['X-Frame-Sequence']))
                    buffer=body[length:]
    except Exception as issue:error.append(type(issue).__name__)
worker=threading.Thread(target=stream,daemon=True);worker.start()
while time.monotonic()-started<args.seconds:
    try:
        with opener.open('http://127.0.0.1:8082/api/queue',timeout=3) as response:data=json.load(response)
        print(json.dumps({'elapsed':round(time.monotonic()-started,1),'healthy':data['healthy'],'stale':data.get('stale'),
            'visible':data.get('visible_people'),'waiting':data.get('queue_length'),'in_service':data.get('in_service'),
            'current_wait':round(data.get('longest_wait_seconds',0),1),'samples':data.get('wait_samples'),'frames':len(samples)}),flush=True)
    except Exception as issue:print(type(issue).__name__,flush=True)
    time.sleep(1)
print(json.dumps({'frames_received':len(samples),'fps':round((len(samples)-1)/(samples[-1]-samples[0]),1) if len(samples)>1 else 0,
    'largest_frame_gap_seconds':round(max([b-a for a,b in zip(samples,samples[1:])]+[0]),2),
    'distinct_sequences':len(set(sequences)),'stream_error':error}),flush=True)
