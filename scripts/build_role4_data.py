"""Build the role-4 reference bundle. No training or route optimization."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def finite_nonnegative(value, name):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'Invalid {name}: {value}')
    return value


def pooled_demand(records):
    """Missing any required record remains unknown; observed zero is retained."""
    if not records or any(not r['has_source_record'] for r in records):
        return None
    days = sum(r['days'] for r in records)
    if days <= 0:
        raise ValueError('Nonpositive denominator')
    return sum(finite_nonnegative(r['alight'], 'alight') for r in records) / days


def normalized(value, denominator):
    if value is None:
        return None
    if denominator < 0 or not math.isfinite(denominator):
        raise ValueError('Invalid normalizer')
    return value / denominator if denominator else 0.0


def haversine(lat1, lon1, lat2, lon2, radius=6371008.8):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2-p1, math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return radius * 2 * math.asin(math.sqrt(min(1, max(0, a))))


def hub_assignment(stop, anchors, radius, earth_radius):
    groups = {}
    for anchor in anchors:
        distance = haversine(stop['latitude'], stop['longitude'],
                             anchor['latitude'], anchor['longitude'], earth_radius)
        option = (distance, anchor['anchor_id'], anchor)
        old = groups.get(anchor['hub_id'])
        if old is None or option[:2] < old[:2]:
            groups[anchor['hub_id']] = option
    candidates = [dict(hub_id=h, hub_name=a['hub_name'], distance_m=d, anchor_id=aid)
                  for h, (d, aid, a) in groups.items() if d <= radius]
    candidates.sort(key=lambda x: (x['distance_m'], x['hub_id'], x['anchor_id']))
    first = candidates[0] if candidates else None
    return dict(station_id=stop['station_id'], hub_id=first['hub_id'] if first else None,
                hub_name=first['hub_name'] if first else None,
                hub_distance_m=first['distance_m'] if first else None,
                hub_anchor_id=first['anchor_id'] if first else None,
                hub_candidates=candidates)


def reward_arithmetic(demand_score, road_m, hub_id, visited_hubs, config):
    """Explain one transition's terms; not a policy/environment implementation."""
    if demand_score is None or road_m is None:
        return None
    finite_nonnegative(demand_score, 'demand score')
    finite_nonnegative(road_m, 'road distance')
    demand = config['demand_weight'] * demand_score
    bonus = config['hub_bonus'] if hub_id is not None and hub_id not in visited_hubs else 0.0
    cost = config['distance_cost_per_km'] * road_m / 1000
    return dict(demand=demand, hub_bonus=bonus, distance_cost=cost, reward=demand+bonus-cost)


def write_json(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                               indent=None if compact else 2,
                               separators=(',', ':') if compact else None)+'\n', encoding='utf-8')


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for item in rows:
            row = {}
            for field in fields:
                value = item.get(field)
                if isinstance(value, bool):
                    value = int(value)
                elif isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                row[field] = value
            writer.writerow(row)


