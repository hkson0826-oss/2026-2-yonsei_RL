"""Build a self-contained reference map; no training or route generation."""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'data/processed/role4_bundle.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    if len(data['ids']) != len(data['stops']) or len(set(data['ids'])) != len(data['ids']):
        raise ValueError('Invalid map station index')
    route_folder = ROOT / 'data/routes/v1'
    if (route_folder / 'routes.geojson').exists():
        routes = json.loads((route_folder / 'routes.geojson').read_text(encoding='utf-8'))
        manifest = json.loads((route_folder / 'manifest.json').read_text(encoding='utf-8'))
        with (route_folder / 'route_metrics.csv').open(encoding='utf-8-sig', newline='') as handle:
            metrics = list(csv.DictReader(handle))
        for feature in routes['features']:
            props = feature['properties']
            if props['from_station_id'] not in data['ids'] or props['to_station_id'] not in data['ids']:
                raise ValueError('Route endpoint outside reference inventory')
        data['selected_routes'] = dict(features=routes['features'], metrics=metrics, manifest=manifest)
    contract = ROOT / 'data/reward_contract_v2.json'
    if contract.exists():
        data['reward_review_contract'] = json.loads(contract.read_text(encoding='utf-8'))
    template = (ROOT/'web/role4_map_template.html').read_text(encoding='utf-8')
    if template.count('__ROLE4_DATA__') != 1:
        raise ValueError('Expected exactly one map data placeholder')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    output = ROOT/'output/role4/station_map.html'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace('__ROLE4_DATA__', payload.replace('</', '<\\/')), encoding='utf-8')
    print(f'Map: {output} ({len(data["ids"])} reference stops)')


if __name__ == '__main__':
    main()
