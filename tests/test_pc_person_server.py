import importlib.util
import io
import threading
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location('pc_person_server', Path(__file__).parents[1] / 'deployment/pc_person_server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_letterbox_mapping_and_nms():
    output = np.zeros((1, 5, 8400), dtype=np.float32)
    output[0, :, 0] = [320, 320, 100, 200, .9]
    output[0, :, 1] = [320, 320, 100, 200, .8]
    output[0, :, 2] = [100, 100, 20, 20, .2]
    class Session:
        def run(self, _, inputs):
            assert inputs['images'].shape == (1, 3, 640, 640)
            return [output]
    model = module.PersonModel.__new__(module.PersonModel)
    model.session = Session()
    model.lock = threading.Lock()
    image = io.BytesIO()
    Image.new('RGB', (1280, 720)).save(image, format='JPEG')
    result = model.infer(image.getvalue())
    boxes = result['result']['bounding_boxes']
    assert len(boxes) == 1
    assert boxes[0]['label'] == 'person'
    assert (boxes[0]['x'], boxes[0]['y'], boxes[0]['width'], boxes[0]['height']) == (540, 160, 200, 400)


def test_pc_adapter_rescales_and_reuses_connection():
    import json
    from retail_counter.yolox_detector import PcPersonDetector
    class Response:
        status = 200
        def read(self):
            return json.dumps({'result': {'bounding_boxes': [dict(label='person', value=.9, x=100, y=50, width=80, height=200)]}, 'latency_ms': 100}).encode()
    class Connection:
        calls = 0
        def request(self, method, path, body, headers):
            self.calls += 1
            assert headers['Content-Type'] == 'image/jpeg'
            assert Image.open(io.BytesIO(body)).size == (640, 360)
        def getresponse(self):
            return Response()
    detector = PcPersonDetector({'base_url': 'http://127.0.0.1:9010'})
    connection = Connection()
    detector.connection = connection
    image = io.BytesIO()
    Image.new('RGB', (1280, 720)).save(image, format='JPEG')
    for _ in range(2):
        assert detector.infer_jpeg(image.getvalue(), 1280, 720)[0].xyxy == (200, 100, 360, 500)
    assert connection.calls == 2
