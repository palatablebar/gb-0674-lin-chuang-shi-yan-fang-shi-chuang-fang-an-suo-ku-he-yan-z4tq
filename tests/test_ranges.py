"""范围依据与毒性分级：双轨范围、证据阻断、跨模块同结论。"""
from copy import deepcopy
from decimal import Decimal
from app.engine import evaluate
from app.modules.ranges.rules import grade

CTX = evaluate({'dataset': 'clean'})


def test_every_result_has_unique_adjudication_range_real(clean):
    assert len(clean['range_results']) == len(clean['records']) == 45
    assert all(r['adj_range_id'] and r['adj_version'] and r['basis'] for r in clean['range_results'])
    assert clean['range_blocks'] == []


def test_sampling_time_range_not_retroactive_real(clean):
    # C01 v2 于 2026-11-01 生效，10 月采样的历史结果必须沿用 v1
    rows = [r for r in clean['range_results'] if r['center'] == 'C01']
    assert rows and all(r['adj_range_id'] == 'RR-C01-V1' and r['adj_version'] == 'v1' for r in rows)


def test_harmonized_is_comparison_only_real(clean):
    # 118 的复检：中心旧版 115-150 判定正常 G0；统一新版 119-155 比较偏低，但分级不被改写
    row = next(r for r in clean['range_results'] if r['id'] == '00001-R1')
    assert row['adj_flag'] == '正常' and row['toxicity_grade'] == 0
    assert row['harm_range_id'] == 'RR-HARM-V2' and row['harm_flag'] == '偏低'
    assert clean['balance']['status'] == '可锁库'


def test_same_value_diverges_across_centers_but_converges_in_comparison(clean):
    # 同一 120mg/dL：C01/C02 中心范围判定正常，C03（下限125）判定偏低 1 级
    flags = {}
    for center in ('C01', 'C02', 'C03'):
        row = next(r for r in clean['range_results'] if r['center'] == center and r['kind'] == 'PRIMARY')
        flags[center] = (row['adj_flag'], row['toxicity_grade'], row['harm_flag'])
    assert flags['C01'][0] == flags['C02'][0] == '正常'
    assert flags['C03'] == ('偏低', 1, '正常')  # 统一新版下跨中心比较一致


def test_grade_boundaries_half_open():
    table = CTX['context']['toxicity_bounds']['HGB']
    low, high = Decimal('115'), Decimal('150')
    assert grade(Decimal('115'), low, high, table)[0] == 0
    assert grade(Decimal('150'), low, high, table)[0] == 0
    assert grade(Decimal('114.9'), low, high, table)[0] == 1
    assert grade(Decimal('103.5'), low, high, table)[0] == 1   # 0.9 倍含
    assert grade(Decimal('86.25'), low, high, table)[0] == 2   # 0.75 倍含
    assert grade(Decimal('57.5'), low, high, table)[0] == 3    # 0.5 倍含
    assert grade(Decimal('150.1'), low, high, table)[0] == 1
    assert grade(Decimal('225'), low, high, table)[0] == 2      # 1.5 倍含
    assert grade(Decimal('300'), low, high, table)[0] == 3      # 2 倍含


def test_missing_toxicity_table_blocks():
    s = evaluate({'dataset': 'clean',
                  'overrides': {'toxicity_bounds': {'HGB': {'high': [], 'low': []}}}})
    assert {b['block_code'] for b in s['range_blocks']} == {'TOXICITY_MISSING'}
    assert all(r['toxicity_grade'] == 'UNDETERMINED' for r in s['range_results'])
    assert s['balance']['status'] == '待处理'


def test_unknown_center_blocks():
    s = evaluate({'dataset': 'clean', 'overrides': {'centers': {'00001': 'C99'}}})
    codes = {b['block_code'] for b in s['range_blocks']}
    assert codes == {'CENTER_UNKNOWN'}
    row = next(r for r in s['range_results'] if r['id'] == '00001-V1')
    assert row['toxicity_grade'] == 'UNDETERMINED' and row['block_reason']


def test_no_active_range_at_sampling_time_blocks():
    ranges = [dict(x, end='2026-01-02T00:00:00+08:00') if x['range_id'] == 'RR-C01-V1' else x
              for x in CTX['context']['reference_ranges']]
    s = evaluate({'dataset': 'clean', 'overrides': {'reference_ranges': ranges}})
    assert {b['block_code'] for b in s['range_blocks']} == {'RANGE_NOT_FOUND'}
    assert s['balance']['range_blocks'] >= 1 and s['balance']['status'] == '待处理'


def test_overlapping_active_ranges_block():
    dup = dict(next(x for x in CTX['context']['reference_ranges'] if x['range_id'] == 'RR-C01-V1'),
               range_id='RR-C01-DUP')
    s = evaluate({'dataset': 'clean',
                  'overrides': {'reference_ranges': CTX['context']['reference_ranges'] + [dup]}})
    assert {b['block_code'] for b in s['range_blocks']} == {'RANGE_CONFLICT'}


def test_invalid_range_bounds_block():
    ranges = [dict(x, low='200') if x['range_id'] == 'RR-C01-V1' else x
              for x in CTX['context']['reference_ranges']]
    s = evaluate({'dataset': 'clean', 'overrides': {'reference_ranges': ranges}})
    assert {b['block_code'] for b in s['range_blocks']} == {'RANGE_BAD'}


def test_missing_harmonized_range_does_not_block():
    s = evaluate({'dataset': 'clean', 'overrides': {'harmonized': {'analyte': 'HGB', 'range_id': 'GHOST'}}})
    row = next(r for r in s['range_results'] if r['id'] == '00001-V1')
    assert row['harm_flag'] == '不适用' and row['harm_note']
    assert s['balance']['range_blocks'] == 0 and s['balance']['status'] == '可锁库'


def test_retest_grading_shares_same_basis(clean):
    # 复检裁决选定结果必须携带范围模块的同一份范围依据与分级
    by_id = {r['id']: r for r in clean['range_results']}
    for picked in clean['selected_results']:
        basis = by_id[picked['id']]
        assert picked['adj_range_id'] == basis['adj_range_id']
        assert picked['toxicity_grade'] == basis['toxicity_grade']
        assert picked['basis'] == basis['basis']


def test_locking_counts_range_blocks(clean):
    s = deepcopy(clean)
    s['range_blocks'] = [{'id': 'x', 'block_code': 'RANGE_NOT_FOUND'}]
    from app.modules.locking.rules import decide
    balance = decide(s)
    assert balance['range_blocks'] == 1 and balance['blocked'] >= 1
    assert balance['status'] == '待处理'


def test_archive_seal_covers_range_basis(clean):
    from app.modules.archive.rules import freeze
    s = deepcopy(clean)
    s['range_results'][0]['adj_range_id'] = 'RR-CHANGED'
    assert freeze(s)['seal'] != clean['archive']['seal']


def test_order_invariant(clean):
    s = deepcopy(clean)
    s['records'] = list(reversed(s['records']))
    from app.modules.ranges.rules import apply
    apply(s)
    a = sorted((r['id'], r['adj_range_id'], str(r['toxicity_grade'])) for r in clean['range_results'])
    b = sorted((r['id'], r['adj_range_id'], str(r['toxicity_grade'])) for r in s['range_results'])
    assert a == b
