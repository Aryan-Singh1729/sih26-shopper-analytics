"""MediaPipe multi-person detector behind the existing local HTTP interface."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.pc-runtime'))
import io
import threading
import time
import argparse
import numpy as np
from PIL import Image
import mediapipe as mp
from pc_person_server import serve


class MediaPipePersonModel:
    backend = 'MediaPipe EfficientDet-Lite0'
    def __init__(self, model_path):
        options = mp.tasks.vision.ObjectDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            category_allowlist=['person'], score_threshold=.5, max_results=30)
        self.detector = mp.tasks.vision.ObjectDetector.create_from_options(options)
        self.lock = threading.Lock()
        self.timestamp = 0

    def infer(self, jpeg):
        started = time.perf_counter()
        with Image.open(io.BytesIO(jpeg)) as picture:
            if picture.width * picture.height > 16000000:
                raise ValueError('Image too large')
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(picture.convert('RGB')).copy())
        with self.lock:
            self.timestamp = max(self.timestamp+1, int(time.monotonic()*1000))
            result = self.detector.detect_for_video(image, self.timestamp)
        boxes = []
        for detection in result.detections:
            category = detection.categories[0]
            if category.category_name != 'person':
                continue
            box = detection.bounding_box
            boxes.append(dict(label='person', value=float(category.score), x=box.origin_x,
                              y=box.origin_y, width=box.width, height=box.height))
        return {'result': {'bounding_boxes': boxes}, 'latency_ms': (time.perf_counter()-started)*1000,
                'backend': 'MediaPipe EfficientDet-Lite0'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--port', type=int, default=9011)
    args = parser.parse_args()
    serve(MediaPipePersonModel(args.model), args.port)
