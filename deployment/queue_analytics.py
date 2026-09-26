"""Anonymous zone occupancy and observed queue-to-service timing, not footfall."""
import math
from collections import deque


def alert_level(count):
    return 'red' if count>2 else ('brown' if count==2 else 'normal')


def validate(config):
    if not isinstance(config,dict):raise ValueError('Expected configuration object')
    if config.get('mode','zones') not in ('zones','whole_frame'):raise ValueError('Unknown counting mode')
    counters=config.get('counters',[])
    if not 1<=len(counters)<=8:raise ValueError('Use 1 to 8 counters')
    identifiers=set()
    for counter in counters:
        identifier=counter.get('id')
        if not isinstance(identifier,str) or not identifier or identifier in identifiers:raise ValueError('Counter IDs must be unique')
        identifiers.add(identifier)
        if not isinstance(counter.get('open'),bool):raise ValueError('Set each counter open or closed')
        if not isinstance(counter.get('service_enabled',True),bool):raise ValueError('Service enabled must be boolean')
        for key in ('queue','service'):
            rect=counter.get(key,[])
            if len(rect)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect):raise ValueError('Zones need four normalized coordinates')
            x,y,w,h=rect
            if min(x,y)<0 or min(w,h)<=0 or x+w>1.00001 or y+h>1.00001:raise ValueError('Zones must fit within the image')
    for key in ('fallback_service_seconds','target_wait_seconds','congestion_queue_length'):
        value=config.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Thresholds must be positive')
    return config


