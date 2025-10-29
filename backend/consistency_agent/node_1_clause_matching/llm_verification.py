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

목적은 "사용자 계약서에 표준 계약서의 이 내용이 다뤄지고 있는가?"를 확인하는 것입니다.
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
    
    def verify_clause_match_batch(
        self,
        user_clause: ClauseData,
        standard_candidates: List[tuple],  # [(ClauseData, similarity), ...]
        min_confidence: float = 0.5
    ) -> List[VerificationDecision]:
        """
        한 사용자 조문에 대해 여러 표준 후보를 한 번에 검증 (배치 처리)
        
        Args:
            user_clause: 사용자 계약서 조문
            standard_candidates: [(표준 조문, 유사도), ...] 리스트
            min_confidence: 최소 신뢰도
            
        Returns:
            List[VerificationDecision]: 각 후보에 대한 검증 결과
        """
        if not standard_candidates:
            return []
        
        user_text = user_clause.text_norm or user_clause.text
        
        # 후보 조문들 텍스트 구성
        candidates_text = ""
        for i, (candidate, similarity) in enumerate(standard_candidates, 1):
            std_text = candidate.text_norm or candidate.text
            candidates_text += f"""
**후보 {i}: {candidate.id}** (FAISS 유사도: {similarity:.2f})
{std_text}

"""
        
        prompt = f"""당신은 계약서 조문의 **의미적 유사성**을 판단하는 전문가입니다.

**사용자 조문 ({user_clause.id}):**
{user_text}

**표준 계약서 후보 조문들:**
{candidates_text}

각 표준 후보 조문이 사용자 조문과 **의미적으로 유사**한지 판단하세요.

**판단 기준:**
- 같은 주제/내용을 다루는가?
- 표현이 달라도 의미가 비슷한가?
- 법적 효력 차이는 무시 (주제 중심 판단)
- **여러 후보가 유사할 수 있음** (사용자 조문이 여러 표준 조문의 내용을 포함할 수 있음)

다음 JSON 형식으로 응답하세요 (모든 후보 포함):
{{
    "results": [
        {{
            "candidate_id": "후보 1 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "reasoning": "판단 근거 (2-3문장)"
        }},
        {{
            "candidate_id": "후보 2 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "reasoning": "판단 근거 (2-3문장)"
        }}
    ]
}}

JSON만 응답하세요."""

        try:
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
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result_json = json.loads(response.choices[0].message.content.strip())
            
            # 결과를 VerificationDecision 리스트로 변환
            decisions = []
            for result in result_json.get('results', []):
                decisions.append(VerificationDecision(
                    is_match=result.get('is_match', False),
                    confidence=float(result.get('confidence', 0.0)),
                    reasoning=result.get('reasoning', '')
                ))
            
            logger.debug(
                f"Batch verification: {user_clause.id} with {len(standard_candidates)} candidates, "
                f"matched: {sum(1 for d in decisions if d.is_match)}"
            )
            
            return decisions
            
        except Exception as e:
            logger.error(f"Error during batch LLM verification: {e}")
            # 에러 시 모든 후보를 불일치로 반환
            return [
                VerificationDecision(
                    is_match=False,
                    confidence=0.0,
                    reasoning=f"검증 중 오류 발생: {str(e)}"
                )
                for _ in standard_candidates
            ]
    
    def batch_verify(
        self, 
        pairs: List[Tuple[ClauseData, ClauseData]]
    ) -> List[VerificationDecision]:
        """
        여러 조문 쌍을 배치로 검증 (레거시)
        
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
        
        retur
    
    def verify_missing_clause_forward_batch(
        self,
        standard_clause: ClauseData,
        user_candidates: List[tuple]  # [(ClauseData, similarity), ...]
    ) -> dict:
        """
        누락된 표준 조문을 Top-3 후보와 한 번에 비교 (배치 정방향 검증)
        
        Args:
            standard_clause: 누락된 표준 계약서 조문
            user_candidates: [(사용자 조문, 유사도), ...] 리스트 (Top-3)
            
        Returns:
            dict: {
                'candidates': [각 후보별 판단 결과],
                'summary': 종합 분석 텍스트
            }
        """
        standard_text = standard_clause.text_norm or standard_clause.text
        
        # 후보 조문들 텍스트 구성
        candidates_text = ""
        for i, (candidate, similarity) in enumerate(user_candidates, 1):
            user_text = candidate.text_norm or candidate.text
            candidates_text += f"""
