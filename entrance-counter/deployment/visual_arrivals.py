"""Durable arrivals derived from the boxes actually rendered on the laptop."""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from retail_counter.timezones import resolve_timezone


def iou(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    area=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
    return area/max(1,aw*ah+bw*bh-area)


class VisualArrivals:
    def __init__(self,path,absence_seconds=1.0):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(path,check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS visual_arrivals(event_id TEXT PRIMARY KEY,timestamp_utc TEXT,local_date TEXT,hour INTEGER,confidence REAL)')
        self.connection.commit()
        self.lock=threading.Lock();self.visits=[];self.absence=absence_seconds
        self.zone=resolve_timezone('Asia/Calcutta')

    def update(self,tracks,now,moment=None):
        moment=moment or datetime.now(timezone.utc)
        local=moment.astimezone(self.zone)
        with self.lock:
            self.visits=[visit for visit in self.visits if now-visit['last_seen']<self.absence]
            available=set(range(len(self.visits)));unmatched=set(range(len(tracks)))
            pairs=sorted([(iou(track['box'],visit['box']),i,j) for i,track in enumerate(tracks) for j,visit in enumerate(self.visits)],reverse=True)
            for score,i,j in pairs:
                if score<.1:break
                if i not in unmatched or j not in available:continue
                visit=self.visits[j];visit['box']=tracks[i]['box'];visit['last_seen']=now
                tracks[i]['visit_id']=visit['id'];unmatched.remove(i);available.remove(j)
            events=[]
            for i in sorted(unmatched):
                identifier=str(uuid.uuid4())
                self.connection.execute('INSERT INTO visual_arrivals VALUES(?,?,?,?,?)',
                    (identifier,moment.isoformat(),local.date().isoformat(),local.hour,float(tracks[i]['score'])))
                self.visits.append({'id':identifier,'box':tracks[i]['box'],'last_seen':now})
                tracks[i]['visit_id']=identifier;events.append(identifier)
            if events:self.connection.commit()
            return events

    def merge(self,history):
        # Old board history is frozen at cutover; new events exist only here.
        with self.lock:
            rows=self.connection.execute('SELECT hour,COUNT(*) FROM visual_arrivals WHERE local_date=? GROUP BY hour',(history['date'],)).fetchall()
            last=self.connection.execute('SELECT MAX(timestamp_utc) FROM visual_arrivals WHERE local_date=?',(history['date'],)).fetchone()[0]
        result=dict(history);hourly=[dict(bucket) for bucket in history['hourly']]
        for hour,count in rows:hourly[hour]['arrivals']+=count
        result['hourly']=hourly;result['total_arrivals']=sum(bucket['arrivals'] for bucket in hourly)
        result['peak_count']=max(bucket['arrivals'] for bucket in hourly)
        result['peak_hours']=[bucket['hour'] for bucket in hourly if bucket['arrivals']==result['peak_count']] if result['peak_count'] else []
        if last:
            last=datetime.fromisoformat(last).astimezone(self.zone).isoformat()
            if not result.get('last_arrival') or last>result['last_arrival']:result['last_arrival']=last
        result['counting_source']='Visible laptop person tracks; archived board events preserved'
        return result

    def today_count(self):
        day=datetime.now(self.zone).date().isoformat()
        with self.lock:return self.connection.execute('SELECT COUNT(*) FROM visual_arrivals WHERE local_date=?',(day,)).fetchone()[0]
