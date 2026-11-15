"""Acquire a bounded sample of real road paths, with explicit offline rebuilding.

No stop-order optimization, model training, paid service, or all-pairs harvesting.
The default execution never contacts a server. Use --fetch for at most 24 cached
directed observations, serially and >=2 seconds between requests. A 429 stops
the acquisition rather than switching identities or circumventing the limit.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from validate_route_geometry import validate_response, validate_feature_collection, THRESHOLDS

ROOT = Path(__file__).resolve().parents[1]
API_DOC = 'https://project-osrm.org/docs/v5.24.0/api/'
POLICY = 'https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server'
ENDPOINT = 'https://router.project-osrm.org'
PARAMETERS = dict(alternatives='false', geometries='geojson', overview='full',
                  steps='true', annotations='distance,duration',
                  generate_hints='false', approaches='curb;curb')
PAIRS = [
    ('112000031', '112900230', 'Yonsei front to Sinchon subway'),
    ('112900188', '112000057', 'Yonsei hospital front to Ewha subway'),
    ('112000057', '112000054', 'Ewha to Chungjeongno station access'),
    ('112900054', '112000167', 'Seodaemun to Dongnimmun corridor'),
    ('112000167', '112000398', 'Dongnimmun to Muakjae northern extension'),
    ('112000398', '112000413', 'Muakjae to Hongje northern extension'),
    ('112000413', '112000424', 'Hongje different exit-side short movement'),
    ('112000424', '112000039', 'Hongje to northern residential area'),
    ('112000039', '112900116', 'Northern residential and internal-road screening'),
    ('112900003', '112900157', 'Original distinct-stop zero-distance snap pair'),
    ('112900031', '112900052', 'Hilly residential/apartment corridor'),
    ('112000073', '112000125', 'District office close directional access'),
]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


def load_stops(root):
    with (root/'data/reference/seodaemun_bus_stops_official.csv').open(
            encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    stops = {row['station_id']: row for row in rows}
    if len(stops) != 464 or len(stops) != len(rows):
        raise ValueError('Official reference needs 464 unique stops')
    return stops


def build_request(stops, a, b):
    if a == b or a not in stops or b not in stops:
        raise ValueError('Unknown or identical stop pair')
    inputs = [[float(stops[s]['longitude']), float(stops[s]['latitude'])] for s in (a, b)]
    coordinates = ';'.join(','.join(f'{v:.10f}' for v in xy) for xy in inputs)
    url = f'{ENDPOINT}/route/v1/driving/{coordinates}?{urlencode(PARAMETERS)}'
    signature = dict(endpoint=ENDPOINT, service='route/v1/driving', inputs=inputs,
                     parameters=PARAMETERS, ids=[a, b])
    key = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return inputs, url, key


def selected_edges():
    return [(a, b, label) for x, y, label in PAIRS for a, b in [(x, y), (y, x)]]


def acquire(args):
    root, folder = args.root, args.root/'data/routes/v1'
    stops = load_stops(root)
    (folder/'responses').mkdir(parents=True, exist_ok=True)
    selections = []
    new_requests, last_request = 0, None
    previous_manifest = folder/'manifest.json'
    stop_reason = (json.loads(previous_manifest.read_text(encoding='utf-8')).get('acquisition_stop_reason')
                   if previous_manifest.exists() else None)
    for a, b, label in selected_edges():
        route_id = f'{a}__{b}'
        inputs, url, key = build_request(stops, a, b)
        meta_path = folder/'responses'/f'{route_id}.meta.json'
        response_path = folder/'responses'/f'{route_id}.response.json'
        metadata = None
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding='utf-8'))
            if metadata['cache_key'] != key:
                raise ValueError(f'Request changed; create a separate version: {route_id}')
        elif args.fetch and stop_reason is None and new_requests < args.max_requests:
            if last_request is not None:
                delay = args.interval - (time.monotonic() - last_request)
                if delay > 0:
                    time.sleep(delay)
            metadata = dict(route_id=route_id, cache_key=key, request_url=url,
                            retrieved_at=datetime.now(timezone.utc).isoformat(),
                            from_station_id=a, to_station_id=b,
                            input_coordinates=inputs, parameters=PARAMETERS,
                            profile='driving/car', routing_objective='car_profile_routing_weight_not_distance_minimum',
                            minimum_duration_verified=False, shortest_distance_verified=False,
                            endpoint=ENDPOINT, source_policy_url=POLICY)
            metadata['fetch_status'] = 'request_started'
            write_json(meta_path, metadata)
            last_request = time.monotonic()
            new_requests += 1
            try:
                request = Request(url, headers={
                    'User-Agent': 'YonseiRole4Research/1.0 (https://github.com/hkson0826-oss/2026-2-yonsei_RL)',
                    'Accept': 'application/json'})
                with urlopen(request, timeout=25) as response:
                    raw = response.read()
                    metadata['http_status'] = response.status
                json.loads(raw)
                response_path.write_bytes(raw)
                metadata.update(fetch_status='response_saved',
                                response_sha256=hashlib.sha256(raw).hexdigest(),
                                response_bytes=len(raw))
                print(f'{route_id}: response saved ({len(raw)} bytes)', flush=True)
            except HTTPError as error:
                metadata.update(fetch_status='fetch_failed', http_status=error.code,
                                error=f'HTTP {error.code}')
                # Do not bypass access or rate limits; no repeated fallback requests.
                if error.code in [401, 403, 406, 429] or error.code >= 500:
                    stop_reason = f'public_endpoint_http_{error.code}_acquisition_stopped'
                print(f'{route_id}: HTTP {error.code}', flush=True)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                metadata.update(fetch_status='fetch_failed', error=f'{type(error).__name__}: {error}')
                stop_reason = 'endpoint_unavailable_acquisition_stopped'
                print(f'{route_id}: acquisition failed ({type(error).__name__})', flush=True)
            write_json(meta_path, metadata)
        item = dict(route_id=route_id, from_station_id=a, to_station_id=b,
                    from_station_name=stops[a]['station_name'],
                    to_station_name=stops[b]['station_name'], selection_reason=label,
                    input_coordinates=inputs, cache_key=key)
        item['meta_path'] = meta_path.relative_to(root).as_posix() if meta_path.exists() else None
        item['response_path'] = response_path.relative_to(root).as_posix() if response_path.exists() else None
        selections.append(item)
    write_json(folder/'selection.json', dict(
        scope='12 predetermined diagnostic pairs in both directions; no route order optimization',
        official_reference_count=len(stops), directed_pair_count=len(selections),
        max_network_requests_per_acquisition=24, pairs=selections))
    return rebuild(root, selections, new_requests, stop_reason)


def rebuild(root, selections, new_requests=0, stop_reason=None):
    folder = root/'data/routes/v1'
    features, metrics = [], []
    total_cached = 0
    for item in selections:
        meta = json.loads((root/item['meta_path']).read_text(encoding='utf-8')) if item['meta_path'] else {}
        result = dict(status='not_acquired', geometry=None, distance_m=None,
                      duration_s=None, quality_flags=['not_acquired'])
        if item['meta_path']:
            total_cached += 1
        if item['response_path']:
            raw = (root/item['response_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta.get('response_sha256'):
                raise ValueError(f'Cached response hash mismatch: {item["route_id"]}')
            try:
                result = validate_response(json.loads(raw), item['input_coordinates'],
                                           [item['from_station_id'], item['to_station_id']])
            except ValueError as error:
                result = dict(status='invalid_response', geometry=None, distance_m=None,
                              duration_s=None, quality_flags=[str(error)])
        elif meta:
            result.update(status='fetch_failed', quality_flags=[meta.get('error', 'fetch_failed')])
        props = dict(item, **{k: v for k, v in result.items() if k not in ['geometry', 'input_coordinates']},
                     source=ENDPOINT, profile='driving/car', routing_objective='car_profile_routing_weight_not_distance_minimum',
                     retrieved_at=meta.get('retrieved_at'), request_parameters=PARAMETERS,
                     response_sha256=meta.get('response_sha256'),
                     duration_kind='car_profile_estimate_not_observed_07_09_bus_time',
                     minimum_duration_verified=False, shortest_distance_verified=False,
                     bus_feasibility_verified=False, selected_route_cache_only=True,
                     legacy_distance_replaced=False)
        metrics.append(props)
        if result['geometry'] is not None:
            features.append(dict(type='Feature', geometry=result['geometry'], properties=props))
    collection = dict(type='FeatureCollection', name='Selected OSRM car-profile road routes',
                      features=features,
                      attribution='© OpenStreetMap contributors; routing by OSRM demo/FOSSGIS',
                      source_documentation=API_DOC)
    validate_feature_collection(collection)
    write_json(folder/'routes.geojson', collection)
    fields = ['route_id', 'from_station_id', 'to_station_id', 'from_station_name', 'to_station_name',
              'selection_reason', 'status', 'distance_m', 'duration_s', 'routing_objective',
              'profile', 'geometry_vertex_count', 'snap_distance_m', 'geometry_endpoint_gap_m',
              'geometry_length_m', 'geometry_api_distance_difference_m', 'quality_flags',
              'route_weight', 'route_weight_name', 'provenance_flags', 'data_version', 'retrieved_at', 'source', 'response_sha256', 'duration_kind',
              'minimum_duration_verified', 'shortest_distance_verified', 'bus_feasibility_verified']
    with (folder/'route_metrics.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in metrics:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})
    manifest = dict(schema_version='selected-road-routes-1.0', endpoint=ENDPOINT,
                    source_documentation=API_DOC, source_policy=POLICY,
                    attribution='© OpenStreetMap contributors; OSRM/FOSSGIS demo routing',
                    routing_objective='car_profile_routing_weight_not_distance_minimum', profile='driving/car',
                    source_data_version_policy='provided response data_version or null if absent',
                    request_parameters=PARAMETERS, selected_directed_count=len(selections),
                    cached_attempt_count=total_cached, successful_geometry_count=len(features),
                    status_counts=dict(Counter(row['status'] for row in metrics)),
                    quality_thresholds=THRESHOLDS, interval_minimum_seconds=2,
                    scope='selected representative road observations, not complete district costs',
                    full_district_model_ready=False, bus_feasibility_verified=False,
                    minimum_duration_verified=False, shortest_distance_verified=False,
                    online_requests_performed_by_offline_build=0,
                    geometry_cache_hashes={f['properties']['route_id']: f['properties']['response_sha256']
                                           for f in features})
    # Acquisition attempts are factual provenance and remain stable on offline rebuild.
    manifest_path = folder/'manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest['total_network_requests_recorded'] = total_cached
    manifest['acquisition_stop_reason'] = stop_reason or previous.get('acquisition_stop_reason')
    write_json(manifest_path, manifest)
    print(json.dumps({k: manifest[k] for k in ['selected_directed_count', 'successful_geometry_count',
          'status_counts', 'acquisition_stop_reason']}, ensure_ascii=False, indent=2), flush=True)
    return collection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fetch', action='store_true', help='Allow bounded public network acquisition')
    mode.add_argument('--offline', action='store_true', help='Rebuild using cached observations only (default)')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--max-requests', type=int, default=24)
    parser.add_argument('--interval', type=float, default=2.0)
    args = parser.parse_args()
    if not 0 <= args.max_requests <= 24 or not math.isfinite(args.interval) or args.interval < 2:
        parser.error('At most 24 requests; interval must be at least two seconds')
    acquire(args)


if __name__ == '__main__':
    main()
