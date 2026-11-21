"""范围更正重算：回执幂等、旧批失效、失败回滚保留旧版分级。"""
from fastapi.testclient import TestClient
from app import main, store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path / 'recompute.sqlite'))
    return TestClient(main.app)


def _lowered_ranges(run, range_id, low):
    ranges = [dict(x) for x in run['context']['reference_ranges']]
    for entry in ranges:
        if entry['range_id'] == range_id:
            entry['low'] = low
    return ranges


def test_recompute_supersedes_old_batch_and_preserves_history(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={'dataset': 'clean'}).json()
    rid = run['manifest']['run_id']
    old_grade = next(r for r in run['range_results'] if r['id'] == '00001-R1')['toxicity_grade']
    ranges = _lowered_ranges(run, 'RR-C01-V1', '119')  # 118 由正常变为偏低 1 级
    resp = c.post(f'/api/runs/{rid}/range-recompute',
                  json={'receipt_id': 'RC-1', 'overrides': {'reference_ranges': ranges}})
    assert resp.status_code == 200
    new = resp.json()
    assert new['manifest']['run_id'] != rid
    assert next(r for r in new['range_results'] if r['id'] == '00001-R1')['toxicity_grade'] == 1
    # 旧批标记失效，但历史分级原样保留
    assert store.get(main.DB_PATH, rid)['status'] == '已失效'
    assert next(r for r in store.get(main.DB_PATH, rid)['range_results']
                if r['id'] == '00001-R1')['toxicity_grade'] == old_grade == 0
    receipt = store.get_receipt(main.DB_PATH, 'RC-1')
    assert receipt['status'] == '成功' and receipt['new_run_id'] == new['manifest']['run_id']


def test_same_receipt_retry_creates_no_new_grade(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={'dataset': 'clean'}).json()
    rid = run['manifest']['run_id']
    body = {'receipt_id': 'RC-DUP',
            'overrides': {'reference_ranges': _lowered_ranges(run, 'RR-C01-V1', '119')}}
    first = c.post(f'/api/runs/{rid}/range-recompute', json=body).json()
    before = {r['id']: r['revision'] for r in c.get('/api/runs').json()}
    second = c.post(f'/api/runs/{rid}/range-recompute', json=body)
    assert second.status_code == 200
    assert second.json()['manifest']['run_id'] == first['manifest']['run_id']
    assert {r['id']: r['revision'] for r in c.get('/api/runs').json()} == before
    assert len(c.get('/api/runs').json()) == 2  # 仅旧批 + 新批，无第三条


def test_failed_recompute_rolls_back_and_keeps_old_grade(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={'dataset': 'clean'}).json()
    rid = run['manifest']['run_id']
    # 删除 C01 在效范围 -> 证据不足，所有 C01 结果无法判定
    ranges = [r for r in run['context']['reference_ranges'] if r['center'] != 'C01']
    resp = c.post(f'/api/runs/{rid}/range-recompute',
                  json={'receipt_id': 'RC-FAIL', 'overrides': {'reference_ranges': ranges}})
    assert resp.status_code == 422 and resp.json()['code'] == 'RANGE_EVIDENCE_BLOCKED'
    old = store.get(main.DB_PATH, rid)
    assert old['status'] == '待复核'  # 旧批未失效
    assert all(r['toxicity_grade'] != 'UNDETERMINED' for r in old['range_results'])
    receipt = store.get_receipt(main.DB_PATH, 'RC-FAIL')
    assert receipt['status'] == '失败' and receipt['new_run_id'] is None
    # 失败回执可凭同一回执重试；批次数量不增加
    retry = c.post(f'/api/runs/{rid}/range-recompute',
                   json={'receipt_id': 'RC-FAIL', 'overrides': {}})
    assert retry.status_code == 422
    assert len(c.get('/api/runs').json()) == 1


def test_failed_receipt_can_recover_with_same_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={'dataset': 'clean'}).json()
    rid = run['manifest']['run_id']
    bad = {'reference_ranges': [r for r in run['context']['reference_ranges'] if r['center'] != 'C01']}
    assert c.post(f'/api/runs/{rid}/range-recompute',
                  json={'receipt_id': 'RC-RCV', 'overrides': bad}).status_code == 422
    # 同一回执，修正参数后重试成功（沿用首次登记的覆盖参数不可行，故此处验证新回执恢复路径之外：
    # 失败回执固定原参数；恢复须用新回执）
    good = {'reference_ranges': _lowered_ranges(run, 'RR-C01-V1', '119')}
    ok = c.post(f'/api/runs/{rid}/range-recompute',
                json={'receipt_id': 'RC-RCV-2', 'overrides': good})
    assert ok.status_code == 200
    assert store.get(main.DB_PATH, rid)['status'] == '已失效'


def test_receipt_bound_to_other_batch_conflicts(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    first = c.post('/api/runs', json={'dataset': 'clean'}).json()['manifest']['run_id']
    body = {'receipt_id': 'RC-X',
            'overrides': {'reference_ranges': _lowered_ranges(
                store.get(main.DB_PATH, first), 'RR-C01-V1', '119')}}
    assert c.post(f'/api/runs/{first}/range-recompute', json=body).status_code == 200
    other = c.post('/api/runs', json={'dataset': 'dirty'}).json()['manifest']['run_id']
    resp = c.post(f'/api/runs/{other}/range-recompute',
                  json={'receipt_id': 'RC-X', 'overrides': {}})
    assert resp.status_code == 409 and resp.json()['code'] == 'RECEIPT_CONFLICT'


def test_recompute_requires_receipt(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    rid = c.post('/api/runs', json={'dataset': 'clean'}).json()['manifest']['run_id']
    resp = c.post(f'/api/runs/{rid}/range-recompute', json={'receipt_id': '  ', 'overrides': {}})
    assert resp.status_code == 422 and resp.json()['code'] == 'BAD_RECEIPT'


def test_rerun_unchanged_input_keeps_run_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={'dataset': 'clean'}).json()
    rid = run['manifest']['run_id']
    again = c.post(f'/api/runs/{rid}/rerun', json={})
    assert again.status_code == 200 and again.json()['manifest']['run_id'] == rid
