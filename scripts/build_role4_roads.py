"""Build an honest, partially observed road-cost reference; never train a model.

The original 808-stop OSM costs are the only numeric distance source. New
district stops are retained in the index with null off-diagonal distances.
"""
import argparse
import csv
import hashlib
import json
import math
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def archive_rows(archives):
    for path in archives:
        with ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.lower().endswith('.csv'):
                    continue
                with archive.open(name) as handle:
                    yield from csv.DictReader(TextIOWrapper(handle, encoding='utf-8-sig', newline=''))


def build_matrix(ids, rows):
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate inventory stop ID')
    index = {sid: i for i, sid in enumerate(ids)}
    matrix = [[0.0 if i == j else None for j in range(len(ids))] for i in range(len(ids))]
    seen = set()
    zero_pairs = []
    source_ids = set()
    for row in rows:
        origin, destination = row['from_station_id'], row['to_station_id']
        if origin not in index or destination not in index:
            continue
        key = (origin, destination)
        value = float(row['road_m'])
        if key in seen or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid or duplicate source cost: {key}')
        if origin == destination and value != 0:
            raise ValueError('Nonzero source diagonal')
        seen.add(key)
        source_ids.update(key)
        matrix[index[origin]][index[destination]] = value
        if origin != destination and value == 0:
            zero_pairs.append(dict(from_station_id=origin, to_station_id=destination,
                                   road_m=value, straight_m=row.get('straight_m')))
    return matrix, source_ids, zero_pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=ROOT/'data/reference/seodaemun_bus_stops_official.csv')
    parser.add_argument('--source', type=Path, default=ROOT/'docs/notion/01_data_preprocessing')
    parser.add_argument('--out', type=Path, default=ROOT/'data/processed')
    args = parser.parse_args()
    stops = read_csv(args.inventory)
    ids = [row['station_id'] for row in stops]
    archives = sorted(args.source.glob('11_road_distance_part*.zip'))
    if not archives:
        raise ValueError('No original road-distance archives')
    matrix, source_ids, zero_pairs = build_matrix(ids, archive_rows(archives))
    args.out.mkdir(parents=True, exist_ok=True)
    n = len(ids)
    available = sum(matrix[i][j] is not None for i in range(n) for j in range(n) if i != j)
    expected = n*(n-1)
    complete = available == expected
    payload = dict(
        schema_version='role4-road-reference-1', ids=ids, distances_m=matrix,
        source='original team 808-stop directional OSM matrix only',
        units='metres', scope='official ARS district13 stop inventory',
        all_pairs_complete=complete, available_off_diagonal_pairs=available,
        missing_off_diagonal_pairs=expected-available,
        missing_policy='null means unknown, not zero and not an impassable road',
        diagonal_policy='zero identity cost for every indexed stop; does not imply road observation',
        source_covered_ids=sorted(source_ids),
        limitations=['OSM-derived costs are not verified bus-feasible routes',
                     'turn restrictions and legal U-turns not verified',
                     'apartment internal roads may be missing',
                     'partial matrix must not be passed to the existing numeric-only model loader'],
    )
    (args.out/'road_distances_full.json').write_text(
        json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    snap_source = {r['station_id']: r for r in read_csv(args.source/'12_station_osm_snap.csv')}
    fields = ['station_id','has_original_road_source','has_original_snap','u','v','key',
              'edge_len','offset_m','snap_dist_m','snap_side_ok','snap_method',
              'road_name','highway','distance_quality']
    with (args.out/'road_snap.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for sid in ids:
            original=snap_source.get(sid,{})
            row={k:original.get(k,'') for k in fields}
            row.update(station_id=sid,has_original_road_source=int(sid in source_ids),
                       has_original_snap=int(bool(original)))
            if not original:
                row['distance_quality']='missing_source'
            writer.writerow(row)
    attempt=ROOT/'data/reference/role4_roads_source.json'
    acquisition=json.loads(attempt.read_text(encoding='utf-8')) if attempt.exists() else {}
    audit=dict(
        snapshot_date_kst='2026-11-15',method='source-only district reindex, no distance imputation',
        official_stop_count=n,source_covered_stop_count=len(source_ids),
        available_directed_pairs=available,expected_directed_pairs=expected,
        missing_directed_pairs=expected-available,all_pairs_complete=complete,
        missing_stop_ids=[sid for sid in ids if sid not in source_ids],
        zero_off_diagonal_pairs=zero_pairs,
        original_sources=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,
                               sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in archives],
        separate_full_graph_attempt=acquisition,
        interpretation='New all464 road graph unavailable; source292 costs are retained without mixing a new source.',
    )
    out=ROOT/'docs/evidence/road_extension_audit.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['missing_stop_ids','separate_full_graph_attempt','original_sources']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
