"""Latest-only laptop MediaPipe detection and OpenCV-annotated video, in RAM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.pc-runtime'))
import collections, threading, time, urllib.request
import cv2
import numpy as np
from mediapipe_person_server import MediaPipePersonModel
from track_continuity import EmptyViewGate, advance_tracks, match_score, overlap, reconcile_tracks
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


class HybridPersonTracker:
    """Follow image features when the primary object tracker loses a person."""

    def __init__(self, image, box, primary_factory=None):
        self.box=tuple(map(float,box))
        self.primary_factory=primary_factory or cv2.TrackerCSRT_create
        self.primary=self.primary_factory()
        self.primary.init(image,tuple(map(int,self.box)))
        self.gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        self.points=self._features(self.gray,self.box)

    @staticmethod
    def _features(gray,box):
        x,y,w,h=map(int,box)
        height,width=gray.shape
        inset_x=max(2,int(w*.08));inset_y=max(2,int(h*.08))
        left=max(0,x+inset_x);top=max(0,y+inset_y)
        right=min(width,x+w-inset_x);bottom=min(height,y+h-inset_y)
        if right<=left or bottom<=top:return None
        mask=np.zeros_like(gray)
        mask[top:bottom,left:right]=255
        return cv2.goodFeaturesToTrack(gray,maxCorners=80,qualityLevel=.01,minDistance=4,mask=mask)

    def update(self,image):
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        flow_box=None
        if self.points is not None and len(self.points)>=5:
            moved,status,_=cv2.calcOpticalFlowPyrLK(self.gray,gray,self.points,None)
            if moved is not None and status is not None:
                good=status.ravel()==1
                if int(good.sum())>=5:
                    deltas=(moved[good]-self.points[good]).reshape(-1,2)
                    offset=np.median(deltas,axis=0)
                    spread=np.median(np.linalg.norm(deltas-offset,axis=1))
                    if spread<max(6,min(self.box[2:])*.08):
                        x,y,w,h=self.box
                        flow_box=(x+float(offset[0]),y+float(offset[1]),w,h)
        try:primary_ok,primary_box=self.primary.update(image) if self.primary is not None else (False,None)
        except cv2.error:primary_ok,primary_box=False,None
        if primary_ok and flow_box is not None:
            distance=np.hypot(primary_box[0]-flow_box[0],primary_box[1]-flow_box[1])
            if distance>max(12,min(self.box[2:])*.25):primary_ok=False
        if primary_ok:box=tuple(map(float,primary_box))
        elif flow_box is not None:
            box=flow_box
            # The next detector result will re-anchor a fresh tracker. Rebuilding
            # CSRT on every flow frame costs more than the frame itself.
            self.primary=None
        else:
            self.gray=gray;self.points=None
            return False,None
        self.box=box
        self.gray=gray
        self.points=self._features(gray,box)
        return True,box


def draw_person_boxes(image,tracks):
    for track in tracks:
        if track.get('predicted'):continue
        x,y,w,h=map(int,track['box'])
        cv2.rectangle(image,(x,y),(x+w,y+h),(70,255,130),2)
        cv2.putText(image,'PERSON',(x,max(15,y-5)),cv2.FONT_HERSHEY_SIMPLEX,.45,(70,255,130),1,cv2.LINE_AA)
    return image


def confirmed_person_tracks(image,boxes):
    """Only current detector boxes; never extrapolate or retain rectangles."""
    tracks=[]
    for box in boxes:
        rectangle=LaptopLive.person_box(image,box)
        if rectangle is None:continue
        if any(overlap(rectangle,track['box'])>.6 for track in tracks):continue
        tracks.append({'box':rectangle,'score':box['value']})
    return tracks


def has_recent_motion(previous,image,box):
    if previous is None or previous.shape!=image.shape:return False
    height,width=image.shape[:2]
    x,y,w,h=map(int,box)
    left=max(0,x);top=max(0,y);right=min(width,x+w);bottom=min(height,y+h)
    if right<=left or bottom<=top:return False
    old=cv2.cvtColor(previous,cv2.COLOR_BGR2GRAY).astype(np.int16)
    new=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.int16)
    difference=new-old
    global_brightness=np.median(difference[::8,::8])
    changed=np.abs(difference[top:bottom,left:right]-global_brightness)>28
    return float(np.mean(changed))>=.08

class LaptopLive:
    def __init__(self,board,model_path):
        self.board=board.rstrip('/');self.model=MediaPipePersonModel(model_path,confidence=.30)
        self.condition=threading.Condition();self.frames=collections.deque(maxlen=24)
        self.arrivals=VisualArrivals(Path(__file__).resolve().parents[1]/'data/laptop-visual-arrivals.sqlite3')
        self.empty_gate=EmptyViewGate(2.0)
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
                with self.condition:
                    self.result=(frame,payload['result']['bounding_boxes'],time.monotonic())
                    self.inference_ms=payload['latency_ms'];self.condition.notify_all()
            except Exception as error:self.error='Detector '+type(error).__name__;time.sleep(.2)

    @staticmethod
    def person_box(image,box):
        height,width=image.shape[:2]
        # Display actual person detections even when feet or an entering body
        # touch the edge. The old whole-body margin hid valid detector boxes.
        values=[box[key] for key in ('x','y','width','height','value')]
        if not all(np.isfinite(value) for value in values):return None
        x=max(0,int(box['x']));y=max(0,int(box['y']))
        right=min(width,int(box['x']+box['width']))
        bottom=min(height,int(box['y']+box['height']))
        w=right-x;h=bottom-y
        if w<8 or h<16:return None
        # Entrance view expects standing/walking full bodies. Reject the short,
        # wide bedding fragment observed as a false person at the bottom edge.
        if h < height*.25 or h < w*1.2:return None
        return x,y,w,h

    @staticmethod
    def new_track(image,box,confirmed):
        person_box=LaptopLive.person_box(image,box)
        if person_box is None:return None
        try:tracker=HybridPersonTracker(image,person_box)
        except cv2.error:return None
        return {'tracker':tracker,'box':person_box,'score':box['value'],'confirmed':confirmed}

    @staticmethod
    def select_detection_tracks(image,boxes,previous_image,current_tracks,confirmed):
        selected=[]
        for box in boxes:
            person_box=LaptopLive.person_box(image,box)
            if person_box is None:continue
            known=any(match_score(track['box'],person_box) is not None for track in current_tracks)
            if not known and not has_recent_motion(previous_image,image,person_box):continue
            candidate=LaptopLive.new_track(image,box,confirmed)
            if candidate is not None:selected.append(candidate)
        return selected

    @staticmethod
    def advance(tracks,image):
        return advance_tracks(tracks,image,time.monotonic())

    def render(self):
        last_result=None
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.result is not None and self.result[0][0]!=last_result,timeout=.5)
                result=self.result
                if result is None or result[0][0]==last_result:continue
            frame,boxes,confirmed=result;last_result=frame[0]
            now=time.monotonic()
            if now-confirmed>1.0:continue
            # Draw on precisely the frame analyzed by the detector. A missing
            # detection removes its rectangle immediately, without deleting
            # the separate arrival identity used to suppress duplicate counts.
            self.tracks=confirmed_person_tracks(frame[3],boxes)
            # Cropped people still prevent the empty-view gate from rearming.
            clear=self.empty_gate.observe(now,len(self.tracks),not self.tracks)
            self.arrivals.update(self.tracks,now,clear=clear)
            height,width=frame[3].shape[:2]
            visible_tracks=[track for track in self.tracks if not track.get('predicted')]
            public_tracks=[{'id':track['visit_id'],'box':[track['box'][0]/width,track['box'][1]/height,track['box'][2]/width,track['box'][3]/height]} for track in visible_tracks]
            image=draw_person_boxes(frame[3].copy(),visible_tracks)
            ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,80])
            if ok:
                with self.condition:
                    self.public_tracks=public_tracks
                    self.persons=len(visible_tracks);self.output=(frame[0],frame[1],encoded.tobytes());self.last_output_at=now
                    self.rendered+=1;self.fps=self.rendered/max(.001,now-self.started);self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            age=time.monotonic()-self.last_output_at
            fresh=age<1.5
            return {'healthy':fresh and self.error is None,'persons':self.persons if fresh else 0,'fps':self.fps,
                    'inference_ms':self.inference_ms,'error':self.error,'backend':'Laptop MediaPipe fresh detections','annotated':True,
                    'tracks':getattr(self,'public_tracks',[]) if fresh else [],
                    'frame_sequence':self.output[0] if self.output else None,'frame_age_ms':round(age*1000)}
