"""
A1. Required Presence Node
"""
from typing import Dict, Any
from services.search_service import SearchService
from services.llm_service import LLMService

class RequiredPresenceNode:
    """필수 조항 존재 여부 검증 노드"""
    
    def __init__(self):
        self.search_service = SearchService()
        self.llm_service = LLMService()
        self.required_clauses = [
            "계약 당사자",
            "계약 목적",
            "계약 기간",
            "계약 금액",
            "손해배상 조항",
            "계약 해지 조건"
        ]
    
    async def validate(self, contract_data: dict) -> Dict[str, Any]:
        """필수 조항 존재 여부 검증"""
        try:
            # 표준계약서에서 필수 조항 조회
            standard_clauses = await self.search_service.search_required_clauses(
                contract_type=contract_data.get("contract_type")
            )
            
            # 각 조항 존재 여부 확인
            presence_results = {}
            for clause in self.required_clauses:
                presence_results[clause] = await self._check_clause_presence(
                    contract_data["text"], clause
                )
            
            # LLM으로 추가 검증
            llm_result = await self.llm_service.validate_required_presence(
                contract_data["text"], standard_clauses
            )
            
            return {
                "node": "A1_RequiredPresence",
                "presence_results": presence_results,
                "llm_validation": llm_result,
                "score": self._calculate_score(presence_results),
                "status": "completed"
            }
            
        except Exception as e:
            return {
                "node": "A1_RequiredPresence",
                "error": str(e),
                "status": "failed"
            }
    
    async def _check_clause_presence(self, contract_text: str, clause: str) -> bool:
        """특정 조항 존재 여부 확인"""
        # TODO: 구현
        pass
    
    def _calculate_score(self, presence_results: Dict[str, bool]) -> float:
        """점수 계산"""
        total_clauses = len(presence_results)
        present_clauses = sum(1 for present in presence_results.values() if present)
        return (present_clauses / total_clauses) * 100
