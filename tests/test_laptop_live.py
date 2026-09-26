import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'deployment'))
import laptop_live
from laptop_live import extract_parts, LaptopLive, overlap
import numpy as np

def test_live_box_label_has_no_confidence_percentage(monkeypatch):
    labels=[]
    monkeypatch.setattr(laptop_live.cv2,'putText',lambda image,text,*args:labels.append(text))
    image=np.zeros((120,240,3),dtype=np.uint8)
    laptop_live.draw_person_boxes(image,[{'box':(20,20,60,80),'score':.39}])
    assert labels==['PERSON']

def test_short_wide_bedding_fragment_is_not_a_full_person():
    image=np.zeros((360,640,3),dtype=np.uint8)
    bedding=dict(x=0,y=268,width=87,height=89,value=.36)
    person=dict(x=95,y=63,width=112,height=297,value=.39)
    assert LaptopLive.person_box(image,bedding) is None
    assert LaptopLive.person_box(image,person)==(95,63,112,297)

def test_confirmed_boxes_disappear_on_next_empty_detection():
    image=np.zeros((240,320,3),dtype=np.uint8)
    box=dict(x=100,y=20,width=80,height=180,value=.8)
    tracks=laptop_live.confirmed_person_tracks(image,[box])
    assert len(tracks)==1
    assert 'tracker' not in tracks[0]
    assert laptop_live.confirmed_person_tracks(image,[])==[]

def test_confirmed_boxes_keep_two_people_but_suppress_duplicate_rectangle():
    image=np.zeros((240,320,3),dtype=np.uint8)
    boxes=[dict(x=20,y=20,width=60,height=180,value=.9),
           dict(x=22,y=21,width=60,height=180,value=.8),
           dict(x=210,y=20,width=60,height=180,value=.85)]
    assert len(laptop_live.confirmed_person_tracks(image,boxes))==2

def test_detection_flicker_and_cropped_exit_do_not_create_new_arrival(tmp_path):
    from visual_arrivals import VisualArrivals
    from track_continuity import EmptyViewGate
    counter=VisualArrivals(tmp_path/'events.sqlite3')
    gate=EmptyViewGate(2.0)
    image=np.zeros((240,320,3),dtype=np.uint8)
    full=dict(x=100,y=20,width=80,height=180,value=.8)
    partial=dict(x=0,y=20,width=80,height=180,value=.8)
    def update(at,boxes):
        tracks=laptop_live.confirmed_person_tracks(image,boxes)
        return counter.update(tracks,at,clear=gate.observe(at,len(boxes),not boxes))
    try:
        assert len(update(0,[full]))==1
        assert update(.2,[])==[]
        assert update(.5,[full])==[]
        assert update(1,[partial])==[]
        assert update(1.2,[])==[]
        assert update(1.5,[full])==[]
        assert update(2,[])==[]
        assert update(4.1,[])==[]
        assert len(update(4.3,[full]))==1
    finally:counter.connection.close()

def test_frame_parser_split_and_multiple_frames():
    packet=b'--frame\r\nContent-Length: 3\r\nX-Frame-Sequence: 4\r\nX-Captured-At: 100.1\r\n\r\nabc\r\n'
    frames,remaining=extract_parts(packet[:-4])
    assert frames==[]
    frames,remaining=extract_parts(remaining+packet[-4:]+packet)
    assert len(frames)==2
    assert frames[0]==(4,100.1,b'abc')

def test_native_tracker_supports_two_independent_person_boxes():
    image=np.random.default_rng(1).integers(0,255,(180,320,3),dtype=np.uint8)
    boxes=[dict(x=20,y=15,width=60,height=140,value=.9),dict(x=180,y=20,width=65,height=130,value=.8)]
    tracks=[LaptopLive.new_track(image,box,time.monotonic()) for box in boxes]
    assert all(tracks)
    updated=LaptopLive.advance(tracks,image.copy())
    assert len(updated)==2
    assert overlap(updated[0]['box'],updated[1]['box'])==0

def test_person_box_is_visible_when_touching_frame_edge():
    image=np.zeros((360,640,3),dtype=np.uint8)
    now=time.monotonic()
    partial=dict(x=570,y=80,width=70,height=250,value=.9)
    centered=dict(x=200,y=35,width=120,height=300,value=.9)
    assert LaptopLive.person_box(image,partial)==(570,80,70,250)
    assert LaptopLive.new_track(image,centered,now) is not None

