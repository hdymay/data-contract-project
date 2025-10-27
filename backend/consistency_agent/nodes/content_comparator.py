"""
ContentComparator - LLM 기반 조항 내용 비교
표준계약서 조항과 사용자 조항의 내용 충실도 분석
"""

import logging
from typing import Dict, Any, List, Optional
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class ContentComparator:
    """
    LLM 기반 내용 비교기

    주요 기능:
    1. 표준계약서 조항과 사용자 조항 포맷팅
    2. LLM을 통한 내용 비교 및 분석
    3. 누락/불충분/문제점 식별
    """

    def __init__(self, azure_client: AzureOpenAI, model: str = "gpt-4o"):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
            model: 사용할 모델명 (기본: gpt-4o)
        """
        self.azure_client = azure_client
        self.model = model

        logger.info(f"ContentComparator 초기화 완료 (model={model})")

    def compare_articles(
        self,
        user_article: Dict[str, Any],
        standard_chunks_list: List[List[Dict[str, Any]]],
        contract_type: str
    ) -> Dict[str, Any]:
        """
        조항 내용 비교 (단일 또는 다중 표준 조항)

        Args:
            user_article: 사용자 조항 (content 배열 포함)
            standard_chunks_list: 표준계약서 조항들의 청크 리스트
                - 1개: 직접 비교
                - 2개 이상: LLM이 관련 조항 선택 후 비교
            contract_type: 계약 유형

        Returns:
            {
                "has_issues": bool,
                "missing_items": List[str],
                "insufficient_items": List[str],
                "analysis": str,
                "selected_articles": List[str],  # 선택된 표준 조항 ID들 (다중 매칭시)
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int
            }
        """
        # 사용자 조항 포맷팅
        user_text = self._format_user_article(user_article)

        # 단일 매칭 vs 다중 매칭
        if len(standard_chunks_list) == 1:
            # 1개: 직접 비교
            return self._compare_single_article(
                user_article, standard_chunks_list[0], user_text, contract_type
            )
        else:
            # 2개 이상: 관련 조항 선택 후 비교
            return self._compare_multiple_articles(
                user_article, standard_chunks_list, user_text, contract_type
            )

    def _compare_single_article(
        self,
        user_article: Dict[str, Any],
        standard_chunks: List[Dict[str, Any]],
        user_text: str,
        contract_type: str
    ) -> Dict[str, Any]:
        """
        단일 표준 조항과 비교

        Args:
            user_article: 사용자 조항
            standard_chunks: 표준계약서 조의 모든 청크들
            user_text: 포맷팅된 사용자 조항 텍스트
            contract_type: 계약 유형

        Returns:
            비교 결과
        """
        # 표준계약서 조항 포맷팅
        standard_text = self._format_standard_article(standard_chunks)

        # 프롬프트 생성
        prompt = self._build_single_comparison_prompt(
            user_article_no=user_article.get('number'),
            user_article_title=user_article.get('title', ''),
            standard_article_id=standard_chunks[0].get('parent_id') if standard_chunks else '',
            standard_article_title=standard_chunks[0].get('title', '') if standard_chunks else '',
            standard_text=standard_text,
            user_text=user_text,
            contract_type=contract_type
        )

        # LLM 호출
        try:
            response = self.azure_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 데이터 계약서 전문가입니다. 사용자 계약서 조항이 표준계약서 조항과 비교하여 얼마나 충실하게 작성되었는지 분석합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )

            analysis_text = response.choices[0].message.content.strip()
            usage = response.usage

            # 분석 결과 파싱
            result = self._parse_llm_response(analysis_text)
            result["prompt_tokens"] = usage.prompt_tokens
            result["completion_tokens"] = usage.completion_tokens
            result["total_tokens"] = usage.total_tokens
            result["selected_articles"] = [standard_chunks[0].get('parent_id')] if standard_chunks else []

            logger.info(f"  LLM 단일 비교 완료 (토큰: {usage.total_tokens})")

            return result

        except Exception as e:
            logger.error(f"  LLM 비교 실패: {e}")
            return {
                "has_issues": False,
                "missing_items": [],
                "insufficient_items": [],
                "analysis": f"LLM 분석 실패: {str(e)}",
                "selected_articles": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

    def _compare_multiple_articles(
        self,
        user_article: Dict[str, Any],
        standard_chunks_list: List[List[Dict[str, Any]]],
        user_text: str,
        contract_type: str
    ) -> Dict[str, Any]:
        """
        다중 표준 조항과 비교 (2단계)
        1단계: LLM이 관련 조항 선택
        2단계: 선택된 조항들을 기준으로 내용 분석

        Args:
            user_article: 사용자 조항
            standard_chunks_list: 표준계약서 조항들의 청크 리스트
            user_text: 포맷팅된 사용자 조항 텍스트
            contract_type: 계약 유형

        Returns:
            비교 결과
        """
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # 1단계: 관련 조항 선택
        selection_result = self._select_relevant_articles(
            user_article, standard_chunks_list, user_text, contract_type
        )

        total_prompt_tokens += selection_result.get('prompt_tokens', 0)
        total_completion_tokens += selection_result.get('completion_tokens', 0)

        selected_article_ids = selection_result.get('selected_articles', [])

        if not selected_article_ids:
            logger.warning(f"  관련 조항 선택 실패")
            return {
                "has_issues": False,
                "missing_items": [],
                "insufficient_items": [],
                "analysis": "LLM이 관련 조항을 선택하지 못했습니다.",
                "selected_articles": [],
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens
            }

        logger.info(f"  선택된 조항: {', '.join(selected_article_ids)}")

        # 선택된 조항들의 청크만 필터링
        selected_chunks_list = [
            chunks for chunks in standard_chunks_list
            if chunks and chunks[0].get('parent_id') in selected_article_ids
        ]

        # 2단계: 선택된 조항들을 기준으로 내용 분석
        analysis_result = self._analyze_selected_articles(
            user_article, selected_chunks_list, user_text, contract_type
        )

        total_prompt_tokens += analysis_result.get('prompt_tokens', 0)
        total_completion_tokens += analysis_result.get('completion_tokens', 0)

        analysis_result['prompt_tokens'] = total_prompt_tokens
        analysis_result['completion_tokens'] = total_completion_tokens
        analysis_result['total_tokens'] = total_prompt_tokens + total_completion_tokens
        analysis_result['selected_articles'] = selected_article_ids

        logger.info(f"  LLM 다중 비교 완료 (토큰: {analysis_result['total_tokens']})")

        return analysis_result

    def _format_standard_article(self, chunks: List[Dict[str, Any]]) -> str:
        """
        표준계약서 조항 포맷팅

        parent_id (title)
        id: text_raw
        id: text_raw
        ...

        Args:
            chunks: 동일한 parent_id를 가진 청크들

        Returns:
            포맷팅된 텍스트
        """
        if not chunks:
            return ""

        # parent_id와 title
        parent_id = chunks[0].get('parent_id', '')
        title = chunks[0].get('title', '')

        lines = [f"{parent_id} ({title})"]

        # 각 청크를 id: text_raw 형식으로 추가
        for chunk in chunks:
            chunk_id = chunk.get('id', '')
            text_raw = chunk.get('text_raw', '').strip()

            if chunk_id and text_raw:
                lines.append(f"{chunk_id}: {text_raw}")

        return "\n".join(lines)

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

    def _select_relevant_articles(
        self,
        user_article: Dict[str, Any],
        standard_chunks_list: List[List[Dict[str, Any]]],
        user_text: str,
        contract_type: str
    ) -> Dict[str, Any]:
        """
        관련 표준 조항 선택 (1단계)

        Args:
            user_article: 사용자 조항
            standard_chunks_list: 표준계약서 조항들의 청크 리스트
            user_text: 포맷팅된 사용자 조항 텍스트
            contract_type: 계약 유형

        Returns:
            {
                "selected_articles": List[str],  # 선택된 조항 ID들
                "prompt_tokens": int,
                "completion_tokens": int
            }
        """
        # 모든 후보 조항 포맷팅
        candidates_text = ""
        for chunks in standard_chunks_list:
            if chunks:
                candidates_text += self._format_standard_article(chunks) + "\n\n---\n\n"

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
                        "content": "당신은 데이터 계약서 전문가입니다. 사용자 조항과 관련있는 표준계약서 조항들을 선택합니다."
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
            selected_ids = self._parse_selection_response(selection_text, standard_chunks_list)

            logger.info(f"  조항 선택 완료: {len(selected_ids)}개 (토큰: {usage.total_tokens})")

            return {
                "selected_articles": selected_ids,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens
            }

        except Exception as e:
            logger.error(f"  조항 선택 실패: {e}")
            # 실패 시 모든 후보 반환
            all_ids = [chunks[0].get('parent_id') for chunks in standard_chunks_list if chunks]
            return {
                "selected_articles": all_ids,
                "prompt_tokens": 0,
                "completion_tokens": 0
            }

    def _analyze_selected_articles(
        self,
        user_article: Dict[str, Any],
        selected_chunks_list: List[List[Dict[str, Any]]],
        user_text: str,
        contract_type: str
    ) -> Dict[str, Any]:
        """
        선택된 표준 조항들을 기준으로 내용 분석 (2단계)

        Args:
            user_article: 사용자 조항
            selected_chunks_list: 선택된 표준계약서 조항들의 청크 리스트
            user_text: 포맷팅된 사용자 조항 텍스트
            contract_type: 계약 유형

        Returns:
            비교 결과
        """
        # 선택된 조항들 포맷팅
        standard_text = ""
        for chunks in selected_chunks_list:
            if chunks:
                standard_text += self._format_standard_article(chunks) + "\n\n"

        # 분석 프롬프트 생성
        prompt = self._build_multi_comparison_prompt(
            user_article_no=user_article.get('number'),
            user_article_title=user_article.get('title', ''),
            standard_text=standard_text,
            user_text=user_text,
            contract_type=contract_type,
            num_articles=len(selected_chunks_list)
        )

        try:
            response = self.azure_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 데이터 계약서 전문가입니다. 사용자 계약서 조항이 표준계약서 조항들과 비교하여 얼마나 충실하게 작성되었는지 분석합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )

            analysis_text = response.choices[0].message.content.strip()
            usage = response.usage

            # 분석 결과 파싱
            result = self._parse_llm_response(analysis_text)
            result["prompt_tokens"] = usage.prompt_tokens
            result["completion_tokens"] = usage.completion_tokens

            return result

        except Exception as e:
            logger.error(f"  내용 분석 실패: {e}")
            return {
                "has_issues": False,
                "missing_items": [],
                "insufficient_items": [],
                "analysis": f"LLM 분석 실패: {str(e)}",
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

    def _build_multi_comparison_prompt(
        self,
        user_article_no: int,
        user_article_title: str,
        standard_text: str,
        user_text: str,
        contract_type: str,
        num_articles: int
    ) -> str:
        """
        다중 조항 비교 프롬프트 생성

        Args:
            user_article_no: 사용자 조항 번호
            user_article_title: 사용자 조항 제목
            standard_text: 포맷팅된 표준계약서 조항들 (선택된 것들)
            user_text: 포맷팅된 사용자 조항
            contract_type: 계약 유형
            num_articles: 선택된 표준 조항 개수

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

        prompt = f"""# 계약서 조항 내용 비교 분석

## 계약 유형
{contract_name}

## 표준계약서 조항들 (총 {num_articles}개)
아래 조항들은 사용자 조항과 관련있는 표준계약서 조항들 입니다.

{standard_text}

## 사용자 계약서 조항
제{user_article_no}조 ({user_article_title})
{user_text}

---

위의 표준계약서 조항들을 **모두 종합**하여, 사용자 계약서 조항의 내용 충실도를 분석해주세요.

답변은 다음 형식을 반드시 지키시오:

**문제 여부**: [있음/없음]

**누락된 내용**:
- [표준계약서 조항들에 있지만 사용자 조항에 누락된 내용이 있다면 구체적으로 나열, 없으면 "없음"]

**불충분한 내용**:
- [표준계약서에 비해 불충분하거나 모호한 내용이 있다면 구체적으로 나열, 없으면 "없음"]

**종합 분석**:
[사용자 조항이 표준계약서 조항들과 비교하여 얼마나 충실하게 작성되었는지 종합적으로 평가. 긍정적인 부분과 개선이 필요한 부분을 모두 포함.]

---

**중요**:
- 사용자 계약서는 표준계약서와 완전히 동일할 필요가 없다. 핵심 내용이 포함되어 있고 논리적으로 문제가 없다면 긍정적으로 평가해라.
- 사용자 계약서 조항의 제목을 근거로 사용자가 해당 조항에 어떤 내용을 작성하려 했는지 의도를 짐작해라. 이를 토대로 표준계약서의 각 항목이 사용자의 조항에 포함되어야 하는지, 혹은 제외되어도 되는지를 판단하라.
- 단순한 표현 차이나 순서 차이는 문제로 보지 마라.
- 누락된 내용의 경우 단순 단어나 표현에 대한 누락이 아닌, 의미상의 누락을 감지해야 한다.
- 실질적으로 누락되었거나 불충분한 내용만 지적해라.
- 어투는 경어체로 통일하라.
"""

        return prompt

    def _parse_selection_response(
        self,
        response_text: str,
        standard_chunks_list: List[List[Dict[str, Any]]]
    ) -> List[str]:
        """
        조항 선택 응답 파싱

        Args:
            response_text: LLM 응답 텍스트
            standard_chunks_list: 표준계약서 조항들의 청크 리스트

        Returns:
            선택된 조항 ID 리스트
        """
        import re

        # 가능한 모든 조항 ID 추출
        available_ids = set()
        for chunks in standard_chunks_list:
            if chunks and chunks[0].get('parent_id'):
                available_ids.add(chunks[0].get('parent_id'))

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
            logger.warning(f"  응답에서 조항 ID를 파싱할 수 없음, 모든 후보 반환")
            result = list(available_ids)

        return result

    def _build_single_comparison_prompt(
        self,
        user_article_no: int,
        user_article_title: str,
        standard_article_id: str,
        standard_article_title: str,
        standard_text: str,
        user_text: str,
        contract_type: str
    ) -> str:
        """
        단일 조항 비교 프롬프트 생성

        Args:
            user_article_no: 사용자 조항 번호
            user_article_title: 사용자 조항 제목
            standard_article_id: 표준계약서 조 ID
            standard_article_title: 표준계약서 조 제목
            standard_text: 포맷팅된 표준계약서 조항
            user_text: 포맷팅된 사용자 조항
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

        prompt = f"""# 계약서 조항 내용 비교 분석

