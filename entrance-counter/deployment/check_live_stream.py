"""Read-only camera delivery benchmark; discard all image bytes."""
import urllib.request
import time
import sys
import json
from datetime import datetime
sys.path.insert(0, 'web')

buffer=b''
samples=[]
clock_samples=[]
for _ in range(3):
    before=time.time()
    with urllib.request.urlopen('http://localhost:8081/api/status',timeout=5) as response:
        status=json.load(response)
    after=time.time()
    clock_samples.append((after-before, datetime.fromisoformat(status['updated_at']).timestamp()-(before+after)/2))
offset=min(clock_samples)[1]
started=time.monotonic()
with urllib.request.urlopen('http://localhost:8081/api/live.mjpg',timeout=5) as response:
    while len(samples)<30 and time.monotonic()-started<12:
        buffer+=response.read1(65536)
        while b'\r\n\r\n' in buffer:
            header,body=buffer.split(b'\r\n\r\n',1)
            values={}
            for line in header.decode('ascii').split('\r\n'):
                if ': ' in line:
                    key,value=line.split(': ',1);values[key]=value
            length=int(values['Content-Length'])
            if len(body)<length:break
            samples.append((time.monotonic(),time.time()+offset-float(values['X-Captured-At']),length))
            buffer=body[length:]
ages=sorted(sample[1] for sample in samples)
print({'frames':len(samples),'delivery_fps':(len(samples)-1)/(samples[-1][0]-samples[0][0]),
       'age_p95_ms':ages[int((len(ages)-1)*.95)]*1000,
       'average_jpeg_bytes':sum(sample[2] for sample in samples)/len(samples)})
