"""参考范围与毒性分级。

双轨依据：
- 判定范围（adjudication）：采样时刻、受试者所属中心、检验项目对应的唯一在效中心范围；
  毒性分级只允许依据判定范围，分级与偏离、复检、锁库共用同一结论。
- 跨中心比较范围（harmonized）：分析方统一新版范围，只用于跨中心比较展示，
  绝不参与分级或锁库判定。

采样时刻落在新版生效窗之前的历史结果沿用旧版；找不到唯一在效范围则证据不足，
生成阻断项，该结果分级置为 UNDETERMINED 并继续阻断锁库。
"""
from app.coerce import instant, number
from app.errors import BusinessError

ANALYTE = 'HGB'
BLOCK_CODES = {
    'CENTER_UNKNOWN': '受试者未分配中心，范围依据无法确定',
    'ANALYTE_UNKNOWN': '检验项目未登记参考范围',
    'RANGE_NOT_FOUND': '采样时刻无在效中心参考范围',
    'RANGE_CONFLICT': '采样时刻存在多个在效中心参考范围',
    'RANGE_BAD': '参考范围配置错误（下限不小于上限或阈值非数值）',
    'TOXICITY_MISSING': '毒性分级阈值缺失，无法分级',
}
HARMONIZED_CODES = {
    'HARMONIZED_MISSING': '未配置跨中心统一新版范围，仅保留中心判定',
    'HARMONIZED_CONFLICT': '跨中心统一范围配置冲突，仅保留中心判定',
}


def _validated(entry):
    try:
        low, high = number(entry['low']), number(entry['high'])
    except (BusinessError, KeyError, TypeError):
        return None
    if low >= high:
        return None
    return low, high


def _active(ranges, analyte, center, at):
    """采样时刻在效的中心范围，半开生效窗 [start, end)，匹配必须唯一。"""
    matches = []
    for entry in ranges:
        if entry.get('analyte') != analyte or entry.get('center') != center:
            continue
        if instant(entry['start']) <= at < instant(entry['end']):
            bounds = _validated(entry)
            if bounds is None:
                return None, 'RANGE_BAD'
            matches.append((entry, bounds))
    if len(matches) > 1:
        return None, 'RANGE_CONFLICT'
    if not matches:
        return None, 'RANGE_NOT_FOUND'
    return matches[0], None


def _harmonized(context, analyte):
    """分析方统一新版范围；仅用于比较，缺失不阻断判定与锁库。"""
    spec = context.get('harmonized')
    if not spec or spec.get('analyte') != analyte:
        return None, 'HARMONIZED_MISSING'
    wanted = spec.get('range_id')
    hits = [r for r in context.get('reference_ranges', [])
            if r.get('range_id') == wanted and r.get('center') == '*' and r.get('analyte') == analyte]
    if len(hits) != 1 or _validated(hits[0]) is None:
        return None, 'HARMONIZED_CONFLICT'
    entry = hits[0]
    return (entry, _validated(entry)), None


def grade(value, low, high, table):
    """按 ULN/LLN 倍数的半开区间做毒性分级，阈值确定性可复核。"""
    if not table or not table.get('high') or not table.get('low'):
        return None, 'TOXICITY_MISSING'
    if low <= value <= high:
        return 0, None
    if value > high:
        last = 0
        for step in sorted(table.get('high', []), key=lambda x: number(x['factor'])):
            factor = number(step['factor'])
            if value >= high * factor:
                last = int(step['grade'])
        return last, None
    # 低于下限即为 1 级；命中更深的加重倍数时逐级上调
    grade_now = 1
    for step in sorted(table.get('low', []), key=lambda x: number(x['factor'])):
        factor = number(step['factor'])
        if value <= low * factor:
            grade_now = max(grade_now, int(step['grade']))
    return grade_now, None


def evaluate_row(row, context):
    at = instant(row['at'])
    result = {
        'id': row['id'], 'subject': row['subject'], 'visit': row['visit'],
        'kind': row['kind'], 'center': '', 'analyte': ANALYTE,
        'value_mg_dl': row['value_mg_dl'], 'sampled_at': row['at'],
        'adj_range_id': '', 'adj_version': '', 'adj_low': '', 'adj_high': '',
        'adj_flag': '', 'toxicity_grade': 'UNDETERMINED',
        'harm_range_id': '', 'harm_low': '', 'harm_high': '', 'harm_flag': '',
        'basis': '', 'block_code': '', 'block_reason': '',
        'harm_note': '', 'line': row.get('_line', 0),
    }
    value = number(row['value_mg_dl'])
    center = context.get('centers', {}).get(row['subject'])
    if not center:
        result.update(block_code='CENTER_UNKNOWN', block_reason=BLOCK_CODES['CENTER_UNKNOWN'],
                      basis='证据不足，未判定')
        return result
    result['center'] = center
    if ANALYTE not in context.get('analytes', {}):
        result.update(block_code='ANALYTE_UNKNOWN', block_reason=BLOCK_CODES['ANALYTE_UNKNOWN'],
                      basis='证据不足，未判定')
        return result
    known_centers = {e.get('center') for e in context.get('reference_ranges', []) if e.get('center') != '*'}
    if center not in known_centers:
        result.update(block_code='CENTER_UNKNOWN',
                      block_reason=f'中心 {center} 未登记任何参考范围，范围依据无法确定',
                      basis='证据不足，未判定')
        return result
    picked, error = _active(context.get('reference_ranges', []), ANALYTE, center, at)
    if error:
        result.update(block_code=error, block_reason=BLOCK_CODES[error], basis='证据不足，未判定')
        return result
    entry, (low, high) = picked
    result.update(adj_range_id=entry['range_id'], adj_version=entry['version'],
                  adj_low=str(low), adj_high=str(high),
                  adj_flag='正常' if low <= value <= high else ('偏高' if value > high else '偏低'))
    g, gerr = grade(value, low, high, context.get('toxicity_bounds', {}).get(ANALYTE))
    if gerr:
        result.update(block_code=gerr, block_reason=BLOCK_CODES[gerr], basis='证据不足，未判定')
        return result
    result['toxicity_grade'] = g
    result['basis'] = f"采样时刻{center}在效范围 {entry['range_id']}（{entry['version']}）"
    harm, hcode = _harmonized(context, ANALYTE)
    if harm is None:
        result['harm_flag'] = '不适用'
        result['harm_note'] = HARMONIZED_CODES[hcode]  # 比较范围缺失仅提示，不阻断
    else:
        hentry, (hlow, hhigh) = harm
        result.update(harm_range_id=hentry['range_id'], harm_low=str(hlow), harm_high=str(hhigh),
                      harm_flag='正常' if hlow <= value <= hhigh else ('偏高' if value > hhigh else '偏低'))
    return result


def apply(state):
    rows, blocks = [], []
    for row in state['records']:
        item = evaluate_row(row, state['context'])
        rows.append(item)
        if item['block_code']:
            blocks.append({k: item[k] for k in ('id', 'subject', 'visit', 'center', 'block_code', 'block_reason', 'line')})
    state['range_results'] = rows
    state['range_blocks'] = blocks
    diverted = sum(1 for r in rows if r['harm_flag'] in ('偏高', '偏低') and r['adj_flag'] == '正常')
    state['views']['ranges'] = {
        'title': '范围依据与分级',
        'rows': rows,
        'metrics': {
            '判定结果': len(rows),
            '毒性异常': sum(1 for r in rows if isinstance(r['toxicity_grade'], int) and r['toxicity_grade'] > 0),
            '分级不一致(比较)': diverted,
            '范围阻断': len(blocks),
        },
    }
