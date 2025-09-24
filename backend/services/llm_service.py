"""
LLM 서비스
"""
from typing import Dict, Any, List
import openai
from core.config import settings

class LLMService:
    """LLM 서비스"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4"
    
    async def classify_contract(self, contract_text: str, relevant_docs: List[Dict]) -> Dict[str, Any]:
        """계약서 분류"""
        try:
            prompt = self._build_classification_prompt(contract_text, relevant_docs)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            return self._parse_classification_response(response.choices[0].message.content)
            
        except Exception as e:
            raise Exception(f"계약서 분류 실패: {e}")
    
    async def validate_required_presence(self, contract_text: str, standard_clauses: List[Dict]) -> Dict[str, Any]:
        """필수 조항 존재 여부 검증"""
        try:
            prompt = self._build_validation_prompt(contract_text, standard_clauses)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            return self._parse_validation_response(response.choices[0].message.content)
            
        except Exception as e:
            raise Exception(f"필수 조항 검증 실패: {e}")
    
    def _build_classification_prompt(self, contract_text: str, relevant_docs: List[Dict]) -> str:
        """분류 프롬프트 구성"""
        # TODO: 프롬프트 구성 로직
        pass
    
    def _build_validation_prompt(self, contract_text: str, standard_clauses: List[Dict]) -> str:
        """검증 프롬프트 구성"""
        # TODO: 프롬프트 구성 로직
        pass
    
    def _parse_classification_response(self, response: str) -> Dict[str, Any]:
        """분류 응답 파싱"""
        # TODO: 응답 파싱 로직
        pass
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """검증 응답 파싱"""
        # TODO: 응답 파싱 로직
        pass
