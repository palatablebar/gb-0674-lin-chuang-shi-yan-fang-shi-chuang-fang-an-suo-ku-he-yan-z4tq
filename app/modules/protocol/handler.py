from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/protocol')
def page(request:Request):
    return render(request,'protocol')
@router.post('/api/protocol')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=2)
