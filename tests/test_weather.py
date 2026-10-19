import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from weather_service import location_query, parse_weather, read_location

PAYLOAD = {
    'current_condition': [{
        'temp_C': '24', 'FeelsLikeC': '24', 'humidity': '58',
        'weatherCode': '122', 'weatherDesc': [{'value': 'Overcast '}],
        'windspeedKmph': '12', 'winddir16Point': 'SW',
        'observation_time': '12:24 PM',
    }],
    'weather': [{
        'maxtempC': '27', 'mintempC': '21',
        'astronomy': [{'sunrise': '05:51 AM', 'sunset': '05:01 PM'}],
    }],
    'nearest_area': [{
        'areaName': [{'value': 'Takehiracho'}],
        'region': [{'value': 'Tokyo'}],
        'country': [{'value': 'Japan'}],
    }],
}


class WeatherTests(unittest.TestCase):
    def test_parse_official_shape(self):
        data = parse_weather(PAYLOAD, '')
        self.assertEqual(data['state'], 'ok')
        self.assertEqual(data['location'], 'Tokyo')
        self.assertEqual(data['temperature'], 24)
        self.assertEqual(data['condition'], '阴')
        self.assertEqual(data['high'], 27)
        self.assertEqual(data['low'], 21)
        self.assertEqual(data['windDirZh'], '西南风')
        self.assertEqual(ord(data['icon']), 0xE33D)

    def test_configured_name_wins_over_detected_area(self):
        data = parse_weather(PAYLOAD, '上海')
        self.assertEqual(data['location'], '上海')

    def test_location_file_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / '.local/state/omarchy/settings'
            state.mkdir(parents=True)
            (state / 'weather.json').write_text(json.dumps({
                'name': 'Shanghai', 'latitude': 31.23, 'longitude': 121.47,
            }))
            location = read_location(tmp)
            self.assertEqual(location['name'], 'Shanghai')
            self.assertEqual(location_query(location), '31.23,121.47')

    def test_missing_location_uses_auto_detect(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = read_location(tmp)
            self.assertEqual(location['name'], '')
            self.assertEqual(location_query(location), '')


if __name__ == '__main__':
    unittest.main()
