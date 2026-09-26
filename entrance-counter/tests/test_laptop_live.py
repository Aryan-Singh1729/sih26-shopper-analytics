import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'deployment'))
from laptop_live import extract_parts, LaptopLive, overlap
import numpy as np

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
    tracks=[LaptopLive.new_track(image,box,100) for box in boxes]
    assert all(tracks)
    updated=LaptopLive.advance(tracks,image.copy())
    assert len(updated)==2
    assert overlap(updated[0]['box'],updated[1]['box'])==0
