"""Freeze archived board counting; laptop rendered tracks own new arrivals."""
import json
from pathlib import Path
path=Path('/home/arduino/retail-entrance-counter/config.example.json')
config=json.loads(path.read_text())
config['doorway']['counting_mode']='external_visual'
path.write_text(json.dumps(config,indent=2))
