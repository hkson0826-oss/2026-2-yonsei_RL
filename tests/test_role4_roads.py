"""Distance semantics checks independent of any model or route optimization."""
import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('role4_roads',Path(__file__).resolve().parents[1]/'scripts/build_role4_roads.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(a,b,d):
    return {'from_station_id':a,'to_station_id':b,'road_m':d}


def test_direction_and_unknown_are_preserved():
    matrix, covered, _=MODULE.build_matrix(['a','b','c'],[row('a','b',12),row('b','a',30)])
    assert matrix==[[0,12,None],[30,0,None],[None,None,0]]
    assert covered=={'a','b'}


def test_zero_observation_is_distinct_from_unknown():
    matrix, _, warnings=MODULE.build_matrix(['a','b'],[row('a','b',0)])
    assert matrix[0][1]==0 and matrix[1][0] is None
    assert warnings[0]['from_station_id']=='a'


@pytest.mark.parametrize('bad',[-1,float('nan'),float('inf')])
def test_invalid_cost_is_rejected(bad):
    with pytest.raises(ValueError):MODULE.build_matrix(['a','b'],[row('a','b',bad)])


def test_duplicate_direction_is_rejected():
    with pytest.raises(ValueError):MODULE.build_matrix(['a','b'],[row('a','b',2),row('a','b',2)])


def test_wrong_identity_cost_is_rejected():
    with pytest.raises(ValueError):MODULE.build_matrix(['a'],[row('a','a',1)])


def test_other_district_rows_are_not_imported():
    matrix,covered,_=MODULE.build_matrix(['a','b'],[row('elsewhere','a',10)])
    assert matrix==[[0,None],[None,0]] and covered==set()
