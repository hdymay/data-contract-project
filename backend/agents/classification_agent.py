"""
분류 에이전트
"""
from celery import Celery
from services.search_service import SearchService
from services.llm_service import LLMService

app = Celery('classification_worker')

@app.task
def classify_contract(contract_text: str, contract_id: str):
    """계약서 유형 분류"""
    try:
        # 검색 서비스
        search_service = SearchService()
        relevant_docs = search_service.search(
            query=contract_text,
            top_k=10,
            doc_types=["standard_contract", "guide"]
        )
        
        # LLM 서비스
        llm_service = LLMService()
        result = llm_service.classify_contract(contract_text, relevant_docs)
        
        return {
            "contract_id": contract_id,
            "predicted_type": result["contract_type"],
            "confidence": result["confidence"],
            "reasoning": result["reasoning"],
            "status": "completed"
        }
        
    except Exception as e:
        return {
            "contract_id": contract_id,
            "error": str(e),
            "status": "failed"
        }
