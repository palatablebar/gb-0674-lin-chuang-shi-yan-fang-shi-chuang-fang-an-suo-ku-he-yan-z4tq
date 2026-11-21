from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/ranges')
def page(request:Request):
    return render(request,'ranges')
@router.post('/api/ranges')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=3)
