from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/windows')
def page(request:Request):
    return render(request,'windows')
@router.post('/api/windows')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=4)
