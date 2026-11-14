"""Semantic preprocessing tests; no route search or model training."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('role4_data', ROOT/'scripts/build_role4_data.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_pooled_days_and_missing_are_distinct_from_zero():
    observed = [dict(has_source_record=True, alight=31, days=31),
                dict(has_source_record=True, alight=90, days=30)]
    assert m.pooled_demand(observed) == 121/61
    assert m.pooled_demand([dict(has_source_record=True, alight=0, days=31)]) == 0
    assert m.pooled_demand(observed+[dict(has_source_record=False, alight=None, days=31)]) is None


def test_normalizer_is_explicit_and_validation_not_clipped():
    assert m.normalized(40, 100) == .4
    # A candidate filter is never an argument that could refit the denominator.
    assert m.normalized(150, 100) == 1.5
    assert m.normalized(None, 100) is None
    assert m.normalized(0, 0) == 0


def test_hub_group_minimum_and_tie_break():
    stop = dict(station_id='s', latitude=0., longitude=0.)
    anchors = [dict(hub_id='b', hub_name='B', anchor_id='b1', latitude=0., longitude=0.),
               dict(hub_id='a', hub_name='A', anchor_id='a2', latitude=0., longitude=0.),
               dict(hub_id='a', hub_name='A', anchor_id='a1', latitude=0., longitude=0.)]
    result = m.hub_assignment(stop, anchors, 0, 6371008.8)
    assert result['hub_id'] == 'a'
    assert result['hub_anchor_id'] == 'a1'
    assert len(result['hub_candidates']) == 2
    assert m.haversine(0, 0, 0, 1) == pytest.approx(111195.0802335329)


def test_reward_terms_and_first_group_only():
    cfg = dict(demand_weight=1, hub_bonus=.5, distance_cost_per_km=.2)
    assert m.reward_arithmetic(.4, 500, 'h', set(), cfg)['reward'] == pytest.approx(.8)
    assert m.reward_arithmetic(.4, 500, 'h', {'h'}, cfg)['reward'] == pytest.approx(.3)
    assert m.reward_arithmetic(.4, 500, None, set(), cfg)['reward'] == pytest.approx(.3)
    assert m.reward_arithmetic(None, 500, 'h', set(), cfg) is None
    assert m.reward_arithmetic(.4, None, 'h', set(), cfg) is None


@pytest.mark.parametrize('value', [-1, math.inf, math.nan])
def test_invalid_values_rejected(value):
    with pytest.raises(ValueError):
        m.finite_nonnegative(value, 'sample')


def test_real_bundle_independent_counts_and_arithmetic():
    d = json.loads((ROOT/'data/processed/role4_bundle.json').read_text(encoding='utf-8'))
    assert len(d['ids']) == len(set(d['ids'])) == 464
    assert d['ids'] == sorted(d['ids']) == [s['station_id'] for s in d['stops']]
    lookup = {s['station_id']: i for i, s in enumerate(d['stops'])}
    i = lookup['112000403']
    assert sum(d['months'][month]['alight'][i] for month in ['202605','202606','202607','202608']) == 104278
    assert d['stops'][i]['demand_daily_train'] == 104278/123
    assert d['stops'][i]['demand_score_train'] == 1
    assert d['stops'][i]['excluded_by_stop_policy'] is True
    for month in d['months'].values():
        assert sum(month['has_source_record']) == 454
        assert sum(v is None for v in month['alight']) == 10
    assert sum(s['demand_daily_train']==0 for s in d['stops']) == 1
    assert sum(v is None for i, row in enumerate(d['distances_m']) for j, v in enumerate(row) if i != j) == 129860
    assert d['distances_m'][lookup['112900003']][lookup['112900157']] == 0
    assert d['readiness']['full_district_model_ready'] is False
    assert [r['mapped_stops'] for r in d['hub_sensitivity']] == [61,103,186]
    assert [r['multi_group_candidates'] for r in d['hub_sensitivity']] == [0,0,36]
    assert any(v > 1 for v in d['months']['202609']['score'] if v is not None)
    diagnostic = json.loads((ROOT/'data/processed/diagnostic_259.json').read_text(encoding='utf-8'))
    assert len(diagnostic['ids']) == 259
    assert diagnostic['full_district'] is False
    assert all(value is not None for row in diagnostic['distances_m'] for value in row)
