from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/deviation')
def page(request:Request):
    return render(request,'deviation')
@router.post('/api/deviation')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=5)
