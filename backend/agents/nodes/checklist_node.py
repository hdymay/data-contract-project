"""
A2. Checklist Node
"""
from typing import Dict, Any
from services.search_service import SearchService
from services.llm_service import LLMService

class ChecklistNode:
    """체크리스트 기반 검증 노드"""
    
    def __init__(self):
        self.search_service = SearchService()
        self.llm_service = LLMService()
    
    async def validate(self, contract_data: dict) -> Dict[str, Any]:
        """체크리스트 기반 검증"""
        try:
            # 계약 유형별 체크리스트 조회
            checklist = await self.search_service.search_checklist(
                contract_type=contract_data.get("contract_type")
            )
            
            # 각 체크리스트 항목 검증
            checklist_results = {}
            for item in checklist:
                checklist_results[item["id"]] = await self._validate_checklist_item(
                    contract_data["text"], item
                )
            
            # LLM으로 추가 검증
            llm_result = await self.llm_service.validate_checklist(
                contract_data["text"], checklist
            )
            
            return {
                "node": "A2_Checklist",
                "checklist_results": checklist_results,
                "llm_validation": llm_result,
                "score": self._calculate_score(checklist_results),
                "status": "completed"
            }
            
        except Exception as e:
            return {
                "node": "A2_Checklist",
                "error": str(e),
                "status": "failed"
            }
    
    async def _validate_checklist_item(self, contract_text: str, item: dict) -> bool:
        """체크리스트 항목 검증"""
        # TODO: 구현
        pass
    
    def _calculate_score(self, checklist_results: Dict[str, bool]) -> float:
        """점수 계산"""
        total_items = len(checklist_results)
        passed_items = sum(1 for passed in checklist_results.values() if passed)
        return (passed_items / total_items) * 100
