"""
LLM Verification Service for Contract Clause Matching

This module provides LLM-based semantic verification to determine if two clauses
are semantically equivalent, even if they use different wording.
"""

import json
import logging
from typing import List, Tuple, Optional
from openai import AzureOpenAI

try:
    from backend.consistency_agent.node_1_clause_matching.models import ClauseData, VerificationDecision
    from backend.consistency_agent.node_1_clause_matching.config import config
except ImportError:
    from .models import ClauseData, VerificationDecision
    from .config import config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)


class LLMVerificationService:
    """
    LLM을 사용하여 조문의 의미론적 일치 여부를 검증하는 서비스
    
    Azure OpenAI의 GPT-4o 모델을 사용하여 표준 계약서 조문과 
    사용자 계약서 조문이 의미적으로 동일한지 판단합니다.
    """
    
    # 프롬프트 템플릿
    VERIFICATION_PROMPT_TEMPLATE = """당신은 계약서 조문의 **의미적 유사성**을 판단하는 전문가입니다. 
두 개의 계약서 항(clause)이 **비슷한 내용**을 다루고 있는지 판단해야 합니다.

**핵심 평가 기준: 의미적 유사성 (Semantic Similarity)**

Node1의 목적은 "사용자 계약서에 표준 계약서의 이 내용이 다뤄지고 있는가?"를 확인하는 것입니다.
법적 효력의 차이는 나중 단계에서 판단하므로, 여기서는 **주제와 의미가 유사한지**만 판단하세요.

**판단 예시:**

✅ **유사함 (일치):**
- 표준: "데이터 제공 범위는 별지1에 기재" ↔ 사용자: "제공 데이터는 별도 합의된 범위" 
  → 둘 다 "데이터 범위 정의"를 다룸
  
- 표준: "품질을 보증한다" ↔ 사용자: "품질 유지를 위해 노력한다"
  → 둘 다 "데이터 품질"을 다룸 (표현은 다르지만 주제 동일)
  
- 표준: "불가항력 시 책임 면제" ↔ 사용자: "천재지변 시 책임 없음"
  → 둘 다 "불가항력 면책"을 다룸

❌ **유사하지 않음 (불일치):**
- 표준: "금융기관 거래정지 시 해지" ↔ 사용자: "지급 불이행 시 해지"
  → 둘 다 "해지"지만 해지 사유가 완전히 다름
  
- 표준: "데이터 제공자의 권리 보증" ↔ 사용자: "데이터 이용자의 의무"
  → 주체가 다르고 내용도 다름
  
- 표준: "개인정보 보호 의무" ↔ 사용자: "일반 데이터 보안 조치"
  → 개인정보 vs 일반 보안 (범위가 다름)

**평가 절차:**

1. **표준 항이 다루는 주제 파악**
   - 이 항은 무엇에 관한 내용인가?
   - 핵심 키워드: 데이터 범위? 대가 지급? 계약 해지? 책임 면제?

2. **사용자 항이 다루는 주제 파악**
   - 이 항은 무엇에 관한 내용인가?
   - 표준 항과 같은 주제를 다루는가?

3. **유사성 판단**
   - 두 항이 **같은 주제/내용**을 다루는가?
   - 표현이 달라도 **의미가 비슷**한가?

**중요 원칙:**
1. **주제 중심 판단** - "무엇에 관한 내용인가?"
2. **표현 차이 허용** - 문구가 달라도 의미가 비슷하면 일치
3. **법적 효력 차이는 무시** - "보증" vs "노력"도 둘 다 품질 관련이면 유사
4. **주제가 다르면 불일치** - 같은 카테고리여도 구체적 내용이 다르면 불일치

**표준 항 (Standard Clause):**
{standard_clause}

**사용자 항 (User Clause):**
{candidate_clause}

위 두 항이 **의미적으로 유사**한지 판단하고, 다음 JSON 형식으로 응답하세요:

{{
    "is_match": true 또는 false,
    "confidence": 0.0에서 1.0 사이의 신뢰도 점수,
    "reasoning": "두 항이 다루는 주제를 각각 설명하고, 유사/불일치 판단 근거를 명확히 제시"
}}

JSON만 응답하세요."""

    def __init__(self, model: str = None, api_version: str = "2024-02-15-preview"):
        """
        LLM 검증 서비스 초기화
        
        Args:
            model: 사용할 모델 이름 (기본값: config.AZURE_LLM_DEPLOYMENT)
            api_version: Azure OpenAI API 버전
        """
        self.model = model or config.AZURE_LLM_DEPLOYMENT
        self.api_version = api_version
        
        # Azure OpenAI 클라이언트 초기화
        try:
            config.validate()
            self.client = AzureOpenAI(
                api_key=config.AZURE_OPENAI_API_KEY,
                api_version=self.api_version,
                azure_endpoint=config.AZURE_ENDPOINT
            )
            logger.info(f"LLM Verification Service initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise
    
    def verify_clause_match(
        self, 
        standard_clause: ClauseData, 
        candidate_clause: ClauseData
    ) -> VerificationDecision:
        """
        두 조문이 의미적으로 동일한지 LLM으로 검증
        
        Args:
            standard_clause: 표준 계약서 조문
            candidate_clause: 비교 대상 조문
            
        Returns:
            VerificationDecision: 검증 결과 (매칭 여부, 신뢰도, 근거)
        """
        try:
            # 프롬프트 생성
            prompt = self._create_verification_prompt(standard_clause, candidate_clause)
            
            # LLM 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 계약서 조문을 정확하게 비교하는 법률 전문가입니다. JSON 형식으로만 응답하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # 일관성을 위해 낮은 temperature 사용
                max_tokens=500,
                response_format={"type": "json_object"}  # JSON 응답 강제
            )
            
            # 응답 파싱
            result = self._parse_llm_response(response)
            
            logger.debug(
                f"Verification result for clause {standard_clause.id}: "
                f"match={result.is_match}, confidence={result.confidence}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error during LLM verification: {e}")
            # 오류 발생 시 보수적으로 불일치로 판단
            return VerificationDecision(
                is_match=False,
                confidence=0.0,
                reasoning=f"검증 중 오류 발생: {str(e)}"
            )
    
    def batch_verify(
        self, 
        pairs: List[Tuple[ClauseData, ClauseData]]
    ) -> List[VerificationDecision]:
        """
        여러 조문 쌍을 배치로 검증
        
        Args:
            pairs: (표준 조문, 후보 조문) 튜플의 리스트
            
        Returns:
            List[VerificationDecision]: 각 쌍에 대한 검증 결과 리스트
        """
        results = []
        
        for i, (standard_clause, candidate_clause) in enumerate(pairs):
            logger.info(f"Verifying pair {i+1}/{len(pairs)}")
            result = self.verify_clause_match(standard_clause, candidate_clause)
            results.append(result)
        
        return results
    
    def explain_mismatch(
        self, 
        standard_clause: ClauseData, 
        candidate_clause: ClauseData
    ) -> str:
        """
        불일치 이유를 상세히 설명
        
        Args:
            standard_clause: 표준 계약서 조문
            candidate_clause: 비교 대상 조문
            
        Returns:
            str: 불일치 이유 설명
        """
        # 세그먼트 기법 적용: text_norm 사용
        standard_text = standard_clause.text_norm or standard_clause.text
        candidate_text = candidate_clause.text_norm or candidate_clause.text
        
        prompt = f"""다음 두 계약서 조문이 왜 다른지 상세히 설명해주세요:

**표준 조문:**
{standard_text}

**비교 대상 조문:**
{candidate_text}

차이점을 구체적으로 설명하고, 어떤 부분이 누락되었거나 변경되었는지 명확히 해주세요."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 계약서 조문의 차이점을 명확하게 설명하는 법률 전문가입니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            explanation = response.choices[0].message.content.strip()
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating mismatch explanation: {e}")
            return f"설명 생성 중 오류 발생: {str(e)}"
    
    def _create_verification_prompt(
        self, 
        standard_clause: ClauseData, 
        candidate_clause: ClauseData
    ) -> str:
        """
        검증용 프롬프트 생성
        
        Args:
            standard_clause: 표준 계약서 조문
            candidate_clause: 비교 대상 조문
            
        Returns:
            str: 생성된 프롬프트
        """
        # 세그먼트 기법 적용: text_norm 사용 (// 구분자 포함)
        standard_text = standard_clause.text_norm or standard_clause.text
        candidate_text = candidate_clause.text_norm or candidate_clause.text
        
        # 별지 참조 감지 및 처리
        if "[별지" in standard_text:
            appendix_note = "\n\n**참고:** 이 조문은 별지를 참조합니다. 별지는 사용자가 작성해야 하는 양식이므로, 사용자 조문에 해당 내용이나 형식이 있는지 확인하세요. 별지 참조가 있다는 것만으로도 부분적으로 일치할 수 있습니다."
            standard_text += appendix_note
        
        return self.VERIFICATION_PROMPT_TEMPLATE.format(
            standard_clause=standard_text,
            candidate_clause=candidate_text
        )
    
    def _parse_llm_response(self, response) -> VerificationDecision:
        """
        LLM 응답을 파싱하여 VerificationDecision 객체 생성
        
        Args:
            response: Azure OpenAI API 응답
            
        Returns:
            VerificationDecision: 파싱된 검증 결과
        """
        try:
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            result_dict = json.loads(content)
            
            # VerificationDecision 객체 생성
            decision = VerificationDecision(
                is_match=result_dict.get("is_match", False),
                confidence=float(result_dict.get("confidence", 0.0)),
                reasoning=result_dict.get("reasoning", "")
            )
            
            return decision
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            # JSON 파싱 실패 시 보수적으로 불일치로 판단
            return VerificationDecision(
                is_match=False,
                confidence=0.0,
                reasoning=f"응답 파싱 실패: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return VerificationDecision(
                is_match=False,
                confidence=0.0,
                reasoning=f"응답 처리 중 오류: {str(e)}"
            )