def test_image_motion_keeps_person_box_on_moving_subject_when_primary_loses():
    rng=np.random.default_rng(5)
    patch=rng.integers(0,256,(140,70,3),dtype=np.uint8)
    first=np.zeros((240,320,3),dtype=np.uint8)
    second=first.copy()
    first[40:180,90:160]=patch
    second[40:180,99:169]=patch

    class LostPrimary:
        def init(self,_image,_box):pass
        def update(self,_image):return False,None

    assert hasattr(laptop_live,'HybridPersonTracker')
    tracker=laptop_live.HybridPersonTracker(first,(90,40,70,140),primary_factory=LostPrimary)
    ok,box=tracker.update(second)
    assert ok
    assert abs(box[0]-99)<=3
    assert abs(box[1]-40)<=3

def test_flow_fallback_does_not_rebuild_expensive_primary_each_frame():
    patch=np.random.default_rng(7).integers(0,256,(140,70,3),dtype=np.uint8)
    images=[]
    for x in (90,98,106):
        image=np.zeros((240,320,3),dtype=np.uint8)
        image[40:180,x:x+70]=patch
        images.append(image)
    starts=[]

    class LostPrimary:
        def init(self,_image,_box):starts.append(1)
        def update(self,_image):return False,None

    tracker=laptop_live.HybridPersonTracker(images[0],(90,40,70,140),primary_factory=LostPrimary)
    assert tracker.update(images[1])[0]
    assert tracker.update(images[2])[0]
    assert len(starts)==1

def test_predicted_box_is_not_drawn_over_a_door():
    image=np.zeros((120,240,3),dtype=np.uint8)
    tracks=[
        {'box':(20,20,60,80),'score':.8,'predicted':True},
        {'box':(120,20,60,80),'score':.9,'predicted':False},
    ]
    assert hasattr(laptop_live,'draw_person_boxes')
    rendered=laptop_live.draw_person_boxes(image,tracks)
    assert tuple(rendered[20,20])==(0,0,0)
    assert tuple(rendered[20,120])==(70,255,130)

def test_static_clothes_cannot_start_a_new_person_track():
    assert hasattr(laptop_live,'has_recent_motion')
    background=np.random.default_rng(11).integers(0,256,(180,320,3),dtype=np.uint8)
    current=background.copy()
    current=np.clip(current.astype(np.int16)+4,0,255).astype(np.uint8)
    assert not laptop_live.has_recent_motion(background,current,(90,20,80,140))

def test_two_moving_people_each_pass_motion_check():
    assert hasattr(laptop_live,'has_recent_motion')
    background=np.zeros((180,320,3),dtype=np.uint8)
    current=background.copy()
    current[20:160,40:100]=180
    current[20:160,200:260]=190
    assert laptop_live.has_recent_motion(background,current,(40,20,60,140))
    assert laptop_live.has_recent_motion(background,current,(200,20,60,140))

def test_new_track_needs_motion_but_existing_track_can_refresh_while_still():
    assert hasattr(LaptopLive,'select_detection_tracks')
    background=np.zeros((240,320,3),dtype=np.uint8)
    image=background.copy()
    box=dict(x=100,y=20,width=80,height=180,value=.8)
    assert LaptopLive.select_detection_tracks(image,[box],background,[],1.0)==[]
    image[20:200,100:180]=180
    started=LaptopLive.select_detection_tracks(image,[box],background,[],1.0)
    assert len(started)==1
    refreshed=LaptopLive.select_detection_tracks(image,[box],image,started,1.2)
    assert len(refreshed)==1

def test_static_false_detection_does_not_build_expensive_tracker(monkeypatch):
    background=np.zeros((240,320,3),dtype=np.uint8)
    box=dict(x=100,y=20,width=80,height=180,value=.8)
    def unexpected_tracker(*_args):
        raise AssertionError('Static detection must be rejected before tracker creation')
    monkeypatch.setattr(LaptopLive,'new_track',staticmethod(unexpected_tracker))
    assert LaptopLive.select_detection_tracks(background,[box],background,[],1.0)==[]