class QueueAnalytics:
    def __init__(self,config):
        self.config=validate(config);self.people={};self.waits=deque(maxlen=1000);self.services=deque(maxlen=1000)
        self.arrivals=deque();self.started=None;self.latest=None;self.completed_wait=0;self.completed_count=0

    def whole_frame(self,tracks,now):
        # Reassociate brief detector ID changes before declaring departures.
        used=set();reserved={track['id'] for track in tracks}
        for track in tracks:
            identifier=track['id'];box=track['box']
            if identifier not in self.people:
                candidates=[]
                for key,person in self.people.items():
                    if key in used or key in reserved or now-person['last']>2:continue
                    a=person['box'];x,y,w,h=box
                    area=max(0,min(a[0]+a[2],x+w)-max(a[0],x))*max(0,min(a[1]+a[3],y+h)-max(a[1],y))
                    score=area/max(.000001,a[2]*a[3]+w*h-area)
                    if score>=.2:candidates.append((score,key))
                if candidates:identifier=max(candidates)[1]
            if identifier in used:continue
            used.add(identifier)
            if identifier not in self.people:
                self.people[identifier]={'since':now,'last':now,'box':box};self.arrivals.append(now)
            self.people[identifier].update(last=now,box=box)
        for identifier,person in list(self.people.items()):
            if now-person['last']>=2:
                duration=max(0,person['last']-person['since'])
                self.waits.append(duration);self.completed_wait+=duration;self.completed_count+=1
                del self.people[identifier]
        while self.arrivals and self.arrivals[0]<now-60:self.arrivals.popleft()
        observed=max(1,min(60,now-self.started));rate=len(self.arrivals)/observed
        duration=lambda p:max(0,(now if now-p['last']<1 else p['last'])-p['since'])
        visible={key:p for key,p in self.people.items() if key in used}
        waits=[duration(person) for person in visible.values()];count=len(waits)
        rows=[]
        for index,counter in enumerate(self.config['counters']):
            members=[p for p in visible.values() if min(len(self.config['counters'])-1,int((p['box'][0]+p['box'][2]/2)*len(self.config['counters'])))==index]
            rows.append(dict(counter,waiting=len(members),in_service=0,longest_wait_seconds=max([duration(p) for p in members]+[0])))
        opened=sum(c['open'] for c in self.config['counters']);assumption=self.config['fallback_service_seconds']
        predicted=max(0,count+(rate-opened/assumption)*120)
        extra=min(len(rows)-opened,max(0,math.ceil(rate*assumption+count*assumption/self.config['target_wait_seconds'])-opened))
        return {'healthy':True,'mode':'whole_frame','counters':rows,'queue_length':count,'in_service':0,'outside_people':0,
            'visible_people':len(tracks),'longest_wait_seconds':max(waits+[0]),'total_wait_seconds':self.completed_wait+sum(duration(p) for p in self.people.values()),
            'average_current_wait_seconds':sum(waits)/count if count else None,
            'average_wait_seconds':self.completed_wait/self.completed_count if self.completed_count else None,'wait_samples':self.completed_count,
            'average_service_seconds':None,'service_samples':0,'service_calibrated':False,
            'forecast_queue_2min':round(predicted,1) if observed>=30 else None,'forecast_ready':observed>=30,'arrival_rate_per_minute':round(rate*60,1),
            'service_basis':'Configured assumption; no real checkout service setup',
            'congested':count>=self.config['congestion_queue_length'],'additional_counters':extra if count else 0,
            'recommendation':f'Consider opening {extra} additional counter(s) once checkout is configured' if extra and count else 'Demo waiting-area monitoring; service timing disabled',
            'people':[{'id':key[-8:],'wait_seconds':round(duration(p),1)} for key,p in visible.items()]}

    def zone(self,box):
        x,y,w,h=box;point=(x+w/2,y+h*.9)
        # Service has priority over queue when rectangles overlap.
        for kind in ('service','queue'):
            for counter in self.config['counters']:
                if kind=='service' and not counter.get('service_enabled',True):continue
                rx,ry,rw,rh=counter[kind]
                if rx<=point[0]<=rx+rw and ry<=point[1]<=ry+rh:return counter['id'],kind
        return None,'outside'

    def update(self,tracks,now,healthy=True):
        if self.started is None:self.started=now
        if not healthy:
            self.people.clear();self.arrivals.clear();self.started=None;self.latest=None
            return {'healthy':False,'message':'Camera unavailable; occupancy and timing paused','counters':[]}
        if self.config.get('mode')=='whole_frame':
            self.latest=self.whole_frame(tracks,now)
            self.latest['alert_level']=alert_level(max([row['waiting'] for row in self.latest['counters']]+[0]))
            for row in self.latest['counters']:row['alert_level']=alert_level(row['waiting'])
            return self.latest
        counts={c['id']:{'waiting':0,'in_service':0} for c in self.config['counters']}
        for track in tracks:
            identifier=track['id'];counter,kind=self.zone(track['box'])
            person=self.people.get(identifier)
            if person is None:
                person={'kind':'outside','counter':None,'since':now,'last':now,'queue_since':None,'service_since':None,
                        'candidate':None,'candidate_since':now}
                self.people[identifier]=person
                # Initial occupancy is immediate; later transitions need stability.
                person['kind']=kind;person['counter']=counter
                if kind=='queue':person['queue_since']=now;self.arrivals.append(now)
                if kind=='service':person['service_since']=now
            target=(counter,kind)
            if target!=(person['counter'],person['kind']):
                if person['candidate']!=target:
                    person['candidate']=target;person['candidate_since']=now
                if now-person['candidate_since']<.75:
                    counter,kind=person['counter'],person['kind']
            else:person['candidate']=None
            if kind!=person['kind'] or counter!=person['counter']:
                transition_at=person['candidate_since']
                if person['kind']=='service' and kind=='outside':
                    self.services.append(transition_at-person['service_since'])
                if kind=='queue':
                    if person['queue_since'] is None:person['queue_since']=transition_at;self.arrivals.append(transition_at)
                elif kind=='service':
                    if person['queue_since'] is not None:
                        self.waits.append(transition_at-person['queue_since']);person['queue_since']=None
                    person['service_since']=transition_at
                else:person['queue_since']=None;person['service_since']=None
                person.update(kind=kind,counter=counter,since=now)
            person['last']=now
            if kind in ('queue','service'):counts[counter]['waiting' if kind=='queue' else 'in_service']+=1
        # Lost identities are not treated as completed service or abandoned queues.
        self.people={key:p for key,p in self.people.items() if now-p['last']<2}
        while self.arrivals and self.arrivals[0]<now-60:self.arrivals.popleft()
        mean_service=sum(self.services)/len(self.services) if self.services else self.config['fallback_service_seconds']
        observed=max(1,min(60,now-self.started));rate=len(self.arrivals)/observed
        opened=sum(c['open'] for c in self.config['counters']);waiting=sum(c['waiting'] for c in counts.values())
        predicted=max(0,waiting+(rate-opened/mean_service)*120)
        required=math.ceil(rate*mean_service+waiting*mean_service/self.config['target_wait_seconds'])
        extra=min(len(counts)-opened,max(0,required-opened))
        ready=observed>=30
        congested=waiting>=self.config['congestion_queue_length'] or (ready and predicted>=self.config['congestion_queue_length'])
        rows=[]
        for c in self.config['counters']:
            row=dict(c,**counts[c['id']]);row['longest_wait_seconds']=max([now-p['queue_since'] for p in self.people.values() if p['counter']==c['id'] and p['kind']=='queue' and now-p['last']<1]+[0])
            rows.append(row)
        self.latest={'healthy':True,'counters':rows,'queue_length':waiting,'in_service':sum(c['in_service'] for c in counts.values()),
            'longest_wait_seconds':max([row['longest_wait_seconds'] for row in rows]+[0]),
            'outside_people':len(tracks)-waiting-sum(c['in_service'] for c in counts.values()),
            'average_wait_seconds':sum(self.waits)/len(self.waits) if self.waits else None,'wait_samples':len(self.waits),
            'average_service_seconds':sum(self.services)/len(self.services) if self.services else None,'service_samples':len(self.services),
            'forecast_queue_2min':round(predicted,1) if ready else None,'arrival_rate_per_minute':round(rate*60,1),
            'forecast_ready':ready,'service_basis':'Observed completed zone transitions' if self.services else 'Configured service-time assumption',
            'congested':congested,'additional_counters':extra if (ready or waiting) else 0,
            'recommendation':f'Open {extra} additional billing counter(s)' if extra and (ready or waiting) else ('All counters open; assist checkout staff' if congested and opened==len(counts) else 'Keep current staffing; monitor the queue'),
            'visible_people':len(tracks)}
        self.latest['service_calibrated']=any(c.get('service_enabled',True) for c in self.config['counters'])
        self.latest['alert_level']=alert_level(max([row['waiting'] for row in rows]+[0]))
        for row in rows:row['alert_level']=alert_level(row['waiting'])
        return self.latest
