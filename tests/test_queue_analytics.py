import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deployment'))
from queue_analytics import QueueAnalytics,validate
from queue_dashboard import DEFAULT
import copy
import pytest

def configured():
    config=copy.deepcopy(DEFAULT)
    config['mode']='zones'
    for index,counter in enumerate(config['counters']):
        counter['service_enabled']=True
        counter['queue']=[.05+index*.5,.1,.4,.75]
    return config

def person(identifier,y,x=.1):return {'id':identifier,'box':[x,y,.1,.1]}

def test_stationary_queue_occupancy_is_not_cumulative():
    queue=QueueAnalytics(configured())
    for now in range(20):
        state=queue.update([person('a',.2),person('b',.2,.6)],now)
        assert state['queue_length']==2
    assert len(queue.arrivals)==2
    assert queue.update([],21)['queue_length']==0

def test_wait_and_service_transitions():
    queue=QueueAnalytics(configured())
    queue.update([person('a',.2)],0)
    queue.update([person('a',.8)],10)
    state=queue.update([person('a',.8)],11)
    assert state['average_wait_seconds']==10 and state['queue_length']==0
    queue.update([person('a',.9,.46)],30)
    state=queue.update([person('a',.9,.46)],31)
    assert state['average_service_seconds']==20

def test_missing_person_not_claimed_completed_service():
    queue=QueueAnalytics(configured());queue.update([person('a',.8)],0)
    state=queue.update([],5)
    assert state['service_samples']==0 and state['average_service_seconds'] is None

def test_disconnect_pauses_timing():
    queue=QueueAnalytics(configured());queue.update([person('a',.2)],0)
    assert not queue.update([],5,False)['healthy']
    state=queue.update([person('a',.8)],10)
    assert state['wait_samples']==0

def test_forecast_and_additional_counter():
    config=configured();config['congestion_queue_length']=2
    queue=QueueAnalytics(config)
    queue.update([],0)
    state=queue.update([person(str(i),.2,x=.1+i*.03) for i in range(8)],35)
    assert state['congested'] and state['additional_counters']==1
    assert state['forecast_queue_2min']>state['queue_length']

def test_invalid_zone_rejected():
    config=copy.deepcopy(DEFAULT);config['counters'][0]['queue']=[.8,0,.5,1]
    with pytest.raises(ValueError):validate(config)

def test_waiting_timer_advances_while_person_stays():
    queue=QueueAnalytics(configured())
    queue.update([person('a',.2)],0)
    state=queue.update([person('a',.2)],20)
    assert state['queue_length']==1 and state['longest_wait_seconds']==20
    assert state['average_wait_seconds'] is None

def test_zone_jitter_does_not_create_timing_samples():
    queue=QueueAnalytics(configured())
    queue.update([person('a',.2)],0)
    for tick in range(1,20):
        state=queue.update([person('a',.8 if tick%2 else .2)],tick*.1)
        assert state['queue_length']==1
    assert state['wait_samples']==0 and state['service_samples']==0

def test_uncalibrated_default_counts_screenshot_waiting_spot():
    queue=QueueAnalytics(copy.deepcopy(DEFAULT))
    state=queue.update([person('a',.8)],0)
    assert state['queue_length']==1 and state['in_service']==0
    assert not state['service_calibrated']

def test_whole_frame_departure_and_average_wait():
    queue=QueueAnalytics(copy.deepcopy(DEFAULT))
    queue.update([person('a',.8)],0)
    state=queue.update([person('a',.8),person('b',.2,.6)],10)
    assert state['queue_length']==2 and state['longest_wait_seconds']==10
    queue.update([person('b',.2,.6)],11)
    state=queue.update([person('b',.2,.6)],12.1)
    assert state['queue_length']==1 and state['average_wait_seconds']==10
    assert state['total_wait_seconds']==pytest.approx(12.1)

def test_whole_frame_brief_id_change_keeps_wait():
    queue=QueueAnalytics(copy.deepcopy(DEFAULT));queue.update([person('a',.8)],0)
    queue.update([],1)
    state=queue.update([person('new-id',.8)],1.5)
    assert state['queue_length']==1 and state['longest_wait_seconds']==1.5 and state['wait_samples']==0

def test_missing_track_not_counted_during_timing_grace():
    queue=QueueAnalytics(copy.deepcopy(DEFAULT))
    queue.update([person('a',.8),person('b',.2,.6)],0)
    state=queue.update([person('b',.2,.6)],.5)
    assert state['queue_length']==1 and state['visible_people']==1
    assert state['wait_samples']==0
    assert [row['waiting'] for row in state['counters']]==[0,1]

def test_two_left_one_right_is_brown_not_red():
    queue=QueueAnalytics(copy.deepcopy(DEFAULT))
    state=queue.update([person('a',.8),person('b',.2,.3),person('c',.2,.6)],0)
    assert state['queue_length']==3
    assert [row['waiting'] for row in state['counters']]==[2,1]
    assert state['alert_level']=='brown'
