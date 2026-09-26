from retail_counter.track_arrivals import TrackArrivalCounter
from retail_counter.types import TrackView

def track(identifier):
    return TrackView(identifier, (10,10,100,200), .9, True, 1, 0)

def test_group_arrivals_and_newcomer_count_each_person_once():
    counter=TrackArrivalCounter({'camera_id':'door'},'Asia/Calcutta')
    assert len(counter.update([track(1),track(2)],100))==2
    assert counter.update([track(1),track(2)],101)==[]
    assert len(counter.update([track(1),track(2),track(3)],102))==1
    assert counter.update([],105,True)==[]
    assert counter.update([track(1),track(2),track(3)],106)==[]
    counter.update([],110,False);counter.update([],114,False)
    assert len(counter.update([track(1)],115))==1
