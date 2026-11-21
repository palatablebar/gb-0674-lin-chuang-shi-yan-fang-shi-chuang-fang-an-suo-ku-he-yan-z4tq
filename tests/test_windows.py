from app.modules.windows.rules import calculate

def test_visits_complete_real(clean):
    assert len(clean['windows'])==45
def test_day_real(clean):
    assert clean['windows'][0]['day']==7
def test_late_real(sample):
    assert sample['windows'][0]['code']=='LATE';assert sample['windows'][0]['day']==11
def test_half_open_end(clean):
    # TRAP-23
    row=dict(clean['records'][0],at='2026-10-11T00:00:00+08:00');assert calculate(row,clean['context'])['code']=='LATE'
def test_window_start_included(clean):
    row=dict(clean['records'][0],at='2026-10-06T00:00:00+08:00');assert calculate(row,clean['context'])['code']=='IN_WINDOW'
def test_early_visit(clean):
    row=dict(clean['records'][0],at='2026-10-05T23:59:59+08:00');assert calculate(row,clean['context'])['code']=='EARLY'
def test_utc_day_equivalence(clean):
    # TRAP-11
    a=calculate(dict(clean['records'][0],at='2026-10-07T16:00:00Z'),clean['context']);b=calculate(dict(clean['records'][0],at='2026-10-08T00:00:00+08:00'),clean['context']);assert a['day']==b['day']==7
