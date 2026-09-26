"""Unified laptop dashboard with durable arrivals from its visible person tracks."""
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


def serve(board, port):
    from laptop_live import LaptopLive
    live=LaptopLive(board,Path(__file__).resolve().parents[1]/'models/person/efficientdet_lite0.tflite')
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            if route == '/api/live.mjpg':
                try:
                    self.send_response(200)
                    self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
                    self.end_headers()
                    previous=None
                    while True:
                        with live.condition:
                            live.condition.wait_for(lambda:live.output and live.output[0]!=previous,timeout=2)
                            if not live.output or live.output[0]==previous:break
                            sequence,captured,jpeg=live.output
                        previous=sequence
                        header=(f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\nX-Frame-Sequence: {sequence}\r\nX-Captured-At: {captured}\r\n\r\n').encode()
                        self.wfile.write(header+jpeg+b'\r\n');self.wfile.flush()
                except (OSError, urllib.error.URLError):
                    pass
                return
            if route == '/api/live-status':
                import json
                payload=json.dumps(live.snapshot()).encode()
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
                return
            if route in ('/api/footfall', '/api/status', '/api/frame.jpg'):
                try:
                    with urllib.request.urlopen(board.rstrip('/') + self.path, timeout=4) as response:
                        payload = response.read(200000)
                except (urllib.error.URLError, TimeoutError, OSError):
                    self.send_error(503, 'Cannot reach entrance event history on UNO Q')
                    return
                self.send_response(200)
                if route in ('/api/footfall','/api/status'):
                    import json
                    data=json.loads(payload)
                    if route=='/api/footfall':data=live.arrivals.merge(data)
                    else:
                        data['counter']['entries_today']+=live.arrivals.today_count()
                        data['counter']['current_occupancy']=max(0,data['counter']['entries_today']-data['counter'].get('exits_today',0))
                        data['counter']['counting_source']='Laptop visible person tracks'
                    payload=json.dumps(data).encode()
                self.send_header('Content-Type', 'image/jpeg' if route == '/api/frame.jpg' else 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if route in ('/mjpeg.mjs', '/person-tracker.mjs'):
                source = Path(__file__).resolve().parents[1] / 'web' / route.lstrip('/')
                payload = source.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

        def log_message(self, *_):
            pass
    root = Path(__file__).resolve().parents[1] / 'footfall-web'
    ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=str(root))).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--board', default='http://10.143.116.243:8080')
    parser.add_argument('--port', type=int, default=8081)
    args = parser.parse_args()
    serve(args.board, args.port)
