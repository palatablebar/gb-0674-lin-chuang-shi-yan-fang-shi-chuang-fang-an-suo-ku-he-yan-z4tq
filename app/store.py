import sqlite3, json
from pathlib import Path
from app.errors import BusinessError

def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(path,timeout=15)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, result TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT '待复核')")
    con.execute("""CREATE TABLE IF NOT EXISTS range_receipts (
        receipt_id TEXT PRIMARY KEY,
        source_run_id TEXT NOT NULL,
        new_run_id TEXT,
        overrides TEXT NOT NULL,
        status TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    return con

def save(path, result):
    run_id=result['manifest']['run_id']
    with connect(path) as con:
        con.execute('INSERT OR IGNORE INTO runs(id,digest,result) VALUES(?,?,?)', (run_id,result['manifest']['sha256'],json.dumps(result,ensure_ascii=False)))
    return get(path,run_id)

def get(path, run_id):
    with connect(path) as con: row=con.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row: raise BusinessError('NOT_FOUND','批次不存在',404)
    result=json.loads(row['result']);result.update(revision=row['revision'],status=row['status'])
    return result

def history(path):
    with connect(path) as con:
        return [dict(r) for r in con.execute('SELECT id,revision,status FROM runs ORDER BY rowid DESC LIMIT 100')]

def review(path,run_id,revision):
    with connect(path) as con:
        cur=con.execute('UPDATE runs SET revision=revision+1,status=? WHERE id=? AND revision=?',('已复核',run_id,revision))
        if cur.rowcount!=1:
            if not con.execute('SELECT 1 FROM runs WHERE id=?',(run_id,)).fetchone():
                raise BusinessError('NOT_FOUND','批次不存在',404)
            raise BusinessError('STALE_VERSION','复核版本已更新，请刷新',409)
    return get(path,run_id)

def get_receipt(path, receipt_id):
    with connect(path) as con:
        row=con.execute('SELECT * FROM range_receipts WHERE receipt_id=?',(receipt_id,)).fetchone()
    return dict(row) if row else None

def recompute_with_receipt(path, receipt_id, source_run_id, overrides, evaluate_fn):
    """范围更正重算。

    同一回执重试：返回首次登记的结果，绝不新增分级或新批次。
    重算成功才置旧批为“已失效”；任一步失败回滚全部批次改动，旧批保留旧版分级，
    仅保留失败回执作为审计线索（可凭同一回执重试）。
    """
    con=connect(path)
    try:
        existing=con.execute('SELECT * FROM range_receipts WHERE receipt_id=?',(receipt_id,)).fetchone()
        if existing:
            if existing['source_run_id']!=source_run_id:
                raise BusinessError('RECEIPT_CONFLICT','回执已绑定其他批次',409)
            if existing['status']=='成功':
                con.close()
                return get(path, existing['new_run_id']), dict(existing)
            # 失败回执可重试：沿用原覆盖参数，忽略本次传入差异
            overrides=json.loads(existing['overrides'])
        else:
            if not con.execute('SELECT 1 FROM runs WHERE id=?',(source_run_id,)).fetchone():
                raise BusinessError('NOT_FOUND','批次不存在',404)
            # 回执先独立落库并提交：后续失败/回滚都不抹掉审计线索
            con.execute('INSERT INTO range_receipts(receipt_id,source_run_id,overrides,status,detail) VALUES(?,?,?,?,?)',
                        (receipt_id,source_run_id,json.dumps(overrides,ensure_ascii=False),'处理中',''))
            con.commit()
        try:
            previous=get(path,source_run_id)
            if 'input_snapshot' not in previous:
                raise BusinessError('INPUT_SNAPSHOT_MISSING','旧批缺少源快照，请重新导入')
            # 先完成全部计算；计算失败抛错，批次事务回滚后旧批与旧版分级原样保留
            new_result=evaluate_fn({'dataset':previous['source'],'overrides':overrides},
                                   snapshot=previous['input_snapshot'])
            if new_result.get('range_blocks'):
                codes=sorted({b['block_code'] for b in new_result['range_blocks']})
                raise BusinessError('RANGE_EVIDENCE_BLOCKED','范围依据证据不足：'+','.join(codes))
            new_id=new_result['manifest']['run_id']
            con.execute('BEGIN IMMEDIATE')
            con.execute('INSERT OR IGNORE INTO runs(id,digest,result) VALUES(?,?,?)',
                        (new_id,new_result['manifest']['sha256'],json.dumps(new_result,ensure_ascii=False)))
            con.execute("UPDATE runs SET status='已失效' WHERE id=? AND status!='已失效'",(source_run_id,))
            con.execute("UPDATE range_receipts SET status='成功',new_run_id=?,detail='' WHERE receipt_id=?",
                        (new_id,receipt_id))
            con.commit()
        except Exception as exc:
            con.rollback()
            # 同一连接回滚后补记失败回执：保留审计线索，且不影响已回滚的批次数据
            con.execute("UPDATE range_receipts SET status='失败',detail=? WHERE receipt_id=?",
                        (str(getattr(exc,'message',exc)),receipt_id))
            con.commit()
            raise
    finally:
        con.close()
    return get(path,new_id), get_receipt(path,receipt_id)
