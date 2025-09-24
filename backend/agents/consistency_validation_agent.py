"""
정합성 검증 에이전트
"""
from celery import Celery
from agents.nodes.required_presence_node import RequiredPresenceNode
from agents.nodes.checklist_node import ChecklistNode
from agents.nodes.completeness_node import CompletenessNode
from agents.nodes.context_logic_node import ContextLogicNode

app = Celery('consistency_validation_worker')

class ConsistencyValidationAgent:
    """정합성 검증 에이전트"""
    
    def __init__(self):
        self.nodes = {
            'A1': RequiredPresenceNode(),
            'A2': ChecklistNode(),
            'A3': CompletenessNode(),
            'A4': ContextLogicNode()
        }
    
    async def validate_contract(self, contract_data: dict, contract_id: str):
        """4개 노드로 계약서 검증"""
        try:
            results = {}
            
            # A1: 필수 조항 존재 여부
            results['A1'] = await self.nodes['A1'].validate(contract_data)
            
            # A2: 체크리스트 기반 검증
            results['A2'] = await self.nodes['A2'].validate(contract_data)
            
            # A3: 내용 충실도 검증
            results['A3'] = await self.nodes['A3'].validate(contract_data)
            
            # A4: 맥락 및 논리 조건 검증
            results['A4'] = await self.nodes['A4'].validate(contract_data)
            
            return {
                "contract_id": contract_id,
                "validation_results": results,
                "status": "completed"
            }
            
        except Exception as e:
            return {
                "contract_id": contract_id,
                "error": str(e),
                "status": "failed"
            }

@app.task
def validate_contract(contract_data: dict, contract_id: str):
    """정합성 검증 에이전트 메인 작업"""
    agent = ConsistencyValidationAgent()
    return agent.validate_contract(contract_data, contract_id)