**후보 {i}: {candidate.id}** (FAISS 유사도: {similarity:.2f})
{user_text}

"""
        
        prompt = f"""당신은 계약서 조문 분석 및 리스크 평가 전문가입니다.

**분석 대상:**
표준 계약서의 "{standard_clause.id} ({standard_clause.title})" 조문이 사용자 계약서에서 누락되었습니다.
이 조문과 가장 유사한 사용자 계약서 조문 Top-3를 찾았습니다.
각 후보가 표준 조문의 내용을 포함하고 있는지 분석해주세요.

**표준 조문 ({standard_clause.id}):**
{standard_text}

**사용자 계약서 후보 조문 (Top-3):**
{candidates_text}

---

### 💡 **판단 지침**
1. **부분 일치(표현 차이형)** – 핵심 의미는 같지만 일부 조건·절차·의무가 누락되거나 표현이 다름  
   (예: '하여야 한다' → '할 수 있다', '사전 통지 및 서면 동의' 중 일부만 포함)
2. **무관** – 의미적으로 관련 없음
3. 반드시 Top-3 후보 모두에 대해 판단하고, 표준의 핵심요소 중 어떤 부분이 포함/누락되었는지,  
   그로 인한 잠재적 리스크(법적·운영적)를 함께 설명할 것.
4. confidence: 0.0~1.0 (0.6 ↑ = 의미 유사, 0.3 ~ 0.6 = 부분 유사 / 표현 차이형, 0.3 ↓ = 무관)

---

### **분석 요청**
각 후보 조문을 표준 조문과 비교하여 자연스러운 문단 형식으로 분석해주세요.

**작성 가이드:**
1. **근거(reasoning)**: 
   - **반드시 후보 조문의 실제 내용을 직접 인용**하여 비교하세요
   - 표준 조문의 핵심 요소(의무, 조건, 절차 등)를 파악하고, 각 후보가 이를 얼마나 포함하는지 서술
   - 예시: "후보 조문은 '데이터 제공 범위는 별도 협의'라고 명시하고 있어, 표준의 '별지1에 기재' 방식과 유사하나..."
   - 누락된 부분이 있다면 구체적으로 명시 (2-3문장의 연결된 문단)

2. **위험(risk)**: "이 조항이 없으면..." 형식의 시나리오로 작성하세요. 계약 체결·이행·분쟁 시 발생할 수 있는 구체적인 문제 상황을 설명하세요. (1-2문장의 자연스러운 서술)

3. **종합 분석(summary)**: 
   - Top-3 후보를 종합적으로 검토한 결과를 문단으로 작성
   - **각 후보의 핵심 내용을 간략히 인용**하면서 비교
   - 왜 이 표준 조문이 누락으로 판단되었는지 자연스럽게 설명 (3-5문장의 연결된 문단)

4. **전체 위험(overall_risk)**: "이 조항이 없으면..." 형식으로 시작하여, 계약서 전체 관점에서 발생할 수 있는 법적·운영적 위험을 시나리오 형식으로 서술하세요. (2-3문장의 자연스러운 문단)

5. **권고(recommendation)**: 각 후보별 분석 결과를 바탕으로 "~을 추가할 것을 권장합니다" 형식으로 끝나는 권고사항을 작성하세요. (1-2문장)