def build(root=ROOT):
    config = json.loads((root/'data/role4_config.json').read_text(encoding='utf-8'))
    if config['decision_status'] != 'C2_design_passed':
        raise ValueError('C2-approved configuration is required')
    sources = {key: root/value for key, value in config['sources'].items()}
    raw_stops = read_csv(sources['stops'])
    ids = sorted(r['station_id'] for r in raw_stops)
    if len(ids) != len(set(ids)) or len(ids) != config['universe']['expected_stop_count']:
        raise ValueError('Invalid official stop universe')
    raw = {r['station_id']: r for r in raw_stops}
    for r in raw_stops:
        if not r['ars_id'].startswith('13'):
            raise ValueError('Unexpected ARS district')
    roads = json.loads(sources['roads'].read_text(encoding='utf-8'))
    if roads['ids'] != ids or len(roads['distances_m']) != len(ids):
        raise ValueError('Road and station IDs/order differ')
    covered = set(roads['source_covered_ids'])
    snaps = {r['station_id']: r for r in read_csv(sources['road_snap'])}
    anchors = read_csv(sources['hub_anchors'])
    for a in anchors:
        a['latitude'], a['longitude'] = float(a['latitude']), float(a['longitude'])
    if len({a['anchor_id'] for a in anchors}) != len(anchors):
        raise ValueError('Duplicate anchor ID')
    by_month = {}
    for r in read_csv(sources['ridership']):
        sid, month = r['station_id'], r['month']
        if sid not in raw or sid in by_month.setdefault(month, {}):
            raise ValueError('Unknown or duplicate stop-month')
        if r['has_source_record'] not in ('0', '1'):
            raise ValueError('Invalid observation flag')
        observed = r['has_source_record'] == '1'
        alight = int(r['alight_07_09']) if observed else None
        if observed and (int(r['alight_07'])+int(r['alight_08']) != alight):
            raise ValueError('Hourly alighting sum mismatch')
        if not observed and any(r[k] for k in ['alight_07', 'alight_08', 'alight_07_09']):
            raise ValueError('Unobserved demand must remain empty')
        if observed:
            finite_nonnegative(alight, 'monthly alight')
        by_month[month][sid] = dict(days=int(r['calendar_days']), split=r['split'],
                                  alight=alight, has_source_record=observed)
    expected_months = config['demand']['train_months']+config['demand']['validation_months']
    if sorted(by_month) != sorted(expected_months):
        raise ValueError('Month coverage mismatch')
    for month, records in by_month.items():
        if set(records) != set(ids) or len({(r['days'], r['split']) for r in records.values()}) != 1:
            raise ValueError('Month IDs/days/split are inconsistent')
        expected_split = 'train' if month in config['demand']['train_months'] else 'validation'
        if any(r['split'] != expected_split or r['days'] <= 0 for r in records.values()):
            raise ValueError('Invalid split/days')
    train_days = sum(by_month[m][ids[0]]['days'] for m in config['demand']['train_months'])
    if train_days != config['demand']['expected_train_days']:
        raise ValueError('Training denominator mismatch')
    demand = {sid: pooled_demand([by_month[m][sid] for m in config['demand']['train_months']])
              for sid in ids}
    normalizer = max(v for v in demand.values() if v is not None)
    if not math.isclose(normalizer, config['demand']['expected_normalizer_daily_alight'], abs_tol=1e-10):
        raise ValueError('Unexpected global training normalizer')
    stops = []
    for sid in ids:
        r = raw[sid]
        lat, lon = float(r['latitude']), float(r['longitude'])
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Invalid WGS84 coordinate')
        excluded = r['stop_type_ko'] in config['stop_policy']['exclude_types']
        quality = snaps[sid]['distance_quality']
        flags = []
        if demand[sid] is None:
            flags.append('missing_train_demand')
        if sid not in covered:
            flags.append('missing_road_source')
        if excluded:
            flags.append('central_lane_excluded_by_assumption')
        if quality in ['check', 'unverified']:
            flags.append('road_snap_'+quality)
        stops.append(dict(station_id=sid, ars_id=r['ars_id'], station_name=r['station_name'],
                          latitude=lat, longitude=lon, stop_type_ko=r['stop_type_ko'],
                          in_baseline_282=r['in_baseline_282']=='1', in_original_808=r['in_original_808']=='1',
                          complete_train=demand[sid] is not None, demand_daily_train=demand[sid],
                          demand_score_train=normalized(demand[sid], normalizer),
                          road_source_covered=sid in covered, distance_quality=quality,
                          excluded_by_stop_policy=excluded, candidate_eligible_by_policy=not excluded,
                          diagnostic_subset_eligible=not excluded and demand[sid] is not None and sid in covered,
                          quality_flags=flags))
    radii = sorted(set(config['hubs']['sensitivity_radii_m']+[config['hubs']['radius_m']]))
    assignments, sensitivity = {}, []
    group_ids = {a['hub_id'] for a in anchors}
    for radius in radii:
        key = str(int(radius)) if float(radius).is_integer() else str(radius)
        mappings = [hub_assignment(s, anchors, radius, config['hubs']['earth_radius_m']) for s in stops]
        assignments[key] = mappings
        counts = Counter(m['hub_id'] for m in mappings if m['hub_id'] is not None)
        candidate_counts = Counter(c['hub_id'] for m in mappings for c in m['hub_candidates'])
        sensitivity.append(dict(radius_m=radius, mapped_stops=sum(counts.values()),
                                assigned_group_count=len(counts), assigned_group_counts=dict(sorted(counts.items())),
                                multi_group_candidates=sum(len(m['hub_candidates'])>1 for m in mappings),
                                candidate_group_counts=dict(sorted(candidate_counts.items())),
                                unassigned_group_ids=sorted(group_ids-set(counts)),
                                no_candidate_group_ids=sorted(group_ids-set(candidate_counts))))
    default_key = str(int(config['hubs']['radius_m']))
    for stop, mapping in zip(stops, assignments[default_key]):
        stop.update({k: v for k, v in mapping.items() if k != 'station_id'})
    known, unknown, zero_pairs = 0, 0, []
    for i, row in enumerate(roads['distances_m']):
        if len(row) != len(ids):
            raise ValueError('Nonsquare road matrix')
        for j, value in enumerate(row):
            if i == j:
                if value != 0:
                    raise ValueError('Nonzero diagonal')
            elif value is None:
                unknown += 1
            else:
                finite_nonnegative(value, 'road distance')
                known += 1
                if value == 0:
                    zero_pairs.append(dict(from_station_id=ids[i], to_station_id=ids[j]))
    flagged_zero_ids = {p[k] for p in zero_pairs for k in ['from_station_id', 'to_station_id']}
    for stop in stops:
        if stop['station_id'] in flagged_zero_ids:
            stop['quality_flags'].append('incident_zero_distance_source_pair')
    months = {}
    monthly_rows = []
    for month in sorted(by_month):
        records = by_month[month]
        first = records[ids[0]]
        daily = [r['alight']/r['days'] if r['has_source_record'] else None for r in (records[i] for i in ids)]
        months[month] = dict(days=first['days'], split=first['split'],
                             alight=[records[i]['alight'] for i in ids],
                             has_source_record=[records[i]['has_source_record'] for i in ids],
                             daily=daily, score=[normalized(v, normalizer) for v in daily])
        for idx, sid in enumerate(ids):
            monthly_rows.append(dict(month=month, station_id=sid, days=first['days'], split=first['split'],
                                     alight_07_09=records[sid]['alight'], has_source_record=records[sid]['has_source_record'],
                                     daily_alight=daily[idx], demand_score=months[month]['score'][idx]))
    summary = dict(stop_count=len(ids), complete_train_stop_count=sum(s['complete_train'] for s in stops),
                   missing_train_stop_count=sum(not s['complete_train'] for s in stops),
                   observed_zero_train_stop_count=sum(s['demand_daily_train']==0 for s in stops),
                   train_calendar_days=train_days, normalizer_daily_alight=normalizer,
                   road_source_covered_stop_count=len(covered), available_directed_pairs=known,
                   missing_directed_pairs=unknown, central_lane_stop_count=sum(s['excluded_by_stop_policy'] for s in stops),
                   policy_eligible_stop_count=sum(s['candidate_eligible_by_policy'] for s in stops),
                   complete_train_policy_eligible_stop_count=sum(s['complete_train'] and not s['excluded_by_stop_policy'] for s in stops),
                   diagnostic_subset_stop_count=sum(s['diagnostic_subset_eligible'] for s in stops),
                   baseline_stop_count=sum(s['in_baseline_282'] for s in stops), anchor_count=len(anchors),
                   hub_group_count=len(group_ids), default_hub_mapped_stop_count=sum(s['hub_id'] is not None for s in stops))
    expected = config['readiness']
    for key, want in [('complete_train_stop_count', expected['expected_complete_train_stop_count']),
                      ('missing_train_stop_count', expected['expected_missing_train_stop_count']),
                      ('road_source_covered_stop_count', expected['expected_road_source_covered_stop_count']),
                      ('missing_directed_pairs', expected['known_missing_distance_pairs']),
                      ('diagnostic_subset_stop_count', expected['expected_diagnostic_subset_stop_count'])]:
        if summary[key] != want:
            raise ValueError(f'Unexpected {key}: {summary[key]} != {want}')
    ready = dict(reference_complete=True, reference_map_ready=True, demand_reference_ready=True,
                 demand_full=summary['missing_train_stop_count']==0,
                 road_full=unknown==0, operational_verified=False, bus_drivability_verified=False,
                 full_district_model_ready=summary['missing_train_stop_count']==0 and unknown==0,
                 existing_train_py_compatible_without_adaptation=False,
                 interpretation='Reference and partial input handoff only; not verified service or complete district model input')
    hashes = {key: dict(path=path.relative_to(root).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
              for key, path in sources.items()}
    bundle = dict(schema_version='role4-bundle-1.0', ids=ids, config=config, stops=stops,
                  months=months, hubs=anchors, distances_m=roads['distances_m'], summary=summary,
                  readiness=ready, hub_assignments_by_radius=assignments, hub_sensitivity=sensitivity,
                  zero_distance_pairs=zero_pairs, provenance=hashes)
    out = root/'data/processed'
    write_json(out/'role4_bundle.json', bundle, compact=True)
    fields = ['station_id', 'ars_id', 'station_name', 'latitude', 'longitude', 'stop_type_ko',
              'in_baseline_282', 'in_original_808', 'complete_train', 'demand_daily_train', 'demand_score_train',
              'hub_id', 'hub_name', 'hub_distance_m', 'hub_anchor_id', 'road_source_covered', 'distance_quality',
              'excluded_by_stop_policy', 'candidate_eligible_by_policy', 'diagnostic_subset_eligible', 'quality_flags']
    write_csv(out/'stop_master.csv', stops, fields)
    write_csv(out/'ridership.csv', monthly_rows,
              ['month', 'station_id', 'days', 'split', 'has_source_record', 'alight_07_09', 'daily_alight', 'demand_score'])
    mapping_rows = [dict(radius_m=k, **m) for k, rows in assignments.items() for m in rows]
    write_csv(out/'hub_mapping.csv', mapping_rows,
              ['radius_m', 'station_id', 'hub_id', 'hub_name', 'hub_distance_m', 'hub_anchor_id', 'hub_candidates'])
    write_json(out/'hub_sensitivity.json', sensitivity)
    diagnostic_indices = [i for i, s in enumerate(stops) if s['diagnostic_subset_eligible']]
    write_json(out/'diagnostic_259.json', dict(schema_version='role4-diagnostic-1.0',
               purpose='observed noncentral source subset only; not complete district experiment population',
               full_district=False, ids=[ids[i] for i in diagnostic_indices],
               stops=[stops[i] for i in diagnostic_indices],
               distances_m=[[roads['distances_m'][i][j] for j in diagnostic_indices] for i in diagnostic_indices]), compact=True)
    validation = dict(summary=summary, readiness=ready, hub_sensitivity=sensitivity,
                      zero_distance_pairs=zero_pairs, source_hashes=hashes,
                      output_sha256={name: hashlib.sha256((out/name).read_bytes()).hexdigest()
                                     for name in ['role4_bundle.json', 'stop_master.csv', 'ridership.csv',
                                                  'hub_mapping.csv', 'hub_sensitivity.json', 'diagnostic_259.json']},
                      checks=['unique official IDs and ARS13', 'monthly ID coverage/split/day consistency',
                              'observed zero distinct from missing', 'hourly sum equals monthly sum',
                              'pooled123 and fixed global max', 'road ID/order/value validation',
                              'deterministic single nearest hub mapping', 'expected source counts independently computed'])
    write_json(root/'docs/evidence/role4_build_validation.json', validation)
    return bundle


if __name__ == '__main__':
    result = build()
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
