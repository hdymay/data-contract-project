"""
MatchingVerifier - LLM 기반 조항 매칭 검증

검색 엔진으로 추출된 후보 조항들 중 실제로 매칭되는 조항을 LLM으로 검증
"""

import logging
from typing import Dict, Any, List, Optional
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class MatchingVerifier:
    """
    LLM 기반 매칭 검증기

    주요 기능:
    1. 후보 조항들 중 실제 관련있는 조항 선택 (LLM)
    2. 선택된 조항들에 대한 매칭 여부 최종 검증 (LLM)
    """

    def __init__(self, azure_client: AzureOpenAI, model: str = "gpt-4o"):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
            model: 사용할 모델명 (기본: gpt-4o)
        """
        self.azure_client = azure_client
        self.model = model

        logger.info(f"MatchingVerifier 초기화 완료 (model={model})")

    def verify_matching(
        self,
        user_article: Dict[str, Any],
        candidate_articles: List[Dict[str, Any]],
        contract_type: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        후보 조항들에 대한 매칭 검증

        Args:
            user_article: 사용자 조항 (content 배열 포함)
            candidate_articles: 후보 표준계약서 조항 목록 (조 단위 집계 결과)
                [
                    {
                        'parent_id': str,
                        'title': str,
                        'score': float,
                        'matched_sub_items': List[int],
                        'num_sub_items': int,
                        'matched_chunks': List[Dict]
                    },
                    ...
                ]
            contract_type: 계약 유형
            top_k: 최종 선택할 조항 개수 (기본: 5)

        Returns:
            {
                "matched": bool,
                "selected_articles": List[str],  # 매칭된 조항 ID들
                "verification_details": List[Dict],  # 각 조항별 검증 상세
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int
            }
        """
        if not candidate_articles:
            logger.warning(f"  후보 조항이 없습니다")
            return {
                "matched": False,
                "selected_articles": [],
                "verification_details": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        # Top-K 후보 선정
        top_candidates = candidate_articles[:top_k]

        logger.info(f"  매칭 검증 시작: 후보 {len(top_candidates)}개 조항")

        # 1단계: 관련 조항 선택
        selection_result = self._select_relevant_articles(
            user_article,
            top_candidates,
            contract_type
        )

        selected_article_ids = selection_result.get('selected_articles', [])

        if not selected_article_ids:
            logger.warning(f"  매칭 검증 실패: LLM이 관련 조항을 선택하지 못함")
            return {
                "matched": False,
                "selected_articles": [],
                "verification_details": [],
                "prompt_tokens": selection_result.get('prompt_tokens', 0),
                "completion_tokens": selection_result.get('completion_tokens', 0),
                "total_tokens": selection_result.get('prompt_tokens', 0) + selection_result.get('completion_tokens', 0)
            }

        logger.info(f"  매칭 검증 완료: {len(selected_article_ids)}개 조항 선택")

        return {
            "matched": True,
            "selected_articles": selected_article_ids,
            "verification_details": [],  # TODO: 필요시 상세 정보 추가
            "prompt_tokens": selection_result.get('prompt_tokens', 0),
            "completion_tokens": selection_result.get('completion_tokens', 0),
            "total_tokens": selection_result.get('prompt_tokens', 0) + selection_result.get('completion_tokens', 0)
        }

    def _select_relevant_articles(
        self,
        user_article: Dict[str, Any],
        candidate_articles: List[Dict[str, Any]],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        관련 표준 조항 선택 (LLM 활용)

        Args:
            user_article: 사용자 조항
            candidate_articles: 후보 표준계약서 조항들 (조 단위 집계 결과)
            contract_type: 계약 유형

        Returns:
            {
                "selected_articles": List[str],  # 선택된 조항 ID들
                "prompt_tokens": int,
                "completion_tokens": int
            }
        """
        # 사용자 조항 포맷팅
        user_text = self._format_user_article(user_article)

        # 후보 조항들 포맷팅
        candidates_text = ""
        for candidate in candidate_articles:
            parent_id = candidate['parent_id']
            title = candidate['title']
            score = candidate['score']
            num_sub_items = candidate['num_sub_items']

            # 해당 조의 청크들 포맷팅
            chunks = candidate.get('matched_chunks', [])
            chunk_lines = []
            for chunk_data in chunks:
                chunk = chunk_data.get('chunk', {})
                chunk_id = chunk.get('id', '')
                text_raw = chunk.get('text_raw', '').strip()
                if chunk_id and text_raw:
                    chunk_lines.append(f"  {chunk_id}: {text_raw}")

            candidates_text += f"{parent_id} ({title}) [유사도: {score:.3f}, 매칭 하위항목: {num_sub_items}개]\n"
            candidates_text += "\n".join(chunk_lines)
            candidates_text += "\n\n---\n\n"

        # 선택 프롬프트 생성
        prompt = self._build_selection_prompt(
            user_article_no=user_article.get('number'),
            user_article_title=user_article.get('title', ''),
            user_text=user_text,
            candidates_text=candidates_text,
            contract_type=contract_type
        )

        try:
            response = self.azure_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 데이터 계약서 전문가입니다. 사용자 조항과 실질적으로 관련있는 표준계약서 조항들을 선택합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )

            selection_text = response.choices[0].message.content.strip()
            usage = response.usage

            # 선택된 조항 ID 파싱
            selected_ids = self._parse_selection_response(selection_text, candidate_articles)

            logger.info(f"    LLM 조항 선택 완료: {len(selected_ids)}개 (토큰: {usage.total_tokens})")

            return {
                "selected_articles": selected_ids,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens
            }

        except Exception as e:
            logger.error(f"    조항 선택 실패: {e}")
            # 실패 시 모든 후보 반환
            all_ids = [candidate['parent_id'] for candidate in candidate_articles]
            return {
                "selected_articles": all_ids,
                "prompt_tokens": 0,
                "completion_tokens": 0
            }

    def _build_selection_prompt(
        self,
        user_article_no: int,
        user_article_title: str,
        user_text: str,
        candidates_text: str,
        contract_type: str
    ) -> str:
        """
        조항 선택 프롬프트 생성

        Args:
            user_article_no: 사용자 조항 번호
            user_article_title: 사용자 조항 제목
            user_text: 포맷팅된 사용자 조항
            candidates_text: 포맷팅된 후보 조항들
            contract_type: 계약 유형

        Returns:
            프롬프트 텍스트
        """
        contract_type_names = {
            "provide": "데이터 제공 계약",
            "create": "데이터 생성 계약",
            "process": "데이터 가공 계약",
            "brokerage_provider": "데이터 중개 계약 (제공자용)",
            "brokerage_user": "데이터 중개 계약 (이용자용)"
        }

        contract_name = contract_type_names.get(contract_type, contract_type)

        prompt = f"""# 관련 표준 조항 선택

## 계약 유형
{contract_name}

## 사용자 계약서 조항
제{user_article_no}조 ({user_article_title})
{user_text}

## 후보 표준계약서 조항들
아래 조항들은 사용자 조항과 연관되어 있을 가능성이 있는 표준계약서 조항들입니다.

{candidates_text}

---

**과제**: 위의 후보 조항들 중에서 사용자 계약서 조항(제{user_article_no}조)과 **실제로 관련있는** 표준계약서 조항들을 **모두**(1개 이상) 선택하세요.

**중요 사항**:
- 사용자 조항의 내용이 표준계약서 기준으로는 여러 조문에 걸쳐 있을 수 있습니다
- 관련있는 조항이라면 모두 선택해야 합니다
- 명확히 관련없는 조항, 또는 유사한듯 보이나 사실상 다른 맥락을 다루는 조항은 제외하세요

**응답 형식** (조항 ID만 나열):
선택된 조항: 제1조, 제3조, 제5조
"""

        return prompt

    def _parse_selection_response(
        self,
        response_text: str,
        candidate_articles: List[Dict[str, Any]]
    ) -> List[str]:
        """
        조항 선택 응답 파싱

        Args:
            response_text: LLM 응답 텍스트
            candidate_articles: 후보 조항 목록

        Returns:
            선택된 조항 ID 리스트
        """
        import re

        # 가능한 모든 조항 ID 추출
        available_ids = set()
        for candidate in candidate_articles:
            available_ids.add(candidate['parent_id'])

        # 응답에서 조항 ID 패턴 찾기 (제N조)
        pattern = r'제\d+조'
        found_ids = re.findall(pattern, response_text)

        # 실제 존재하는 ID만 필터링
        selected_ids = [id for id in found_ids if id in available_ids]

        # 중복 제거 및 순서 유지
        seen = set()
        result = []
        for id in selected_ids:
            if id not in seen:
                seen.add(id)
                result.append(id)

        # 아무것도 선택되지 않았으면 모든 후보 반환
        if not result:
            logger.warning(f"    응답에서 조항 ID를 파싱할 수 없음, 모든 후보 반환")
            result = list(available_ids)

        return result

    def _format_user_article(self, user_article: Dict[str, Any]) -> str:
        """
        사용자 조항 포맷팅

        text
        content[0]
        content[1]
        ...

        Args:
            user_article: 사용자 조항

        Returns:
            포맷팅된 텍스트
        """
        lines = []

        # text (조 본문)
        text = user_article.get('text', '').strip()
        if text:
            lines.append(text)

        # content 배열 (하위항목들)
        content_items = user_article.get('content', [])
        for item in content_items:
            if item.strip():
                lines.append(item.strip())

        return "\n".join(lines)

    def verify_missing_article_forward(
        self,
        standard_article: Dict[str, Any],
        user_candidates: List[Dict[str, Any]],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        누락 조문 역방향 검증 (표준 → 사용자)
        
        누락된 것으로 식별된 표준 조문이 실제로 사용자 계약서에 없는지 재확인
        
        Args:
            standard_article: 누락된 표준 조문
                {
                    'parent_id': str,
                    'title': str,
                    'chunks': List[Dict]
                }
            user_candidates: 유사한 사용자 조문 후보들
                [
                    {
                        'user_article': Dict,
                        'similarity': float,
                        'matched_chunks': List[Dict]
                    },
                    ...
                ]
            contract_type: 계약 유형
        
        Returns:
            {
                "is_truly_missing": bool,  # 실제로 누락되었는지
                "confidence": float,  # 신뢰도
                "matched_user_article": Dict or None,  # 매칭된 사용자 조문 (있다면)
                "reasoning": str,  # 판단 근거
                "recommendation": str,  # 권고사항
                "evidence": str,  # 상세 증거
                "risk_assessment": str,  # 위험도 평가
                "candidates_analysis": List[Dict],  # 후보별 분석
                "prompt_tokens": int,
                "completion_tokens": int
            }
        """
        parent_id = standard_article.get('parent_id')
        title = standard_article.get('title', '')
        
        logger.info(f"  누락 조문 재검증: {parent_id} ({title})")
        
        if not user_candidates:
            logger.warning(f"    후보 조문이 없습니다 - LLM으로 상세 분석 생성")
            # 후보가 없어도 LLM으로 상세한 누락 분석 생성
            return self._generate_missing_analysis_without_candidates(
                standard_article,
                contract_type
            )
        
        # 표준 조문 포맷팅
        standard_text = self._format_standard_article(standard_article)
        
        # 후보 조문들 포맷팅
        candidates_text = ""
        for i, candidate in enumerate(user_candidates, 1):
            user_article = candidate['user_article']
            similarity = candidate['similarity']
            user_no = user_article.get('number')
            user_title = user_article.get('title', '')
            user_text = self._format_user_article(user_article)
            
            candidates_text += f"**후보 {i}: 제{user_no}조 ({user_title})** (유사도: {similarity:.2f})\n"
            candidates_text += user_text
            candidates_text += "\n\n"
        
        # LLM 프롬프트 생성
        prompt = self._build_forward_verification_prompt(
            parent_id=parent_id,
            title=title,
            standard_text=standard_text,
            candidates_text=candidates_text,
            contract_type=contract_type
        )
        
        try:
            response = self.azure_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 계약서 조항을 정확하게 비교 분석하는 법률 전문가입니다. JSON 형식으로만 응답하세요."
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
            
            response_text = response.choices[0].message.content.strip()
            usage = response.usage
            
            # 응답 파싱
            result = self._parse_forward_verification_response(
                response_text,
                user_candidates,
                standard_article
            )
            
            result['prompt_tokens'] = usage.prompt_tokens
            result['completion_tokens'] = usage.completion_tokens
            
            logger.info(f"    재검증 완료: 누락={result['is_truly_missing']}, "
                       f"신뢰도={result['confidence']:.2f} (토큰: {usage.total_tokens})")
            
            return result
            
        except Exception as e:
            logger.error(f"    재검증 실패: {e}")
            return {
                "is_truly_missing": True,  # 실패 시 누락으로 간주
                "confidence": 0.5,
                "matched_user_article": None,
                "reasoning": f"검증 중 오류 발생: {str(e)}",
                "recommendation": f"'{title}' 조항 확인이 필요합니다.",
                "evidence": "LLM 검증 실패",
                "risk_assessment": "검증 실패로 인해 정확한 평가 불가",
                "candidates_analysis": [],
                "prompt_tokens": 0,
                "completion_tokens": 0
            }
    
    def _format_standard_article(self, standard_article: Dict[str, Any]) -> str:
        """
        표준 조문 포맷팅
        
        Args:
            standard_article: 표준 조문
                {
                    'parent_id': str,
                    'title': str,
                    'chunks': List[Dict]
                }
        
        Returns:
            포맷팅된 텍스트
        """
        chunks = standard_article.get('chunks', [])
        
        lines = []
        for chunk in chunks:
            text = chunk.get('text_raw', '').strip()
            if text:
                lines.append(text)
        
        return "\n".join(lines)
    
    def _build_forward_verification_prompt(
        self,
        parent_id: str,
        title: str,
        standard_text: str,
        candidates_text: str,
        contract_type: str
    ) -> str:
        """
        역방향 검증 프롬프트 생성 (A1 브랜치 스타일)
        
        Args:
            parent_id: 표준 조문 ID
            title: 표준 조문 제목
            standard_text: 표준 조문 내용
            candidates_text: 후보 사용자 조문들
            contract_type: 계약 유형
        
        Returns:
            프롬프트 텍스트
        """
        contract_type_names = {
            "provide": "데이터 제공 계약",
            "create": "데이터 생성 계약",
            "process": "데이터 가공 계약",
            "brokerage_provider": "데이터 중개 계약 (제공자용)",
            "brokerage_user": "데이터 중개 계약 (이용자용)"
        }
        
        contract_name = contract_type_names.get(contract_type, contract_type)
        
        prompt = f"""당신은 계약서 조항 분석 및 리스크 평가 전문가입니다.

**분석 대상**
표준 계약서의 "{parent_id} ({title})" 조항이 사용자 계약서에서 누락되었습니다.
해당 조항과 가장 유사한 사용자 계약서 조항 Top-3를 찾았습니다.
각 후보가 표준 조항의 내용을 포함하고 있는지 분석해주세요.

**표준 조항 ({parent_id}):**
{standard_text}

**사용자 계약서 후보 조항 (Top-3):**
{candidates_text}

---

### 📋 **판단 지침**
1. **부분 일치(표현 차이)**: 핵심 내용은 같으나 표현·조건·절차가 다르거나 표현이 다름  
   (예: '제공한다' vs '제공할 수 있다', '사전 동의 받으면 동의' 중 하나만 포함)
2. **무관**: 내용적으로 관련없음
3. 반드시 Top-3 후보 모두에 대해 판단하고, 표준의 핵심요소 중 어떤 부분이 포함/누락되었는지,  
   그로 인한 잠재적 리스크·법적·운영상 문제를 명확히 서술할 것
4. confidence: 0.0~1.0 (0.6 이상 = 내용 유사, 0.3 ~ 0.6 = 부분 유사 / 표현 차이, 0.3 미만 = 무관)

---

### **분석 요청**
각 후보 조항을 표준 조항과 비교하여 자연스러운 문단 형식으로 분석해주세요.

**작성 가이드:**
1. **근거(reasoning)**: 
   - **반드시 후보 조항의 실제 내용을 직접 인용**하여 비교하세요
   - 표준 조항의 핵심 요소(내용, 조건, 절차 등)를 파악하고, 각 후보가 이를 얼마나 포함하는지 서술
   - 예시: "후보 조항은 '데이터 제공 범위는 별도 합의'라고 명시하고 있어, 표준의 '별지1에 기재' 방식과 유사하나..."
   - 누락된 부분이 있다면 구체적으로 명시 (2-3문장의 간결한 문단)

2. **위험(risk)**: "해당 조항이 없으면.." 형식의 시나리오로 작성하세요. 계약 체결·이행·분쟁 시 발생할 수 있는 구체적인 문제 상황을 서술하세요 (1-2문장의 자연스러운 서술)

3. **종합 분석(summary)**: 
   - Top-3 후보를 종합적으로 검토한 결과를 문단으로 작성
   - **각 후보의 핵심 내용을 간략히 인용**하면서 비교
   - 최종적으로 표준 조항이 누락으로 판단되었는지 서술 (3-5문장의 간결한 문단)

4. **전체 위험(overall_risk)**: "해당 조항이 없으면.." 형식으로 시작하여, 계약의 전체 관점에서 발생할 수 있는 법적·운영상 위험을 시나리오 형식으로 서술하세요 (2-3문장의 자연스러운 문단)

5. **권고(recommendation)**: 각 후보별 분석 결과를 바탕으로 "~를 추가할 것을 권장합니다" 형식으로 하나의 권고사항을 작성하세요 (1-2문장)

다음 JSON 형식으로 응답하세요(Top-3 후보 모두 포함):
{{
    "candidates": [
        {{
            "candidate_id": "후보 조항 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이)" | "무관",
            "reasoning": "후보 조항의 실제 내용을 직접 인용하며 표준 조항과 비교. 예: '후보는 \\"[실제 문구]\\"라고 명시하여...' 형식으로 작성 (2-3문장)",
            "risk": "해당 조항이 없으면 [구체적 문제 상황]이 발생할 수 있습니다. [추가 위험 서술] (1-2문장)",
            "recommendation": "구체적 권고사항을 서술하고 '~를 추가할 것을 권장합니다'로 마무리(1-2문장)"
        }},
        {{
            "candidate_id": "후보 2 조항 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이)" | "무관",
            "reasoning": "후보 조항 내용을 직접 인용하며 비교 (2-3문장)",
            "risk": "해당 조항이 없으면.. 시나리오 (1-2문장)",
            "recommendation": "~를 추가할 것을 권장합니다(1-2문장)"
        }},
        {{
            "candidate_id": "후보 3 조항 ID",
            "is_match": true/false,
            "confidence": 0.0~1.0,
            "match_type": "부분 일치(표현 차이)" | "무관",
            "reasoning": "후보 조항 내용을 직접 인용하며 비교 (2-3문장)",
            "risk": "해당 조항이 없으면.. 시나리오 (1-2문장)",
            "recommendation": "~를 추가할 것을 권장합니다(1-2문장)"
        }}
    ],
    "summary": "Top-3 후보의 핵심 내용을 간략히 인용하며 종합 비교. 최종적으로 표준 조항이 누락으로 판단되었는지 서술 (3-5문장의 간결한 문단)",
    "overall_risk": "해당 조항이 없으면 [구체적 시나리오]가 발생할 수 있습니다. 계약 체결·이행·분쟁 시 어떤 문제가 생길 수 있는지 자연스럽게 서술 (2-3문장의 간결한 문단)"
}}

JSON만 응답하세요."""
        
        return prompt
    
    def _parse_forward_verification_response(
        self,
        response_text: str,
        user_candidates: List[Dict[str, Any]],
        standard_article: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        역방향 검증 응답 파싱
        
        Args:
            response_text: LLM 응답
            user_candidates: 사용자 조문 후보들
            standard_article: 표준 조문
        
        Returns:
            파싱된 검증 결과
        """
        import json
        
        try:
            data = json.loads(response_text)
            
            # 후보별 분석 결과
            candidates_analysis = data.get('candidates', [])
            
            # 매칭된 후보 찾기 (is_match=True이고 confidence가 가장 높은 것)
            matched_candidate = None
            matched_user_article = None
            max_confidence = 0.0
            
            for i, candidate_data in enumerate(candidates_analysis):
                if candidate_data.get('is_match', False):
                    confidence = float(candidate_data.get('confidence', 0.0))
                    if confidence > max_confidence:
                        max_confidence = confidence
                        matched_candidate = candidate_data
                        if i < len(user_candidates):
                            matched_user_article = user_candidates[i]['user_article']
            
            # 실제 누락 여부 판단
            is_truly_missing = matched_candidate is None
            
            # 종합 분석에서 정보 추출
            summary = data.get('summary', '')
            overall_risk = data.get('overall_risk', '')
            
            # 권고사항 (매칭된 후보가 있으면 그것의 권고, 없으면 첫 번째 후보의 권고)
            if matched_candidate:
                recommendation = matched_candidate.get('recommendation', f"'{standard_article.get('title')}' 조항 확인 필요")
                reasoning = matched_candidate.get('reasoning', '')
            elif candidates_analysis:
                recommendation = candidates_analysis[0].get('recommendation', f"'{standard_article.get('title')}' 조항을 추가할 것을 권장합니다.")
                reasoning = summary
            else:
                recommendation = f"'{standard_article.get('title')}' 조항을 추가할 것을 권장합니다."
                reasoning = "후보 조문 분석 결과 없음"
            
            return {
                "is_truly_missing": is_truly_missing,
                "confidence": max_confidence if matched_candidate else 1.0,
                "matched_user_article": matched_user_article,
                "reasoning": reasoning,
                "recommendation": recommendation,
                "evidence": summary,
                "risk_assessment": overall_risk,
                "candidates_analysis": candidates_analysis
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"    JSON 파싱 실패: {e}")
            return {
                "is_truly_missing": True,
                "confidence": 0.5,
                "matched_user_article": None,
                "reasoning": "JSON 파싱 실패",
                "recommendation": f"'{standard_article.get('title')}' 조항 확인 필요",
                "evidence": response_text,
                "risk_assessment": "파싱 실패로 정확한 평가 불가",
                "candidates_analysis": []
            }

    def _generate_missing_analysis_without_candidates(
        self,
        standard_article: Dict[str, Any],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        후보 조문이 없을 때 LLM으로 상세한 누락 분석 생성
        
        Args:
            standard_article: 누락된 표준 조문
            contract_type: 계약 유형
        
        Returns:
            상세 분석 결과
        """
        parent_id = standard_article.get('parent_id')
        title = standard_article.get('title', '')
        standard_text = self._format_standard_article(standard_article)
        
        contract_type_names = {
            "provide": "데이터 제공 계약",
            "create": "데이터 생성 계약",
            "process": "데이터 가공 계약",
            "brokerage_provider": "데이터 중개 계약 (제공자용)",
            "brokerage_user": "데이터 중개 계약 (이용자용)"
        }
        
        contract_name = contract_type_names.get(contract_type, contract_type)
        
        prompt = f"""당신은 계약서 조항 분석 및 리스크 평가 전문가입니다.

**분석 대상**
{contract_name}의 표준계약서 조항 "{parent_id} ({title})"이 사용자 계약서에서 완전히 누락되었습니다.
역방향 검색에서도 유사한 조문을 전혀 찾을 수 없었습니다.

**표준 조항 ({parent_id}):**
{standard_text}

---

**과제**: 이 조항이 누락되었을 때의 영향을 상세히 분석해주세요.

**작성 가이드:**
1. **조항의 핵심 목적**: 이 조항이 계약서에서 수행하는 핵심 역할을 2-3문장으로 설명

2. **누락으로 인한 위험**: "해당 조항이 없으면..." 형식으로 시작하여, 계약 체결·이행·분쟁 시 발생할 수 있는 구체적인 문제 상황을 시나리오 형식으로 서술 (3-4문장)

3. **법적·운영상 영향**: 이 조항의 부재가 계약 전체에 미치는 법적·운영상 영향을 구체적으로 서술 (2-3문장)

4. **권고사항**: 이 조항을 어떻게 추가해야 하는지 구체적인 권고 (2-3문장)

다음 JSON 형식으로 응답하세요:
{{
    "purpose": "조항의 핵심 목적 (2-3문장)",
    "risk_scenario": "해당 조항이 없으면 [구체적 시나리오]가 발생할 수 있습니다. [추가 위험 서술] (3-4문장)",
    "legal_impact": "법적·운영상 영향 분석 (2-3문장)",
    "recommendation": "구체적 권고사항. '~를 추가할 것을 권장합니다'로 마무리 (2-3문장)"
}}

JSON만 응답하세요."""
        
        try:
            response = self.azure_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 계약서 조항을 정확하게 분석하는 법률 전문가입니다. JSON 형식으로만 응답하세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content.strip()
            usage = response.usage
            
            # JSON 파싱
            import json
            data = json.loads(response_text)
            
            # 결과 구성
            purpose = data.get('purpose', '')
            risk_scenario = data.get('risk_scenario', '')
            legal_impact = data.get('legal_impact', '')
            recommendation = data.get('recommendation', f"'{title}' 조항을 추가할 것을 권장합니다.")
            
            # 증거 텍스트 구성
            evidence = f"""**조항의 핵심 목적:**
{purpose}

**역방향 검색 결과:**
사용자 계약서 전체를 검색했으나 이 조항과 유사한 내용을 전혀 찾을 수 없었습니다.

**법적·운영상 영향:**
{legal_impact}"""
            
            logger.info(f"    LLM 누락 분석 완료 (토큰: {usage.total_tokens})")
            
            return {
                "is_truly_missing": True,
                "confidence": 1.0,
                "matched_user_article": None,
                "reasoning": f"역방향 검색에서 유사한 조문을 전혀 찾을 수 없었습니다. {purpose}",
                "recommendation": recommendation,
                "evidence": evidence,
                "risk_assessment": risk_scenario,
                "candidates_analysis": [],
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens
            }
            
        except Exception as e:
            logger.error(f"    LLM 누락 분석 실패: {e}")
            return {
                "is_truly_missing": True,
                "confidence": 1.0,
                "matched_user_article": None,
                "reasoning": "사용자 계약서에서 유사한 조문을 찾을 수 없습니다.",
                "recommendation": f"'{title}' 조항을 추가할 것을 권장합니다.",
                "evidence": "역방향 검색에서 유사한 사용자 조문이 발견되지 않았습니다.",
                "risk_assessment": "해당 조항이 없으면 계약 이행 과정에서 불명확성이 발생할 수 있습니다.",
                "candidates_analysis": [],
                "prompt_tokens": 0,
                "completion_tokens": 0
            }
