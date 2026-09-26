"""Short, read-only live verification; never stores camera images."""
import json
import time
import urllib.request

end = time.monotonic() + 45
while time.monotonic() < end:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/status', timeout=2) as response:
            data = json.load(response)
        detection = data.get('detection', {})
        print(json.dumps({'time': data.get('updated_at'), 'count': data.get('counter', {}).get('entries_today'),
                          'persons': detection.get('persons'), 'present': detection.get('present'),
                          'raw_persons': detection.get('raw_persons'), 'raw_confidence': detection.get('raw_confidence'),
                          'rejected': detection.get('ignored_outside_area'),
                          'boxes': detection.get('boxes'), 'sequence': detection.get('frame_sequence'),
                          'frame_age': data.get('frame_age_seconds')}), flush=True)
    except Exception as error:
        print(type(error).__name__, flush=True)
    time.sleep(.2)
