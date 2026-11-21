from app.engine import evaluate
from app.errors import BusinessError
from app.config import ROOT
import pytest

def test_bom_real(sample):
    # TRAP-02
    assert sample['records'][0]['id']=='00001-V1'
def test_legacy_real():
    # TRAP-01
    s=evaluate({'dataset':'legacy'});assert s['encoding']=='gb18030';assert s['records'][0]['unit']=='毫克/分升'
def test_leading_zero_real(sample):
    # TRAP-08
    assert sample['records'][0]['subject']=='00001'
def test_header_real(sample):
    # TRAP-04
    assert sample['counts']['repeated_header']==1
def test_columns_real(sample):
    # TRAP-05
    assert next(r for r in sample['quarantine'] if r['id']=='COLUMN')['code']=='COLUMN_COUNT'
def test_duplicate_real(sample):
    assert sample['counts']['duplicate']==1
def test_empty_types():
    # TRAP-18
    for text,code in [('', 'EMPTY_FILE'),('\n\n','BLANK_FILE'),((ROOT/'sample_data/clean.csv').read_text().splitlines()[0]+'\n','HEADER_ONLY')]:
        with pytest.raises(BusinessError) as e:evaluate({'csv_text':text})
        assert e.value.code==code
