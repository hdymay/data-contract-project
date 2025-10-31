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
