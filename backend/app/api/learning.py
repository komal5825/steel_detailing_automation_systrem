from fastapi import APIRouter

router = APIRouter()

@router.get("/rules")
async def get_proposed_rules():
    return {"rules": []}

@router.post("/suggest")
async def suggest_rule(suggestion: dict):
    return {"status": "received", "suggestion": suggestion}
