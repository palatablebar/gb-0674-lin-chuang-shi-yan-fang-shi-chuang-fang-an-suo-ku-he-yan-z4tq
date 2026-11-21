import hashlib,json

def freeze(state):
    basis={'selected':state['selected_results'],'windows':state['windows'],'deviations':state['deviations']}
    return {'status':'可冻结' if state['balance']['status']=='可锁库' else '待处理','seal':hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest(),'subjects':len(state['context']['subjects']),'results':len(state['selected_results'])}
def apply(state):
    state['archive']=freeze(state);state['views']['archive']={'title':'冻结清单','rows':state['selected_results'],'metrics':{'受试者':state['archive']['subjects'],'结果':state['archive']['results'],'状态':state['archive']['status']}}
