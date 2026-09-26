"""Loopback-only full-person ONNX inference; access remotely via SSH tunnel."""
import argparse
import io
import json
import threading
import time
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import onnxruntime as ort
from PIL import Image


class PersonModel:
    def __init__(self, path, threads=4):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(path, options, providers=['CPUExecutionProvider'])
        if self.session.get_inputs()[0].shape != [1, 3, 640, 640]:
            raise ValueError('Expected static 640x640 RGB model')
        self.lock = threading.Lock()

    def infer(self, jpeg):
        started = time.perf_counter()
        with Image.open(io.BytesIO(jpeg)) as image:
            width, height = image.size
            if width * height > 16000000:
                raise ValueError('Image too large')
            ratio = min(640 / width, 640 / height)
            resized = image.convert('RGB').resize((round(width * ratio), round(height * ratio)))
            pad_x, pad_y = (640 - resized.width) // 2, (640 - resized.height) // 2
            canvas = Image.new('RGB', (640, 640), (114, 114, 114))
            canvas.paste(resized, (pad_x, pad_y))
            tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255
        with self.lock:
            output = self.session.run(None, {'images': tensor})[0]
        if output.shape != (1, 5, 8400):
            raise ValueError('Unexpected single-class YOLO output')
        candidates = output[0].T
        candidates = candidates[np.isfinite(candidates).all(axis=1) & (candidates[:, 4] >= .5)]
        boxes = []
        for cx, cy, bw, bh, score in candidates[candidates[:, 4].argsort()[::-1]]:
            x1, y1 = max(0., (cx-bw/2-pad_x)/ratio), max(0., (cy-bh/2-pad_y)/ratio)
            x2, y2 = min(width-1., (cx+bw/2-pad_x)/ratio), min(height-1., (cy+bh/2-pad_y)/ratio)
            if x2 <= x1 or y2 <= y1:
                continue
            area = (x2-x1)*(y2-y1)
            duplicate = False
            for box in boxes:
                ax, ay, aw, ah = (box[k] for k in ('x', 'y', 'width', 'height'))
                intersection = max(0., min(x2, ax+aw)-max(x1, ax))*max(0., min(y2, ay+ah)-max(y1, ay))
                if intersection / (area + aw*ah - intersection) > .45:
                    duplicate = True
                    break
            if not duplicate:
                boxes.append(dict(label='person', value=float(score), x=float(x1), y=float(y1), width=float(x2-x1), height=float(y2-y1)))
        return {'result': {'bounding_boxes': boxes}, 'latency_ms': (time.perf_counter()-started)*1000}


def serve(model, port):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        def do_GET(self):
            self.reply(200, {'ready': True, 'backend': getattr(model, 'backend', 'PC ONNX Runtime CPU'), 'class': 'person'})

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.path != '/api/image' or not 0 < length <= 2000000:
                    self.reply(400, {'error': 'Invalid image request'})
                    return
                self.connection.settimeout(3)
                body = self.rfile.read(length)
                if self.headers.get_content_type() == 'multipart/form-data':
                    boundary = self.headers.get_param('boundary')
                    if not boundary:
                        raise ValueError('Missing boundary')
                    body = body.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--' + boundary.encode(), 1)[0]
                self.reply(200, model.infer(body))
            except Exception:
                self.reply(400, {'error': 'Image inference failed'})

        def reply(self, code, payload):
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--port', type=int, default=9010)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    serve(PersonModel(args.model, args.threads), args.port)
