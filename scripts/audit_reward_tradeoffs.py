"""Describe reward-scale tradeoffs and small analytic cases, without model runs."""
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT/'data/processed/role4_bundle.json'
    bundle = json.loads(path.read_text(encoding='utf-8'))
    cfg = bundle['config']['reward']
    populations = {
        'all_train_observed': [s for s in bundle['stops'] if s['complete_train']],
        'noncentral_train_observed': [s for s in bundle['stops']
                                     if s['complete_train'] and not s['excluded_by_stop_policy']],
        'diagnostic_source_subset': [s for s in bundle['stops'] if s['diagnostic_subset_eligible']],
    }
    result = dict(date_kst='2026-11-15',
                  source_bundle_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  method='descriptive scale and analytic examples only; no policy search or training',
                  hub_bonus=cfg['hub_bonus'], distance_cost_per_km=cfg['distance_cost_per_km'],
                  hub_bonus_distance_equivalent_km=cfg['hub_bonus']/cfg['distance_cost_per_km'], groups={})
    for name, stops in populations.items():
        median = statistics.median(s['demand_score_train'] for s in stops)
        top = max(stops, key=lambda s: s['demand_score_train'])
        result['groups'][name] = dict(n=len(stops), median_score=median,
             max_score=top['demand_score_train'], max_station_id=top['station_id'],
             max_station_name=top['station_name'],
             hub_bonus_in_median_stop_scores=cfg['hub_bonus']/median if median else None,
             median_score_distance_equivalent_m=median/cfg['distance_cost_per_km']*1000)
    # These are deliberately hypothetical arithmetic examples, not generated routes.
    result['analytic_examples'] = {
        'dense_five_score_0_2_same_1km': 5*.2-cfg['distance_cost_per_km'],
        'single_score_0_7_same_1km': .7-cfg['distance_cost_per_km'],
        'negative_continuation_score_0_01_extra_500m': .01-cfg['distance_cost_per_km']*.5,
        'stop_terminal_increment': 0,
        'new_hub_score_0_4_500m': .4+cfg['hub_bonus']-cfg['distance_cost_per_km']*.5,
        'same_hub_score_0_4_500m': .4-cfg['distance_cost_per_km']*.5,
        'interpretation': 'objective meaning and termination distinctions; no algorithm performance claim',
    }
    out = ROOT/'docs/evidence/reward_tradeoff_audit.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['groups']['noncentral_train_observed'],ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
