"""Check selected OSRM route observations, without creating an ML environment."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EARTH_M = 6371008.8
THRESHOLDS = {'snap_review_m': 30.0, 'snap_large_m': 100.0,
              'endpoint_gap_m': 3.0, 'length_relative_tolerance': 0.02,
              'length_absolute_tolerance_m': 5.0}


def finite_nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be numeric')
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return float(value)


def coordinate(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError('Coordinate must be longitude, latitude')
    lon, lat = value[:2]
    if isinstance(lon, bool) or isinstance(lat, bool) or not all(
            isinstance(x, (int, float)) and math.isfinite(x) for x in (lon, lat)):
        raise ValueError('Invalid coordinate number')
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError('Invalid longitude/latitude order or range')
    return [float(lon), float(lat)]


def haversine(a, b):
    lon1, lat1 = coordinate(a)
    lon2, lat2 = coordinate(b)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2-p1, math.radians(lon2-lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return EARTH_M*2*math.asin(math.sqrt(min(1.0, max(0.0, h))))


def validate_response(payload, inputs, expected_ids):
    """Return geometry and measurable diagnostics, or a classified absent route.

    Review thresholds are screening rules, not calibrated confidence scores.
    A flagged observation is preserved rather than silently repaired.
    """
    if len(inputs) != 2 or len(expected_ids) != 2 or expected_ids[0] == expected_ids[1]:
        raise ValueError('Expected two distinct directed stop IDs')
    inputs = [coordinate(x) for x in inputs]
    code = payload.get('code')
    if code != 'Ok':
        state = {'NoRoute': 'no_route', 'NoSegment': 'no_segment'}.get(code, 'router_error')
        return dict(status=state, geometry=None, distance_m=None, duration_s=None,
                    quality_flags=[f'router_code:{code}'], router_code=code,
                    input_coordinates=inputs)
    routes = payload.get('routes')
    waypoints = payload.get('waypoints')
    if not isinstance(routes, list) or len(routes) != 1:
        raise ValueError('Expected exactly one route (alternatives=false)')
    if not isinstance(waypoints, list) or len(waypoints) != 2:
        raise ValueError('Expected two snapped waypoints')
    route = routes[0]
    geometry = route.get('geometry', {})
    if geometry.get('type') != 'LineString':
        raise ValueError('Expected full GeoJSON LineString')
    coords = geometry.get('coordinates', [])
    if len(coords) < 2:
        raise ValueError('Route needs at least two geometry vertices')
    coords = [coordinate(p) for p in coords]
    distance = finite_nonnegative(route.get('distance'), 'distance')
    duration = finite_nonnegative(route.get('duration'), 'duration')
    if route.get('weight') is not None:
        finite_nonnegative(route['weight'], 'route weight')
    snapped = [coordinate(w.get('location')) for w in waypoints]
    snap_errors = [haversine(x, y) for x, y in zip(inputs, snapped)]
    provider_snap = [finite_nonnegative(w.get('distance'), 'waypoint distance') for w in waypoints]
    gaps = [haversine(coords[0], snapped[0]), haversine(coords[-1], snapped[-1])]
    length = sum(haversine(a, b) for a, b in zip(coords, coords[1:]))
    difference = abs(length-distance)
    legs = route.get('legs', [])
    if len(legs) != 1:
        raise ValueError('Two waypoints must produce exactly one route leg')
    leg_distance = sum(finite_nonnegative(x.get('distance'), 'leg distance') for x in legs)
    leg_duration = sum(finite_nonnegative(x.get('duration'), 'leg duration') for x in legs)
    flags = []
    if max(snap_errors) > THRESHOLDS['snap_review_m']:
        flags.append('snap_distance_over_30m_review')
    if max(snap_errors) > THRESHOLDS['snap_large_m']:
        flags.append('snap_distance_over_100m_high_review')
    if max(gaps) > THRESHOLDS['endpoint_gap_m']:
        flags.append('geometry_endpoint_snap_gap_over_3m')
    if difference > max(THRESHOLDS['length_absolute_tolerance_m'],
                        distance*THRESHOLDS['length_relative_tolerance']):
        flags.append('geometry_length_vs_api_distance_review')
    if abs(leg_distance-distance) > 1.0 or abs(leg_duration-duration) > 1.0:
        flags.append('leg_sum_vs_route_metric_review')
    if max(abs(x-y) for x, y in zip(snap_errors, provider_snap)) > 3.0:
        flags.append('provider_vs_recomputed_snap_distance_review')
    if distance == 0:
        flags.append('distinct_stops_zero_router_distance')
    if haversine(inputs[0], inputs[1]) > 10 and haversine(snapped[0], snapped[1]) < 1:
        flags.append('distinct_input_stops_collapsed_to_same_snap')
    return dict(status='quality_flagged' if flags else 'ok',
                geometry=dict(type='LineString', coordinates=coords),
                distance_m=distance, duration_s=duration, input_coordinates=inputs,
                snapped_coordinates=snapped, snap_distance_m=snap_errors,
                provider_snap_distance_m=provider_snap, geometry_endpoint_gap_m=gaps,
                geometry_length_m=length, geometry_api_distance_difference_m=difference,
                geometry_api_distance_relative_difference=(difference/distance if distance else None),
                leg_distance_sum_m=leg_distance, leg_duration_sum_s=leg_duration,
                geometry_vertex_count=len(coords), quality_flags=flags,
                router_code=code, data_version=payload.get('data_version'),
                route_weight=route.get('weight'), route_weight_name=route.get('weight_name'),
                provenance_flags=([] if payload.get('data_version') else ['provider_data_version_not_supplied'])
                + (['routing_weight_not_identical_to_duration']
                   if isinstance(route.get('weight'), (int, float))
                   and abs(route['weight']-duration) > 1e-6 else []))


def validate_feature_collection(collection):
    if collection.get('type') != 'FeatureCollection':
        raise ValueError('Expected GeoJSON FeatureCollection')
    seen = set()
    for feature in collection.get('features', []):
        if feature.get('type') != 'Feature':
            raise ValueError('Expected GeoJSON Feature')
        props = feature['properties']
        direction = (props['from_station_id'], props['to_station_id'])
        if direction[0] == direction[1] or direction in seen:
            raise ValueError('Duplicate or identity directed edge')
        seen.add(direction)
        if feature['geometry']['type'] != 'LineString':
            raise ValueError('Non-line route geometry')
        for xy in feature['geometry']['coordinates']:
            coordinate(xy)
        finite_nonnegative(props['distance_m'], 'distance')
        finite_nonnegative(props['duration_s'], 'duration')
        if props['bus_feasibility_verified'] is not False:
            raise ValueError('Unsupported bus feasibility claim')
    return len(seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    folder = args.root/'data/routes/v1'
    collection = json.loads((folder/'routes.geojson').read_text(encoding='utf-8'))
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    count = validate_feature_collection(collection)
    if count != manifest['successful_geometry_count']:
        raise ValueError('Manifest/geometry count mismatch')
    with (args.root/'data/reference/seodaemun_bus_stops_official.csv').open(
            encoding='utf-8-sig', newline='') as handle:
        stops = {row['station_id']: row for row in csv.DictReader(handle)}
    for feature in collection['features']:
        prop = feature['properties']
        if prop['route_id'] != prop['from_station_id']+'__'+prop['to_station_id']:
            raise ValueError('Directed route ID mismatch')
        expected_inputs = [[float(stops[s]['longitude']), float(stops[s]['latitude'])]
                           for s in [prop['from_station_id'], prop['to_station_id']]]
        if prop['input_coordinates'] != expected_inputs:
            raise ValueError('Input coordinate/stop ID mismatch')
        raw = (args.root/prop['response_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != prop['response_sha256']:
            raise ValueError('Route response source hash mismatch')
        response = json.loads(raw)
        route = response['routes'][0]
        if (feature['geometry'] != route['geometry'] or prop['distance_m'] != route['distance']
                or prop['duration_s'] != route['duration']):
            raise ValueError('Geometry and metrics differ from preserved source response')
        if prop['snapped_coordinates'] != [w['location'] for w in response['waypoints']]:
            raise ValueError('Snapped waypoint/source mismatch')
    report = dict(schema_version='selected-routes-validation-1.0',
                  scope='selected directed route observations, not the full district matrix',
                  feature_count=count, requested_directed_count=manifest['selected_directed_count'],
                  thresholds=THRESHOLDS,
                  flagged_route_ids=[f['properties']['route_id'] for f in collection['features']
                                     if f['properties']['quality_flags']],
                  zero_distance_route_ids=[f['properties']['route_id'] for f in collection['features']
                                           if f['properties']['distance_m'] == 0],
                  max_recomputed_snap_distance_m=max((max(f['properties']['snap_distance_m'])
                                                     for f in collection['features']), default=None),
                  max_geometry_api_distance_difference_m=max((
                      f['properties']['geometry_api_distance_difference_m']
                      for f in collection['features']), default=None),
                  route_weight_names=sorted({f['properties'].get('route_weight_name')
                                            for f in collection['features']}),
                  routing_weight_differs_from_duration_route_ids=[
                      f['properties']['route_id'] for f in collection['features']
                      if 'routing_weight_not_identical_to_duration' in f['properties']['provenance_flags']],
                  directed_ids_and_official_coordinates_verified=True,
                  original_response_hashes_and_route_metrics_verified=True,
                  all_geometry_and_costs_from_same_response=True,
                  full_district_model_ready=False, bus_feasibility_verified=False,
                  minimum_duration_verified=False, shortest_distance_verified=False,
                  duration_kind='car_profile_estimate_not_observed_bus_peak_time',
                  limitations=['No actual bus access/turn/curb validation',
                               'Independent route pairs do not prove continuous multi-stop driving',
                               'Selected route geometry does not complete all464 costs'])
    path = args.root/'docs/evidence/selected_routes_validation.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
