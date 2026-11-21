from app.modules.retest.rules import adjudicate
from copy import deepcopy

def test_retest_selected_real(clean):
    row=next(r for r in clean['selected_results'] if r['primary_id']=='00001-V1');assert row['id']=='00001-R1';assert row['value_mg_dl']=='118'
def test_orphan_retest_real(sample):
    assert next(r for r in sample['retest_issues'] if r['id']=='ORPHAN')['code']=='RETEST_REFERENCE'
def test_retest_before_primary_real(sample):
    assert next(r for r in sample['retest_issues'] if r['id']=='00001-R1')['code']=='RETEST_WINDOW'
def test_retest_cannot_repair_deviation(sample):
    assert any(r['code']=='WINDOW_LATE' for r in sample['deviations']);assert sample['balance']['status']=='待处理'
def test_same_version_conflict(clean):
    rows=[dict(r) for r in clean['records']];rows.append(dict(next(r for r in rows if r['id']=='00001-R1'),id='R-DUP'));selected,issues=adjudicate(rows,clean['context']);assert issues[0]['code']=='RETEST_VERSION_CONFLICT'
def test_other_subject_reference(clean):
    rows=[dict(r) for r in clean['records']];row=next(r for r in rows if r['id']=='00001-R1');row['parent']='00002-V1';_,issues=adjudicate(rows,clean['context']);assert issues[0]['code']=='RETEST_REFERENCE'
def test_retest_max_72_hours_inclusive(clean):
    rows=[dict(r) for r in clean['records']];row=next(r for r in rows if r['id']=='00001-R1');row['at']='2026-10-11T00:00:00+00:00';selected,issues=adjudicate(rows,clean['context']);assert not issues;assert next(r for r in selected if r['primary_id']=='00001-V1')['id']=='00001-R1'
