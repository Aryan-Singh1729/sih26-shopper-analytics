import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deployment'))
from visual_arrivals import VisualArrivals


def track(x=20):
    return {'box': (x, 10, 40, 100), 'score': .9}


class VisualArrivalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'events.sqlite3'
        self.counter = VisualArrivals(self.path)

    def tearDown(self):
        self.counter.connection.close()
        self.directory.cleanup()

    def test_first_box_counts_immediately_and_hold_does_not_repeat(self):
        self.assertEqual(len(self.counter.update([track()], 0)), 1)
        for tick in range(1, 100):
            self.assertEqual(self.counter.update([track(20 + tick / 2)], tick / 10), [])

    def test_short_dropout_does_not_repeat(self):
        self.counter.update([track()], 0)
        self.counter.update([], .2)
        self.assertEqual(self.counter.update([track()], .8), [])

    def test_departure_then_return_counts_again(self):
        self.counter.update([track()], 0)
        self.counter.update([], 1.1)
        self.assertEqual(len(self.counter.update([track()], 1.2)), 1)

    def test_group_and_additional_person(self):
        self.assertEqual(len(self.counter.update([track(), track(200)], 0)), 2)
        self.assertEqual(len(self.counter.update([track(200), track(), track(400)], .1)), 1)
        self.assertEqual(self.counter.update([track(400), track(), track(200)], .2), [])

    def test_matching_is_one_to_one(self):
        self.counter.update([track()], 0)
        self.assertEqual(len(self.counter.update([track(), track(45)], .1)), 1)

    def test_persistent_hourly_aggregate(self):
        moment = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
        self.counter.update([track(), track(200)], 0, moment)
        self.counter.connection.close()
        self.counter = VisualArrivals(self.path)
        history = {'date': '2026-09-26', 'hourly': [{'hour': h, 'arrivals': 0} for h in range(24)], 'last_arrival': None}
        merged = self.counter.merge(history)
        self.assertEqual(merged['total_arrivals'], 2)
        self.assertEqual(merged['hourly'][15]['arrivals'], 2)
        self.assertEqual(merged['peak_hours'], [15])
        self.assertEqual(history['hourly'][15]['arrivals'], 0)

    def test_new_local_day(self):
        self.counter.update([track()], 0, datetime(2026, 9, 26, 19, 0, tzinfo=timezone.utc))
        day = self.counter.connection.execute('SELECT local_date FROM visual_arrivals').fetchone()[0]
        self.assertEqual(day, '2026-09-27')
