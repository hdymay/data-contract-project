"""
계약서 분류 API
"""
from fastapi import APIRouter, HTTPException
from services.classification_agent import ClassificationAgent
from models.schemas import ClassificationRequest, ClassificationResponse

router = APIRouter()

@router.post("/classify", response_model=ClassificationResponse)
async def classify_contract(request: ClassificationRequest):
    """계약서 유형 분류"""
    try:
        # 분류 에이전트
        agent = ClassificationAgent()
        result = await agent.classify_contract(
            contract_text=request.contract_text,
            contract_id=request.contract_id
        )
        
        return ClassificationResponse(
            contract_id=request.contract_id,
            predicted_type=result.get("predicted_type"),
            confidence=result.get("confidence"),
            reasoning=result.get("reasoning")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
