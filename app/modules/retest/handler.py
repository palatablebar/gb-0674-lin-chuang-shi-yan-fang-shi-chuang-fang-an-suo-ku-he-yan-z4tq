from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/retest')
def page(request:Request):
    return render(request,'retest')
@router.post('/api/retest')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=6)
