import sqlite3
import pytest
from retail_counter.footfall import hourly_footfall


def test_local_hour_bins_exclude_other_cameras_and_exits(tmp_path):
    path=tmp_path/'events.sqlite3'
    connection=sqlite3.connect(path)
    connection.execute('CREATE TABLE crossing_events(timestamp_utc,local_date,camera_id,direction)')
    connection.executemany('INSERT INTO crossing_events VALUES (?,?,?,?)',[
        ('2026-09-25T18:45:00+00:00','2026-09-26','door','ENTRY'),
        ('2026-09-26T07:00:00+00:00','2026-09-26','door','ENTRY'),
        ('2026-09-26T07:20:00+00:00','2026-09-26','door','ENTRY'),
        ('2026-09-26T07:20:00+00:00','2026-09-26','old','ENTRY'),
        ('2026-09-26T07:20:00+00:00','2026-09-26','door','EXIT')])
    connection.commit();connection.close()
    data=hourly_footfall(path,'2026-09-26','door')
    assert data['total_arrivals']==3
    assert data['hourly'][0]['arrivals']==1
    assert data['hourly'][12]['arrivals']==2
    assert data['peak_hours']==[12]
    assert len(data['hourly'])==24
    assert hourly_footfall(path,'2026-09-27','door')['peak_hours']==[]
    with pytest.raises(ValueError):hourly_footfall(path,'bad','door')
