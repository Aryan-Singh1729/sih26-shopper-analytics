"""Queue dashboard shares live annotated video without modifying entrance counts."""
import argparse,json,threading,time,urllib.request
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from functools import partial
from queue_analytics import QueueAnalytics,validate

ROOT=Path(__file__).resolve().parents[1]
DEFAULT={'mode':'whole_frame','counters':[{'id':'Counter 1','open':True,'service_enabled':False,'queue':[0,0,.5,1],'service':[.05,.75,.4,.2]},
                     {'id':'Counter 2','open':False,'service_enabled':False,'queue':[.5,0,.5,1],'service':[.55,.75,.4,.2]}],
         'fallback_service_seconds':45,'target_wait_seconds':120,'congestion_queue_length':5}

def serve(source,port):
    # Explicit direct loopback transport: no Windows proxy discovery for local video.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    path=ROOT/'data/queue-config.json'
    config=json.loads(path.read_text()) if path.exists() else DEFAULT
    analytics=QueueAnalytics(config);lock=threading.Lock();state={'healthy':False,'counters':[]};last_good=0
    def poll():
        nonlocal state,last_good
        while True:
            try:
                with opener.open(source+'/api/live-status',timeout=3) as response:live=json.load(response)
                now=time.monotonic()
                with lock:
                    if live['healthy']:
                        last_good=now;state=analytics.update(live.get('tracks',[]),now,True)
                        state.update(stale=False,frame_sequence=live.get('frame_sequence'),frame_age_ms=live.get('frame_age_ms'))
                    elif now-last_good<2:
                        state=dict(state,stale=True,message='Brief camera stall; waiting for fresh frames')
                    else:
                        state=analytics.update([],now,False)
                        state['message']='Camera frames stale: '+str(live.get('error') or 'capture delayed')
            except Exception as error:
                with lock:
                    if time.monotonic()-last_good<2:state=dict(state,stale=True,message='Reconnecting live analytics')
                    else:
                        state=analytics.update([],time.monotonic(),False)
                        state['message']='Shared video server unavailable: '+type(error).__name__
            time.sleep(.15)
    threading.Thread(target=poll,daemon=True).start()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/api/queue','/api/config'):
                with lock:payload=json.dumps(state if self.path=='/api/queue' else analytics.config).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
            if self.path in ('/api/live.mjpg','/mjpeg.mjs'):
                try:
                    with opener.open(source+self.path,timeout=4) as response:
                        self.connection.settimeout(5)
                        self.send_response(200);self.send_header('Content-Type',response.headers['Content-Type']);self.end_headers()
                        while True:
                            chunk=response.read1(65536)
                            if not chunk:break
                            self.wfile.write(chunk);self.wfile.flush()
                except OSError:pass
                return
            super().do_GET()
        def do_POST(self):
            nonlocal analytics,state
            if self.path!='/api/config':self.send_error(404);return
            # Loopback-only settings; reject cross-origin browser writes.
            if self.headers.get('Origin') not in (None,f'http://localhost:{port}',f'http://127.0.0.1:{port}'):
                self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<20000:raise ValueError('Invalid body size')
                config=validate(json.loads(self.rfile.read(length)))
                with lock:
                    path.parent.mkdir(exist_ok=True);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(config,indent=2));temporary.replace(path)
                    analytics=QueueAnalytics(config);state={'healthy':False,'counters':[]}
                self.send_response(204);self.end_headers()
            except (ValueError,TypeError,KeyError):self.send_error(400,'Invalid zones or thresholds')
        def end_headers(self):self.send_header('Cache-Control','no-store');super().end_headers()
        def log_message(self,*_):pass
    ThreadingHTTPServer(('127.0.0.1',port),partial(Handler,directory=str(ROOT/'queue-web'))).serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='http://127.0.0.1:8081');parser.add_argument('--port',type=int,default=8082)
    args=parser.parse_args();serve(args.source.rstrip('/'),args.port)
