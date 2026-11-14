"""Compare demand definitions; no policies, route search, or model training."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/notion/01_data_preprocessing'


def read(name):
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def main():
    stops = {r['station_id']: r for r in read('01_region_stations_clean.csv')
             if r['station_id'].startswith('112')}
    records = read('02_region_ridership_7to9_monthly.csv')
    train = {}
    for row in records:
        if row['station_id'] in stops and row['split'] == 'train':
            train.setdefault(row['station_id'], []).append(row)
    if set(train) != set(stops) or any(len(v) != 4 for v in train.values()):
        raise ValueError('Expected four training months per stop')
    pooled = {i: sum(int(x['alight_07_09']) for x in rows) /
              sum(int(x['calendar_days']) for x in rows) for i, rows in train.items()}
    monthly = {i: sum(int(x['alight_07_09']) / int(x['calendar_days'])
                      for x in rows) / len(rows) for i, rows in train.items()}
    low, high = min(pooled.values()), max(pooled.values())
    max_monthly = max(monthly.values())
    ordered = sorted(stops)
    details = [{
        'station_id': i, 'name': stops[i]['station_name'],
        'pooled_daily_alight': pooled[i], 'monthly_mean_daily_alight': monthly[i],
        'pooled_minus_monthly': pooled[i] - monthly[i],
        'relative_difference_pct': 100 * (pooled[i] - monthly[i]) / monthly[i],
        'pooled_max_normalized': pooled[i] / high,
        'pooled_minmax_normalized': (pooled[i] - low) / (high - low) if high > low else 0,
        'legacy_normalized': monthly[i] / max(1, max_monthly),
    } for i in ordered]
    top_pooled = sorted(stops, key=lambda i: (-pooled[i], i))
    top_monthly = sorted(stops, key=lambda i: (-monthly[i], i))
    fixed_scale = {'max': high, 'min': low}
    validation = {}
    for row in records:
        if row['station_id'] not in stops or row['split'] != 'validation':
            continue
        day = int(row['alight_07_09']) / int(row['calendar_days'])
        normalized = (day - low) / (high - low) if high > low else 0
        validation.setdefault(row['month'], []).append(normalized)
    summary = {
        'date_kst': '2026-11-15', 'scope': 'all 282 prefix-112 stops in supplied study area',
        'train_months': sorted({r['month'] for rows in train.values() for r in rows}),
        'train_calendar_days': sum(int(x['calendar_days']) for x in next(iter(train.values()))),
        'stop_count': len(stops), 'fixed_pooled_scale': fixed_scale,
        'max_absolute_daily_difference': max(abs(r['pooled_minus_monthly']) for r in details),
        'max_absolute_relative_pct': max(abs(r['relative_difference_pct']) for r in details),
        'max_max_vs_minmax_score_difference': max(abs(r['pooled_max_normalized'] -
                                                    r['pooled_minmax_normalized']) for r in details),
        'top10_pooled': top_pooled[:10], 'top10_monthly': top_monthly[:10],
        'rank_changed_stop_count': sum(top_pooled.index(i) != top_monthly.index(i) for i in stops),
        'validation_fixed_train_minmax': {month: {
            'min': min(v), 'max': max(v), 'below_zero': sum(x < 0 for x in v),
            'above_one': sum(x > 1 for x in v)} for month, v in validation.items()},
        'rows': details,
        'interpretation': 'Definition comparison only; not policy or route performance evidence.',
    }
    out = ROOT / 'docs/evidence/demand_definition_audit.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
