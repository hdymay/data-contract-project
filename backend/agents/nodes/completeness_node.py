"""
A3. Completeness Node
"""
from typing import Dict, Any
from services.search_service import SearchService
from services.llm_service import LLMService

class CompletenessNode:
    """내용 충실도 검증 노드"""
    
    def __init__(self):
        self.search_service = SearchService()
        self.llm_service = LLMService()
    
    async def validate(self, contract_data: dict) -> Dict[str, Any]:
        """내용 충실도 검증"""
        try:
            # 표준계약서 해설 조회
            standard_explanations = await self.search_service.search_explanations(
                contract_type=contract_data.get("contract_type")
            )
            
            # 각 조항별 충실도 검증
            completeness_results = {}
            for explanation in standard_explanations:
                completeness_results[explanation["clause_id"]] = await self._validate_completeness(
                    contract_data["text"], explanation
                )
            
            # LLM으로 추가 검증
            llm_result = await self.llm_service.validate_completeness(
                contract_data["text"], standard_explanations
            )
            
            return {
                "node": "A3_Completeness",
                "completeness_results": completeness_results,
                "llm_validation": llm_result,
                "score": self._calculate_score(completeness_results),
                "status": "completed"
            }
            
        except Exception as e:
            return {
                "node": "A3_Completeness",
                "error": str(e),
                "status": "failed"
            }
    
    async def _validate_completeness(self, contract_text: str, explanation: dict) -> float:
        """특정 조항의 충실도 검증"""
        # TODO: 구현
        pass
    
    def _calculate_score(self, completeness_results: Dict[str, float]) -> float:
        """점수 계산"""
        if not completeness_results:
            return 0.0
        return sum(completeness_results.values()) / len(completeness_results)
