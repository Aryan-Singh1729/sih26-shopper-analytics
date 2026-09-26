"""Inspect one live frame and its detector output without changing counts."""
import json
import urllib.request
from pathlib import Path
from laptop_live import extract_parts, LaptopLive
import cv2
import numpy as np

with urllib.request.urlopen('http://127.0.0.1:8081/api/live.mjpg',timeout=8) as response:
    buffer=b''
    while True:
        chunk=response.read1(65536)
        if not chunk:raise RuntimeError('No camera frame')
        frames,buffer=extract_parts(buffer+chunk)
        if frames:
            sequence,captured,jpeg=frames[-1]
            break
image=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
target=Path(__file__).resolve().parents[1]/'data/person-probe.jpg'
target.write_bytes(jpeg)
request=urllib.request.Request('http://127.0.0.1:9011/api/image',data=jpeg,headers={'Content-Type':'image/jpeg'})
with urllib.request.urlopen(request,timeout=8) as response:payload=json.load(response)
print(json.dumps({'sequence':sequence,'shape':image.shape,'detector':payload,
    'accepted':[LaptopLive.person_box(image,box) for box in payload['result']['bounding_boxes']],
    'image':str(target)}))
