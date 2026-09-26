"""Preserve installed configuration; select local PC tunnel backend."""
import json
from pathlib import Path

root = Path('/home/arduino/retail-entrance-counter')
path = root / 'config.example.json'
config = json.loads(path.read_text())
backup = root / 'data/config-before-pc.json'
if not backup.exists():
    backup.write_text(json.dumps(config, indent=2))
config['model'].update(backend='pc_onnx', base_url='http://127.0.0.1:9010', confidence=.5, request_timeout_seconds=3)
config['camera']['live_fps'] = 15
config['runtime']['metrics_interval_seconds'] = .1
path.write_text(json.dumps(config, indent=2))
