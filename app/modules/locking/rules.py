def decide(state):
    c=state['counts'];explained=len(state['records'])+len(state['quarantine'])+c['blank']+c['duplicate']+c['repeated_header']
    range_blocks=len(state.get('range_blocks',[]))
    blocked=len(state['deviations'])+len(state['retest_issues'])+len(state['quarantine'])+range_blocks
    return {'input':c['input'],'accepted':len(state['records']),'quarantined':len(state['quarantine']),'row_balanced':c['input']==explained,'completed':len(state['completed']),'expected':len(state['context']['subjects'])*len(state['context']['required_visits']),'deviations':len(state['deviations']),'retest_issues':len(state['retest_issues']),'range_blocks':range_blocks,'blocked':blocked,'status':'可锁库' if not blocked and c['input']==explained else '待处理'}
def apply(state):
    state['balance']=decide(state);state['views']['locking']={'title':'锁库闸门','rows':[state['balance']],'metrics':{'应访视':state['balance']['expected'],'已完成':state['balance']['completed'],'阻断项':state['balance']['blocked'],'范围阻断':state['balance']['range_blocks']}}
