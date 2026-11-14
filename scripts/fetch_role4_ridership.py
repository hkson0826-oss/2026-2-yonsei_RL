"""Fetch free OA-12913 monthly source files and aggregate the official district universe."""
import calendar
import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'data/reference'
PAGE = 'https://data.seoul.go.kr/dataList/OA-12913/S/1/datasetView.do'


def acquire(month):
    seq = 105 + month
    url = ('https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?'
           f'useCache=false&infId=OA-12913&seq={seq}&infSeq=3')
    dest = REF / 'raw_ridership' / f'seoul_bus_hourly_2026{month:02d}.csv.gz'
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raw = gzip.decompress(dest.read_bytes())
    else:
        with urlopen(url, timeout=60) as response:
            raw = response.read()
        if len(raw) < 1_000_000 or b'<html' in raw[:100].lower():
            raise ValueError(f'Not a monthly CSV: {url}')
        dest.write_bytes(gzip.compress(raw, mtime=0))
    encoding = 'utf-8-sig'
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = 'cp949'
        text = raw.decode(encoding)
    by_stop = defaultdict(lambda: [0, 0, 0, 0, 0])
    count = 0
    for row in csv.DictReader(io.StringIO(text, newline='')):
        if row['사용년월'] != f'2026{month:02d}':
            raise ValueError('Unexpected month in source')
        values = by_stop[row['표준버스정류장ID']]
        for k, field in enumerate(['7시승차총승객수', '7시하차총승객수',
                                   '8시승차총승객수', '8시하차총승객수']):
            values[k] += int(row[field])
        values[4] += 1
        count += 1
    meta = dict(month=f'2026{month:02d}', source_page=PAGE, download_url=url,
                encoding=encoding, raw_bytes=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest(),
                preserved_path=dest.relative_to(ROOT).as_posix(), source_rows=count,
                aggregation='sum route/direction records by standard stop ID; hours 07 and 08 only')
    return month, by_stop, meta


def main():
    inventory = REF / 'seodaemun_bus_stops_official.csv'
    with inventory.open(encoding='utf-8-sig', newline='') as handle:
        stops = list(csv.DictReader(handle))
    id_column = 'station_id'
    if not stops or id_column not in stops[0]:
        raise ValueError('Official district inventory must have station_id')
    if len({s[id_column] for s in stops}) != len(stops):
        raise ValueError('Duplicate official station IDs')
    with ThreadPoolExecutor(max_workers=2) as pool:
        source = sorted(pool.map(acquire, range(5, 11)))
    fields = ['month', 'station_id', 'has_source_record', 'calendar_days', 'split',
              'board_07', 'alight_07', 'board_08', 'alight_08', 'board_07_09',
              'alight_07_09', 'total_07_09', 'source_route_rows']
    out = REF / 'seodaemun_ridership_202605_202610.csv'
    coverage = {}
    with out.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for month, grouped, meta in source:
            missing = []
            for stop in stops:
                sid = stop[id_column]
                values = grouped.get(sid)
                row = dict(month=f'2026{month:02d}', station_id=sid,
                           has_source_record=int(values is not None),
                           calendar_days=calendar.monthrange(2026, month)[1],
                           split='train' if month <= 8 else 'validation')
                if values is not None:
                    b7, a7, b8, a8, routes = values
                    row.update(board_07=b7, alight_07=a7, board_08=b8, alight_08=a8,
                               board_07_09=b7+b8, alight_07_09=a7+a8,
                               total_07_09=b7+b8+a7+a8, source_route_rows=routes)
                else:
                    missing.append(sid)
                writer.writerow(row)
            coverage[meta['month']] = dict(observed=len(stops)-len(missing), missing_ids=missing)
    # Compare independently recovered sources with supplied team aggregates.
    lookup = {(meta['month'], sid): v[1]+v[3]
              for _, grouped, meta in source for sid, v in grouped.items()}
    mismatch = []
    with (ROOT/'docs/notion/01_data_preprocessing/02_region_ridership_7to9_monthly.csv').open(
            encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            key = (row['month'], row['station_id'])
            if row['station_id'] in {s[id_column] for s in stops} and lookup.get(key) != int(row['alight_07_09']):
                mismatch.append(dict(month=key[0], station_id=key[1],
                                     team=int(row['alight_07_09']), recovered=lookup.get(key)))
    manifest = dict(snapshot_date_kst='2026-11-15', source_page=PAGE,
                    inventory=inventory.relative_to(ROOT).as_posix(), universe_count=len(stops),
                    output=out.relative_to(ROOT).as_posix(), sources=[v[2] for v in source],
                    coverage=coverage, team_aggregate_mismatch=mismatch,
                    missing_policy='empty numeric fields and has_source_record=0; never impute zero')
    (REF/'ridership_provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='sources'},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
