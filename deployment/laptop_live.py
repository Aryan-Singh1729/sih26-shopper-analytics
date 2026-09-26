"""Latest-only laptop MediaPipe detection and OpenCV-annotated video, in RAM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.pc-runtime'))
import collections, threading, time, urllib.request
import cv2
import numpy as np
from mediapipe_person_server import MediaPipePersonModel
from visual_arrivals import VisualArrivals

def extract_parts(buffer):
    frames=[]
    while b'\r\n\r\n' in buffer:
        header,body=buffer.split(b'\r\n\r\n',1)
        fields=dict(line.split(': ',1) for line in header.decode('ascii').split('\r\n') if ': ' in line)
        length=int(fields['Content-Length'])
        if not 0<length<2000000:raise ValueError('Invalid frame size')
        if len(body)<length:break
        frames.append((int(fields['X-Frame-Sequence']),float(fields['X-Captured-At']),body[:length]))
        buffer=body[length:]
    if len(buffer)>4000000:raise ValueError('Buffer limit')
    return frames,buffer

def overlap(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    area=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
    return area/max(1,aw*ah+bw*bh-area)

class LaptopLive:
    def __init__(self,board,model_path):
        self.board=board.rstrip('/');self.model=MediaPipePersonModel(model_path)
        self.condition=threading.Condition();self.frames=collections.deque(maxlen=24)
        self.arrivals=VisualArrivals(Path(__file__).resolve().parents[1]/'data/laptop-visual-arrivals.sqlite3')
        self.result=None;self.output=None;self.tracks=[];self.persons=0;self.error=None
        self.inference_ms=0;self.fps=0;self.rendered=0;self.started=time.monotonic();self.last_output_at=0
        for target in (self.capture,self.detect,self.render):threading.Thread(target=target,daemon=True).start()

    def capture(self):
        while True:
            try:
                with urllib.request.urlopen(self.board+'/api/live.mjpg',timeout=5) as response:
                    buffer=b''
                    while True:
                        chunk=response.read1(65536)
                        if not chunk:break
                        parts,buffer=extract_parts(buffer+chunk)
                        if not parts:continue
                        sequence,captured,jpeg=parts[-1]
                        image=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
                        if image is None:continue
                        with self.condition:
                            if self.frames and sequence<=self.frames[-1][0]:self.frames.clear();self.result=None
                            self.frames.append((sequence,captured,jpeg,image));self.error=None;self.condition.notify_all()
            except Exception as error:
                with self.condition:
                    self.frames.clear();self.result=None;self.output=None;self.error=type(error).__name__;self.condition.notify_all()
            time.sleep(.5)

    def detect(self):
        previous=None
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.frames and self.frames[-1][0]!=previous,timeout=1)
                if not self.frames:continue
                frame=self.frames[-1]
                if frame[0]==previous:continue
            previous=frame[0]
            try:
                payload=self.model.infer(frame[2])
                with self.condition:self.result=(frame,payload['result']['bounding_boxes'],time.monotonic());self.inference_ms=payload['latency_ms']
            except Exception as error:self.error='Detector '+type(error).__name__;time.sleep(.2)

    @staticmethod
    def new_track(image,box,confirmed):
        height,width=image.shape[:2];x=max(0,int(box['x']));y=max(0,int(box['y']))
        w=min(width-x,int(box['width']));h=min(height-y,int(box['height']))
        if w<8 or h<16:return None
        tracker=cv2.TrackerKCF_create()
        try:tracker.init(image,(x,y,w,h))
        except cv2.error:return None
        return {'tracker':tracker,'box':(x,y,w,h),'score':box['value'],'confirmed':confirmed}

    @staticmethod
    def advance(tracks,image):
        valid=[]
        for track in tracks:
            try:ok,box=track['tracker'].update(image)
            except cv2.error:continue
            if ok:track['box']=box;valid.append(track)
        return valid

    def render(self):
        previous=None;last_result=None
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.frames and self.frames[-1][0]!=previous,timeout=.5)
                if not self.frames:self.tracks=[];continue
                history=list(self.frames);frame=history[-1];result=self.result
                if frame[0]==previous:continue
            if previous is not None and frame[0]<previous:self.tracks=[];last_result=None
            if previous is not None:self.tracks=self.advance(self.tracks,frame[3])
            previous=frame[0];now=time.monotonic()
            if result and result[0][0]!=last_result:
                seed,boxes,confirmed=result;last_result=seed[0]
                if now-confirmed<.5 and any(item[0]==seed[0] for item in history):
                    new=[]
                    for box in boxes:
                        track=self.new_track(seed[3],box,confirmed)
                        if track:new.append(track)
                    for intermediate in history:
                        if intermediate[0]>seed[0]:new=self.advance(new,intermediate[3])
                    retained=[track for track in self.tracks if now-track['confirmed']<.8 and all(overlap(track['box'],other['box'])<.1 for other in new)]
                    self.tracks=new+retained
            self.tracks=[track for track in self.tracks if now-track['confirmed']<1.2]
            self.arrivals.update(self.tracks,now)
            height,width=frame[3].shape[:2]
            public_tracks=[{'id':track['visit_id'],'box':[track['box'][0]/width,track['box'][1]/height,track['box'][2]/width,track['box'][3]/height]} for track in self.tracks]
            image=frame[3].copy()
            for track in self.tracks:
                x,y,w,h=map(int,track['box']);cv2.rectangle(image,(x,y),(x+w,y+h),(70,255,130),2)
                cv2.putText(image,f"PERSON {round(track['score']*100)}%",(x,max(15,y-5)),cv2.FONT_HERSHEY_SIMPLEX,.45,(70,255,130),1,cv2.LINE_AA)
            ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,80])
            if ok:
                with self.condition:
                    self.public_tracks=public_tracks
                    self.persons=len(self.tracks);self.output=(frame[0],frame[1],encoded.tobytes());self.last_output_at=now
                    self.rendered+=1;self.fps=self.rendered/max(.001,now-self.started);self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            age=time.monotonic()-self.last_output_at
            fresh=age<1.5
            return {'healthy':fresh and self.error is None,'persons':self.persons if fresh else 0,'fps':self.fps,
                    'inference_ms':self.inference_ms,'error':self.error,'backend':'Laptop MediaPipe + OpenCV KCF','annotated':True,
                    'tracks':getattr(self,'public_tracks',[]) if fresh else [],
                    'frame_sequence':self.output[0] if self.output else None,'frame_age_ms':round(age*1000)}
