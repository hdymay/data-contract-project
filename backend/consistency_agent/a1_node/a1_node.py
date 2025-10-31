"""
A1 Node - Completeness Check (완전성 검증)

사용자 계약서 조문별로 표준계약과 매칭하여 누락된 조문을 식별
다단계 검증과 LLM 매칭 검증 수행
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict
from openai import AzureOpenAI

from .article_matcher import ArticleMatcher
from .matching_verifier import MatchingVerifier

logger = logging.getLogger(__name__)


class CompletenessCheckNode:
    """
    A1 노드 - 완전성 검증
    주요 기능:
    1. 사용자 조문과 표준 조문 매칭 (ArticleMatcher)
    2. LLM 기반 매칭 검증(MatchingVerifier)
    3. 누락 조문 식별 및 보고서 생성
    4. 매칭 결과 DB 저장
    """

    def __init__(
        self,
        knowledge_base_loader,
        azure_client: AzureOpenAI,
        matching_threshold: float = 0.7
    ):
        """
        Args:
            knowledge_base_loader: KnowledgeBaseLoader 서비스
            azure_client: Azure OpenAI 클라이언트
            matching_threshold: 매칭 성공 임계치(기본 0.7)
        """
        self.kb_loader = knowledge_base_loader
        self.azure_client = azure_client
        self.threshold = matching_threshold

        # 내부 컴포넌트 초기화
        self.article_matcher = ArticleMatcher(
            knowledge_base_loader,
            azure_client,
            similarity_threshold=matching_threshold
        )

        self.matching_verifier = MatchingVerifier(
            azure_client,
            model="gpt-4o"
        )

        logger.info("A1 노드 (Completeness Check) 초기화 완료")

    def check_completeness(
        self,
        contract_id: str,
        user_contract: Dict[str, Any],
        contract_type: str,
        text_weight: float = 0.7,
        title_weight: float = 0.3,
        dense_weight: float = 0.85
    ) -> Dict[str, Any]:
        """
        계약서 완전성 검증
        Args:
            contract_id: 계약서 ID
            user_contract: 사용자 계약서 파싱 결과
            contract_type: 분류된 계약 유형
            text_weight: 본문 가중치 (기본값 0.7)
            title_weight: 제목 가중치 (기본값 0.3)
            dense_weight: 임베딩가중치 (기본값 0.85)

        Returns:
            완전성 검증 결과
        """
        start_time = time.time()

        logger.info(f"A1 완전성 검증 시작: {contract_id} (type={contract_type})")

        # 사용자 계약서 조항 추출
        user_articles = user_contract.get('articles', [])
        total_user_articles = len(user_articles)

        if not user_articles:
            logger.warning("  검증할 조항이 없습니다")
            return {
                "contract_id": contract_id,
                "contract_type": contract_type,
                "total_user_articles": 0,
                "matched_user_articles": 0,
                "total_standard_articles": 0,
                "matched_standard_articles": 0,
                "missing_standard_articles": [],
                "matching_details": [],
                "processing_time": time.time() - start_time,
                "verification_date": datetime.now().isoformat()
            }

        # 표준계약서 항목 로드
        standard_chunks = self.kb_loader.load_chunks(contract_type)
        if not standard_chunks:
            logger.error(f"  표준계약서 데이터를 로드 실패: {contract_type}")
            raise ValueError(f"표준계약서 데이터를 로드할 수 없습니다: {contract_type}")

        # 표준계약서의 parent_id 목록 추출
        standard_articles = self._extract_standard_articles(standard_chunks)
        total_standard_articles = len(standard_articles)

        logger.info(f"  사용자 조문: {total_user_articles}개, 표준 조문: {total_standard_articles}개")

        # 1단계: 모든 사용자 조문과 표준 조문 매칭 수행
        matched_standard_articles: Set[str] = set()  # 매칭된 표준 조문 ID
        matched_user_articles: Set[int] = set()  # 매칭된 사용자조문 번호
        matching_details: List[Dict] = []

        for article in user_articles:
            try:
                article_result = self._check_article(
                    article,
                    contract_type,
                    contract_id,
                    text_weight,
                    title_weight,
                    dense_weight
                )

                matching_details.append(article_result)

                # 매칭 성공 시 추적
                if article_result['matched'] and article_result['matched_articles']:
                    matched_user_articles.add(article.get('number'))
                    for matched_std_id in article_result['matched_articles']:
                        matched_standard_articles.add(matched_std_id)

            except Exception as e:
                logger.error(f"  조항 검증 실패 (제{article.get('number')}조): {e}")
                continue

        # 2단계: 누락된 표준 조문 식별
        missing_articles = [
            std_article for std_article in standard_articles
            if std_article['parent_id'] not in matched_standard_articles
        ]

        logger.info(f"  매칭 완료: 사용자 {len(matched_user_articles)}/{total_user_articles}, "
                   f"표준 {len(matched_standard_articles)}/{total_standard_articles}")
        logger.info(f"  누락 조문: {len(missing_articles)}개")

        # 3단계: 누락 조문 재검증 (TODO: 구현 필요)
        # missing_article_analysis = self._verify_missing_articles(
        #     missing_articles, user_articles, contract_type, contract_id
        # )

        # 결과 생성
        processing_time = time.time() - start_time

        result = {
            "contract_id": contract_id,
            "contract_type": contract_type,
            "total_user_articles": total_user_articles,
            "matched_user_articles": len(matched_user_articles),
            "total_standard_articles": total_standard_articles,
            "matched_standard_articles": len(matched_standard_articles),
            "missing_standard_articles": missing_articles,
            "matching_details": matching_details,
            "processing_time": processing_time,
            "verification_date": datetime.now().isoformat()
        }

        logger.info(f"A1 완전성 검증 완료: {processing_time:.2f}초")

        return result

    def _check_article(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        contract_id: str,
        text_weight: float,
        title_weight: float,
        dense_weight: float
    ) -> Dict[str, Any]:
        """
        단일 조항 완전성 검증
        Args:
            user_article: 사용자 조항
            contract_type: 계약 유형
            contract_id: 계약서ID (토큰 로깅용)
            text_weight: 본문 가중치
            title_weight: 제목 가중치
            dense_weight: 임베딩가중치

        Returns:
            조항 매칭 결과
        """
        article_no = user_article.get('number')
        article_title = user_article.get('title', '')

        logger.info(f"  완전성 검증 제{article_no}조({article_title})")

        # 기본 결과 객체
        result = {
            "user_article_no": article_no,
            "user_article_title": article_title,
            "matched": False,
            "matched_articles": [],
            "verification_details": []
        }

        try:
            # 1단계: 검색 기반 후보 취합 (ArticleMatcher)
            matching_result = self.article_matcher.find_matching_article(
                user_article,
                contract_type,
                top_k=1,  # 단계별로 top-1까지만 사용
                contract_id=contract_id,
                text_weight=text_weight,
                title_weight=title_weight,
                dense_weight=dense_weight
            )

            if not matching_result['matched'] or not matching_result['matched_articles']:
                logger.warning(f"    매칭 실패: 검색결과 없음")
                return result

            candidate_articles = matching_result['matched_articles']
            logger.info(f"    후보 조문: {len(candidate_articles)}개")

            # 2단계: LLM 매칭 검증(MatchingVerifier)
            verification_result = self.matching_verifier.verify_matching(
                user_article,
                candidate_articles,
                contract_type,
                top_k=5  # Top-5 조문 LLM 검증
            )

            if verification_result['matched']:
                result['matched'] = True
                result['matched_articles'] = verification_result['selected_articles']
                result['verification_details'] = verification_result.get('verification_details', [])

                logger.info(f"    매칭 성공: {len(result['matched_articles'])}개 조문")
                for std_id in result['matched_articles']:
                    logger.info(f"      - {std_id}")
            else:
                logger.warning(f"    매칭 실패: LLM 검증 통과 못함")

        except Exception as e:
            logger.error(f"    조항 검증 중 오류: {e}")
            result['error'] = str(e)

        return result

    def _extract_standard_articles(self, chunks: List[Dict]) -> List[Dict]:
        """
        표준계약서 항목 정보를 parent_id 기준으로 그룹화

        Args:
            chunks: 표준계약서 청크 리스트
        Returns:
            조항단위로 그룹화된 정보 리스트
        """
        article_map = defaultdict(lambda: {
            'parent_id': None,
            'title': None,
            'chunks': []
        })

        for chunk in chunks:
            parent_id = chunk.get('parent_id')
            if not parent_id:
                continue

            if article_map[parent_id]['parent_id'] is None:
                article_map[parent_id]['parent_id'] = parent_id
                article_map[parent_id]['title'] = chunk.get('title', '')

            article_map[parent_id]['chunks'].append(chunk)

        # 리스트로 변환 후 정렬
        articles = list(article_map.values())
        articles.sort(key=lambda x: self._extract_article_number(x['parent_id']))

        return articles

    def _extract_article_number(self, parent_id: str) -> int:
        """
        항목ID에서 숫자 추출 (정렬용)

        예: "제3조" -> 3
        """
        import re
        match = re.search(r'\d+', parent_id)
        if match:
            return int(match.group())
        return 999999
