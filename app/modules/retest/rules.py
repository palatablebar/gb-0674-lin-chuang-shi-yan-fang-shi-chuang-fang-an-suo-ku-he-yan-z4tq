from app.coerce import instant
from collections import defaultdict

def adjudicate(rows,context):
    by_id={r['id']:r for r in rows};children=defaultdict(list);issues=[];selected=[]
    for row in rows:
        if row['kind']!='RETEST':continue
        parent=by_id.get(row['parent'])
        if parent is None or parent['kind']!='PRIMARY' or any(parent[k]!=row[k] for k in ('subject','visit')):
            issues.append({'id':row['id'],'code':'RETEST_REFERENCE','parent':row['parent']});continue
        hours=(instant(row['at'])-instant(parent['at'])).total_seconds()/3600
        if not 0<hours<=context['retest_hours'] or row['revision']<=parent['revision']:
            issues.append({'id':row['id'],'code':'RETEST_WINDOW','parent':row['parent']});continue
        children[parent['id']].append(row)
    for row in rows:
        if row['kind']!='PRIMARY':continue
        candidates=children[row['id']]
        if candidates:
            max_revision=max(r['revision'] for r in candidates);winners=[r for r in candidates if r['revision']==max_revision]
            if len(winners)>1:issues.append({'id':row['id'],'code':'RETEST_VERSION_CONFLICT','parent':row['id']});winner=row
            else:winner=winners[0]
        else:winner=row
        selected.append({'id':winner['id'],'subject':row['subject'],'visit':row['visit'],'primary_id':row['id'],'value_mg_dl':winner['value_mg_dl'],'revision':winner['revision'],'code':'RETEST_SELECTED' if winner is not row else 'PRIMARY_SELECTED'})
    return selected,issues

def apply(state):
    selected,issues=adjudicate(state['records'],state['context']);state.update(selected_results=selected,retest_issues=issues)
    state['views']['retest']={'title':'复检裁决','rows':selected+issues,'metrics':{'有效结果':len(selected),'采用复检':sum(r['code']=='RETEST_SELECTED' for r in selected),'复检问题':len(issues)}}
