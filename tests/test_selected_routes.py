"""Independent geometry/cost meaning checks; no public network requests."""
import copy
import importlib.util
import math
import sys
from types import SimpleNamespace
from urllib.error import HTTPError
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
SPEC = importlib.util.spec_from_file_location('validate_route_geometry', SCRIPTS/'validate_route_geometry.py')
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
FETCH_SPEC = importlib.util.spec_from_file_location('fetch_selected_routes', SCRIPTS/'fetch_selected_routes.py')
FETCH = importlib.util.module_from_spec(FETCH_SPEC)
FETCH_SPEC.loader.exec_module(FETCH)


def response():
    # One degree along the equator: an independently known R*pi/180 distance.
    distance = 6371008.8*math.pi/180
    return {'code': 'Ok', 'routes': [{'distance': distance, 'duration': 120,
            'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [.5, 0], [1, 0]]},
            'legs': [{'distance': distance, 'duration': 120}]}],
            'waypoints': [{'location': [0, 0], 'distance': 0}, {'location': [1, 0], 'distance': 0}]}


def test_geodesic_equator_and_same_response_metrics():
    result = MOD.validate_response(response(), [[0, 0], [1, 0]], ['A', 'B'])
    assert result['status'] == 'ok'
    assert result['distance_m'] == pytest.approx(111195.0802, abs=.001)
    assert result['geometry_api_distance_difference_m'] < 1e-8
    assert result['duration_s'] == 120


def test_coordinate_order_is_not_silently_swapped():
    with pytest.raises(ValueError):
        MOD.coordinate([37.55, 126.95])  # Seoul latitude in longitude slot is invalid lat126.95.


@pytest.mark.parametrize('bad', [-1, float('nan'), float('inf'), True])
def test_invalid_router_cost_rejected(bad):
    body = response()
    body['routes'][0]['distance'] = bad
    with pytest.raises(ValueError):
        MOD.validate_response(body, [[0, 0], [1, 0]], ['A', 'B'])


def test_missing_route_is_not_zero_distance():
    result = MOD.validate_response({'code': 'NoRoute'}, [[0, 0], [1, 0]], ['A', 'B'])
    assert result['status'] == 'no_route'
    assert result['geometry'] is None
    assert result['distance_m'] is None and result['duration_s'] is None


def test_distinct_inputs_collapsed_to_zero_snap_are_preserved_and_flagged():
    body = response()
    body['routes'][0].update(distance=0, duration=0,
        geometry={'type': 'LineString', 'coordinates': [[0, 0], [0, 0]]},
        legs=[{'distance': 0, 'duration': 0}])
    body['waypoints'][1] = {'location': [0, 0], 'distance': 111195.0802}
    result = MOD.validate_response(body, [[0, 0], [1, 0]], ['A', 'B'])
    assert result['distance_m'] == 0
    assert 'distinct_stops_zero_router_distance' in result['quality_flags']
    assert 'distinct_input_stops_collapsed_to_same_snap' in result['quality_flags']


def test_large_geometry_cost_disagreement_is_not_repaired():
    body = response()
    body['routes'][0]['distance'] = 50
    body['routes'][0]['legs'][0]['distance'] = 50
    result = MOD.validate_response(body, [[0, 0], [1, 0]], ['A', 'B'])
    assert result['distance_m'] == 50
    assert 'geometry_length_vs_api_distance_review' in result['quality_flags']


def test_reverse_geometry_endpoint_disagreement_is_exposed():
    body = response()
    body['routes'][0]['geometry']['coordinates'].reverse()
    result = MOD.validate_response(body, [[0, 0], [1, 0]], ['A', 'B'])
    assert 'geometry_endpoint_snap_gap_over_3m' in result['quality_flags']


def test_identity_edge_is_not_a_valid_selected_movement():
    with pytest.raises(ValueError):
        MOD.validate_response(response(), [[0, 0], [1, 0]], ['A', 'A'])


def test_directional_feature_duplicates_rejected_but_reverse_is_distinct():
    feature = {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [1, 0]]},
               'properties': {'from_station_id': 'A', 'to_station_id': 'B',
                              'distance_m': 10, 'duration_s': 20, 'bus_feasibility_verified': False}}
    reverse = copy.deepcopy(feature)
    reverse['properties'].update(from_station_id='B', to_station_id='A')
    assert MOD.validate_feature_collection({'type': 'FeatureCollection', 'features': [feature, reverse]}) == 2
    with pytest.raises(ValueError):
        MOD.validate_feature_collection({'type': 'FeatureCollection', 'features': [feature, feature]})


def test_request_coordinates_direction_and_cache_key_are_explicit():
    stops = {'A': {'longitude': '126.95', 'latitude': '37.55'},
             'B': {'longitude': '126.96', 'latitude': '37.56'}}
    inputs, url, forward = FETCH.build_request(stops, 'A', 'B')
    _, _, reverse = FETCH.build_request(stops, 'B', 'A')
    assert inputs == [[126.95, 37.55], [126.96, 37.56]]
    assert '/126.9500000000,37.5500000000;126.9600000000,37.5600000000?' in url
    assert forward != reverse


def test_rate_limit_stops_and_is_not_circumvented_on_next_run(tmp_path, monkeypatch):
    stops = {s: {'station_name': s, 'longitude': 126.95, 'latitude': 37.55}
             for a, b, _ in FETCH.PAIRS for s in [a, b]}
    monkeypatch.setattr(FETCH, 'load_stops', lambda root: stops)
    calls = []
    def blocked(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 429, 'rate limit', {}, None)
    monkeypatch.setattr(FETCH, 'urlopen', blocked)
    args = SimpleNamespace(root=tmp_path, fetch=True, max_requests=24, interval=2)
    FETCH.acquire(args)
    assert len(calls) == 1
    FETCH.acquire(args)
    assert len(calls) == 1
    import json
    manifest = json.loads((tmp_path/'data/routes/v1/manifest.json').read_text(encoding='utf-8'))
    assert manifest['successful_geometry_count'] == 0
    assert manifest['status_counts'] == {'fetch_failed': 1, 'not_acquired': 23}


def test_offline_execution_makes_no_network_requests(tmp_path, monkeypatch):
    stops = {s: {'station_name': s, 'longitude': 126.95, 'latitude': 37.55}
             for a, b, _ in FETCH.PAIRS for s in [a, b]}
    monkeypatch.setattr(FETCH, 'load_stops', lambda root: stops)
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline build must not call a public service')
    monkeypatch.setattr(FETCH, 'urlopen', forbidden)
    result = FETCH.acquire(SimpleNamespace(root=tmp_path, fetch=False, max_requests=24, interval=2))
    assert result['features'] == []
