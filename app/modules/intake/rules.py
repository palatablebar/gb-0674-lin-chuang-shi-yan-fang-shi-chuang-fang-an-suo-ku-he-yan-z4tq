from .reader import read_source
FIELDS=['id', 'subject', 'visit', 'at', 'enrolled', 'kind', 'parent', 'value', 'unit', 'protocol', 'revision']
def apply(state):read_source(state,FIELDS,{'编号':'id'})
