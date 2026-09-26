"""Select tested PC MediaPipe runtime; preserve saved event history."""
import json
from pathlib import Path
root=Path('/home/arduino/retail-entrance-counter')
path=root/'config.example.json'
config=json.loads(path.read_text())
backup=root/'data/config-before-mediapipe.json'
if not backup.exists():backup.write_text(json.dumps(config,indent=2))
config['model'].update(backend='pc_onnx',base_url='http://127.0.0.1:9011',confidence=.5,request_timeout_seconds=3)
config['doorway']['counting_mode']='per_person_tracks'
config['tracking']['new_track_threshold']=.5
config['tracking']['minimum_hits']=1
config['runtime']['metrics_interval_seconds']=.1
config['camera'].update(live_width=640,live_quality=70,live_fps=15)
path.write_text(json.dumps(config,indent=2))
