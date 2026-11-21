from app.modules.protocol.rules import choose_protocol,normalize
from app.coerce import instant
from app.errors import BusinessError
from copy import deepcopy
import pytest

def test_subject_specific_real(clean):
    assert next(r for r in clean['records'] if r['id']=='00001-V2')['selected_protocol']=='v2';assert next(r for r in clean['records'] if r['id']=='00002-V2')['selected_protocol']=='v1'
def test_older_visit_version_real(clean):
    assert next(r for r in clean['records'] if r['id']=='00001-V1')['selected_protocol']=='v1'
def test_sentinel_real(sample):
    # TRAP-07
    assert next(r for r in sample['quarantine'] if r['id']=='BAD1')['code']=='MISSING_VALUE'
def test_wrong_global_latest_real(sample):
    assert next(r for r in sample['quarantine'] if r['id']=='BAD2')['code']=='PROTOCOL_MISMATCH'
def test_overlap_assignment(clean):
    # TRAP-25
    c=deepcopy(clean['context']);c['assignments']['00002'].append(dict(c['assignments']['00002'][0],version='v2'))
    with pytest.raises(BusinessError) as e:choose_protocol('00002',instant('2026-10-15T00:00:00+08:00'),c)
    assert e.value.code=='PROTOCOL_CONFLICT'
def test_unit_conversion_real(clean):
    # TRAP-15
    assert clean['records'][0]['value_mg_dl']=='120.0'
def test_enrollment_mismatch(clean):
    with pytest.raises(BusinessError) as e:normalize(dict(clean['records'][0],enrolled='2026-10-02T00:00:00+08:00'),clean['context'])
    assert e.value.code=='ENROLLMENT_CONFLICT'
