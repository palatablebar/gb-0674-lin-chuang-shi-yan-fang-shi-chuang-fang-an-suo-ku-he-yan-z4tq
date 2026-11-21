from app.modules.locking.rules import decide
from copy import deepcopy

def test_clean_lockable(clean):
    assert clean['balance']['status']=='可锁库'
def test_dirty_blocks(sample):
    assert sample['balance']['blocked']==7;assert sample['balance']['status']=='待处理'
def test_input_conservation(sample):
    assert sample['balance']['input']==51;assert sample['balance']['accepted']==45;assert sample['balance']['quarantined']==3;assert sample['balance']['row_balanced']
def test_completed_expected(clean):
    assert clean['balance']['completed']==clean['balance']['expected']==40
def test_isolation_blocks(clean):
    s=deepcopy(clean);s['quarantine']=[{'id':'x'}];assert decide(s)['status']=='待处理'
def test_count_mismatch_blocks(clean):
    s=deepcopy(clean);s['counts']['input']+=1;assert decide(s)['status']=='待处理';assert decide(s)['row_balanced'] is False
def test_missing_visit_not_replaced(sample):
    assert sample['balance']['completed']==38;assert sample['balance']['expected']==40