다음 JSON 형식으로 응답하세요 (Top-3 후보 모두 포함):
{{
    "candidates": [
        {{
            "candidate_id": "후보 조문 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이형)" | "무관",
            "reasoning": "후보 조문의 실제 내용을 직접 인용하며 표준 조문과 비교. 예: '후보는 \"[실제 문구]\"라고 명시하여...' 형식으로 작성 (2-3문장)",
            "risk": "이 조항이 없으면 [구체적 문제 상황]이 발생할 수 있습니다. [추가 위험 설명] (1-2문장)",
            "recommendation": "구체적 권고사항을 서술하고 '~을 추가할 것을 권장합니다'로 마무리 (1-2문장)"
        }},
        {{
            "candidate_id": "후보 2 조문 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이형)" | "무관",
            "reasoning": "후보 조문 내용을 직접 인용하며 비교 (2-3문장)",
            "risk": "이 조항이 없으면... 시나리오 (1-2문장)",
            "recommendation": "~을 추가할 것을 권장합니다 (1-2문장)"
        }},
        {{
            "candidate_id": "후보 3 조문 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이형)" | "무관",
            "reasoning": "후보 조문 내용을 직접 인용하며 비교 (2-3문장)",
            "risk": "이 조항이 없으면... 시나리오 (1-2문장)",
            "recommendation": "~을 추가할 것을 권장합니다 (1-2문장)"
        }}
    ],
    "summary": "Top-3 후보의 핵심 내용을 간략히 인용하며 종합 비교. 왜 이 표준 조문이 누락으로 판단되었는지 설명 (3-5문장의 연결된 문단)",
    "overall_risk": "이 조항이 없으면 [구체적 시나리오]가 발생할 수 있습니다. 계약 체결·이행·분쟁 시 어떤 문제가 생길 수 있는지 자연스럽게 서술 (2-3문장의 연결된 문단)"
}}

JSON만 응답하세요."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 계약서 조문을 정확하게 비교 분석하는 법률 전문가입니다. JSON 형식으로만 응답하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result_json = json.loads(response.choices[0].message.content.strip())
            
            logger.debug(
                f"Batch forward verification: {standard_clause.id} with {len(user_candidates)} candidates"
            )
            
            return result_json
            
        except Exception as e:
            logger.error(f"Error during batch forward LLM verification: {e}")
            # 에러 시 기본 응답
            return {
                'candidates': [
                    {
                        'candidate_id': cand[0].id,
                        'is_match': False,
                        'confidence': 0.0,
                        'match_type': '무관',
                        'reasoning': f'검증 중 오류 발생: {str(e)}'
                    }
                    for cand in user_candidates
                ],
                'summary': f'검증 중 오류가 발생했습니다: {str(e)}'
            }
    
    def verify_missing_clause_forward(
        self,
        standard_clause: ClauseData,
        user_candidate: ClauseData
    ) -> VerificationDecision:
        """
        누락된 표준 조문이 사용자 조문에 포함되어 있는지 검증 (정방향) - 레거시
        
        Args:
            standard_clause: 누락된 표준 계약서 조문
            user_candidate: 사용자 계약서 후보 조문
            
        Returns:
            VerificationDecision: 검증 결과
        """
        standard_text = standard_clause.text_norm or standard_clause.text
        user_text = user_candidate.text_norm or user_candidate.text
        
        prompt = f"""당신은 계약서 조문 분석 전문가입니다.

**질문:** 표준 조문 "{standard_clause.id}"의 의미와 동일하거나 부분적으로 포함된 내용이 사용자 조문에 있는가?

**표준 조문 ({standard_clause.id}):**
{standard_text}

**사용자 조문 ({user_candidate.id}):**
{user_text}

**판단 기준:**
1. **완전 일치**: 사용자 조문이 표준 조문의 의미를 완전히 포함
2. **부분 일치**: 사용자 조문이 표준 조문의 일부 내용만 포함 (표현 차이 포함)
3. **무관**: 사용자 조문이 표준 조문과 의미적으로 관련 없음

다음 JSON 형식으로 응답하세요:
{{
    "is_match": true (완전/부분 일치) 또는 false (무관),
    "confidence": 0.0~1.0 사이의 신뢰도,
    "reasoning": "판단 근거를 명확히 풍부하게 설명 (왜 일치/불일치인지, 어떤 부분이 유사/다른지)"
}}

JSON만 응답하세요."""

        try:
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
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = self._parse_llm_response(response)
            
            logger.debug(
                f"Forward verification: {standard_clause.id} -> {user_candidate.id}: "
                f"match={result.is_match}, confidence={result.confidence:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error during forward LLM verification: {e}")
            return VerificationDecision(
                is_match=False,
                confidence=0.0,
                reasoning=f"검증 중 오류 발생: {str(e)}"
            )
    
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