## 계약 유형
{contract_name}

## 표준계약서 조항
{standard_text}

## 사용자 계약서 조항
제{user_article_no}조 ({user_article_title})
{user_text}

---

위의 표준계약서 조항을 기준으로, 사용자 계약서 조항의 내용 충실도를 분석해주세요.

답변은 다음 형식을 반드시 지키시오:

**문제 여부**: [있음/없음]

**누락된 내용**:
- [누락된 항목이 있다면 구체적으로 나열, 없으면 "없음"]

**불충분한 내용**:
- [표준계약서에 비해 불충분하거나 모호한 내용이 있다면 구체적으로 나열, 없으면 "없음"]

**종합 분석**:
[사용자 조항이 표준계약서 조항과 비교하여 얼마나 충실하게 작성되었는지 종합적으로 평가. 긍정적인 부분과 개선이 필요한 부분을 모두 포함.]

---

**중요**:
- 사용자 계약서는 표준계약서와 완전히 동일할 필요가 없다. 핵심 내용이 포함되어 있고 논리적으로 문제가 없다면 긍정적으로 평가해라.
- 사용자 계약서 조항의 제목을 근거로 사용자가 해당 조항에 어떤 내용을 작성하려 했는지 의도를 짐작해라. 이를 토대로 표준계약서의 각 항목이 사용자의 조항에 포함되어야 하는지, 혹은 제외되어도 되는지를 판단하라.
- 단순한 표현 차이나 순서 차이는 문제로 보지 마라.
- 누락된 내용의 경우 표현이나 단어에 대한 누락이 아닌, 의미상의 누락을 감지해야 한다.
- 실질적으로 누락되었거나 불충분한 내용만 지적해라.
- 어투는 경어체로 통일하라.
"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        LLM 응답 파싱

        Args:
            response_text: LLM 응답 텍스트

        Returns:
            {
                "has_issues": bool,
                "missing_items": List[str],
                "insufficient_items": List[str],
                "analysis": str
            }
        """
        lines = response_text.split('\n')

        has_issues = False
        missing_items = []
        insufficient_items = []
        analysis = response_text  # 전체 분석 내용

        # "문제 여부" 파싱
        for line in lines:
            if '문제 여부' in line or '문제여부' in line:
                if '있음' in line:
                    has_issues = True
                break

        # "누락된 내용" 섹션 파싱
        in_missing_section = False
        in_insufficient_section = False

        for line in lines:
            line_stripped = line.strip()

            if '누락된 내용' in line_stripped:
                in_missing_section = True
                in_insufficient_section = False
                continue
            elif '불충분한 내용' in line_stripped:
                in_missing_section = False
                in_insufficient_section = True
                continue
            elif '종합 분석' in line_stripped or '**종합' in line_stripped:
                in_missing_section = False
                in_insufficient_section = False
                continue

            # 리스트 항목 파싱
            if in_missing_section and line_stripped.startswith('-'):
                item = line_stripped[1:].strip()
                if item and item.lower() != '없음':
                    missing_items.append(item)

            if in_insufficient_section and line_stripped.startswith('-'):
                item = line_stripped[1:].strip()
                if item and item.lower() != '없음':
                    insufficient_items.append(item)

        # 실제로 문제가 있는지 재확인
        if not missing_items and not insufficient_items:
            has_issues = False

        return {
            "has_issues": has_issues,
            "missing_items": missing_items,
            "insufficient_items": insufficient_items,
            "analysis": analysis
        }
