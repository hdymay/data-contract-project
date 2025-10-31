"""
A3 Node - Content Analysis
조항별 내용 충실도 분석 및 개선 제안 생성
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..models import ArticleAnalysis, ContentAnalysisResult
from .article_matcher import ArticleMatcher
from .content_comparator import ContentComparator

logger = logging.getLogger(__name__)


class ContentAnalysisNode:
    """
    A3 노드 - 내용 분석
    
    주요 기능:
    1. 사용자 조항과 표준 조항 매칭 (ArticleMatcher)
    2. LLM 기반 내용 비교 (ContentComparator)
    3. 개선 제안 생성 (SuggestionGenerator)
    4. 특수 조항 처리 (SpecialArticleHandler)
    """
    
    def __init__(
        self,
        knowledge_base_loader,
        azure_client,
        similarity_threshold: float = 0.7
    ):
        """
        Args:
            knowledge_base_loader: KnowledgeBaseLoader 인스턴스
            azure_client: Azure OpenAI 클라이언트
            similarity_threshold: 매칭 임계값
        """
        self.kb_loader = knowledge_base_loader
        self.azure_client = azure_client
        
        # 하위 컴포넌트 초기화
        self.article_matcher = ArticleMatcher(
            knowledge_base_loader,
            azure_client,
            similarity_threshold=similarity_threshold
        )

        self.content_comparator = ContentComparator(azure_client)

        # TODO: 다른 컴포넌트들 초기화
        # self.suggestion_generator = SuggestionGenerator(azure_client)
        # self.special_handler = SpecialArticleHandler(azure_client)
        
        logger.info("A3 노드 (Content Analysis) 초기화 완료")
    
    def analyze_contract(
        self,
        contract_id: str,
        user_contract: Dict[str, Any],
        contract_type: str,
        text_weight: float = 0.7,
        title_weight: float = 0.3,
        dense_weight: float = 0.85
    ) -> ContentAnalysisResult:
        """
        계약서 전체 분석 (A1 매칭 결과 참조)

        Args:
            contract_id: 계약서 ID
            user_contract: 사용자 계약서 파싱 결과
            contract_type: 분류된 계약 유형
            text_weight: 본문 가중치 (사용하지 않음, A1에서 이미 매칭 완료)
            title_weight: 제목 가중치 (사용하지 않음, A1에서 이미 매칭 완료)
            dense_weight: 시멘틱 가중치 (사용하지 않음, A1에서 이미 매칭 완료)

        Returns:
            ContentAnalysisResult: 전체 분석 결과
        """
        start_time = time.time()

        logger.info(f"A3 분석 시작: {contract_id} (type={contract_type})")

        # 결과 객체 초기화
        result = ContentAnalysisResult(
            contract_id=contract_id,
            contract_type=contract_type,
            analysis_timestamp=datetime.now()
        )

        # 사용자 계약서 조항 추출
        articles = user_contract.get('articles', [])
        result.total_articles = len(articles)

        if not articles:
            logger.warning("  분석할 조항이 없습니다")
            result.processing_time = time.time() - start_time
            return result

        # A1 매칭 결과 로드
        a1_matching_details = self._load_a1_matching_results(contract_id)

        if not a1_matching_details:
            logger.warning("  A1 매칭 결과를 찾을 수 없습니다")
            result.processing_time = time.time() - start_time
            return result

        # 조항 번호별 매칭 결과 매핑
        a1_results_by_article = {
            detail['user_article_no']: detail
            for detail in a1_matching_details
        }

        logger.info(f"  A1 매칭 결과 로드 완료: {len(a1_results_by_article)}개 조항")

        # 각 조항 분석
        for article in articles:
            try:
                article_no = article.get('number')
                a1_result = a1_results_by_article.get(article_no)

                analysis = self.analyze_article(
                    article,
                    contract_type,
                    contract_id,
                    a1_matching_result=a1_result
                )
                result.article_analysis.append(analysis)

                if analysis.matched:
                    result.analyzed_articles += 1
                if analysis.is_special:
                    result.special_articles += 1

            except Exception as e:
                logger.error(f"  조항 분석 실패 (제{article.get('number')}조): {e}")
                continue

        # 처리 시간 기록
        result.processing_time = time.time() - start_time

        logger.info(f"A3 분석 완료: {result.analyzed_articles}/{result.total_articles}개 조항 분석 ({result.processing_time:.2f}초)")

        return result
    
    def analyze_article(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        contract_id: str = None,
        a1_matching_result: Dict[str, Any] = None
    ) -> ArticleAnalysis:
        """
        단일 조항 분석 (A1 매칭 결과 참조)

        Args:
            user_article: 사용자 계약서 조항
            contract_type: 계약 유형
            contract_id: 계약서 ID (토큰 로깅용)
            a1_matching_result: A1 노드의 매칭 결과 (해당 조항)

        Returns:
            ArticleAnalysis: 조항 분석 결과
        """
        article_no = user_article.get('number')
        article_title = user_article.get('title', '')

        logger.info(f"  조항 분석: 제{article_no}조 ({article_title})")

        # 기본 분석 객체 생성
        analysis = ArticleAnalysis(
            user_article_no=article_no,
            user_article_title=article_title,
            matched=False,
            similarity=0.0,
            analysis_timestamp=datetime.now()
        )

        try:
            # A1 매칭 결과가 없으면 분석 불가
            if not a1_matching_result:
                logger.warning(f"    A1 매칭 결과 없음")
                analysis.reasoning = "A1 매칭 결과를 찾을 수 없습니다"
                return analysis

            # A1 매칭 결과 참조
            analysis.matched = a1_matching_result.get('matched', False)

            # A1에서는 is_special 필드가 없으므로 기본값 사용
            analysis.is_special = False

            # A1 매칭 정보
            matched_article_ids = a1_matching_result.get('matched_articles', [])

            if not analysis.matched or not matched_article_ids:
                logger.info(f"    매칭 실패: A1에서 매칭되지 않음")
                analysis.reasoning = "A1 매칭 검증 통과 못함"
                return analysis

            # 매칭된 조항 정보 구성 (A1 결과 기반)
            # A1의 matched_articles는 조항 ID 리스트 (예: ["제5조", "제7조"])
            # A3는 상세 정보가 필요하므로 표준계약서 청크 로드
            analysis.matched_articles = []

            for std_article_id in matched_article_ids:
                # 해당 조의 청크 로드
                chunks = self.article_matcher.load_full_article_chunks(
                    std_article_id,
                    contract_type
                )

                if chunks:
                    # 조 정보 추가
                    article_info = {
                        'parent_id': std_article_id,
                        'title': chunks[0].get('title', ''),
                        'score': 0.0,  # A1에서는 유사도를 조 단위로 제공하지 않음
                        'num_sub_items': 0,  # A1에서는 하위항목 개수 정보 없음
                        'matched_chunks': chunks
                    }
                    analysis.matched_articles.append(article_info)

            if not analysis.matched_articles:
                logger.warning(f"    청크 로드 실패: 모든 표준 조항")
                analysis.reasoning = "표준계약서 조항 로드 실패"
                return analysis

            # 첫 번째 조 정보 (UI 표시용)
            first_article = analysis.matched_articles[0]
            analysis.similarity = first_article.get('score', 0.0)
            analysis.std_article_id = first_article['parent_id']
            analysis.std_article_title = first_article.get('title', '')

            # 매칭 성공
            logger.info(f"    매칭 성공 (A1 참조): {analysis.std_article_id}")
            logger.info(f"    매칭된 조항: {len(analysis.matched_articles)}개")

            # 여러 조가 매칭된 경우
            if len(analysis.matched_articles) > 1:
                other_articles = [a['parent_id'] for a in analysis.matched_articles[1:]]
                logger.info(f"    기타 매칭 조: {', '.join(other_articles)}")
                analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨. 기타 매칭: {', '.join(other_articles)}"
            else:
                analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨"

            # ContentComparator로 내용 비교
            # 상위 4개 매칭 조의 청크 로드 (이미 로드됨)
            top_matched_articles = analysis.matched_articles[:4]
            standard_chunks_list = [
                article['matched_chunks'] for article in top_matched_articles
                if article.get('matched_chunks')
            ]

            if len(analysis.matched_articles) > 4:
                logger.info(f"      매칭 조 {len(analysis.matched_articles)}개 중 상위 4개만 LLM 비교 수행")

            if not standard_chunks_list:
                logger.warning(f"      모든 표준계약서 조 청크 로드 실패")
            else:
                # LLM 비교 수행
                # A1에서 이미 관련 조항을 선택했으므로
                # 1개: 직접 비교
                # 2개 이상: 모든 조항을 종합하여 비교
                comparison_result = self.content_comparator.compare_articles(
                    user_article,
                    standard_chunks_list,
                    contract_type
                )

                # 선택된 조항 정보
                selected_article_ids = comparison_result.get('selected_articles', [])
                logger.info(f"      내용 비교 대상: {', '.join(selected_article_ids)}")

                # 토큰 사용량 로깅
                if contract_id:
                    self._log_token_usage(
                        contract_id,
                        comparison_result.get('prompt_tokens', 0),
                        comparison_result.get('completion_tokens', 0),
                        comparison_result.get('total_tokens', 0),
                        extra_info={
                            'operation': 'content_comparison',
                            'user_article_no': article_no,
                            'num_candidates': len(analysis.matched_articles),
                            'selected_articles': selected_article_ids
                        }
                    )

                # 제안 생성 (analysis가 있으면 항상 생성)
                analysis_text = comparison_result.get('analysis', '')
                if analysis_text:
                    if comparison_result.get('has_issues'):
                        # 문제가 있는 경우
                        missing_count = len(comparison_result.get('missing_items', []))
                        insufficient_count = len(comparison_result.get('insufficient_items', []))

                        # 심각도 결정
                        # high: 누락 항목 3개 이상 또는 (누락 + 불충분) 5개 이상
                        # medium: 누락 항목 1개 이상 또는 불충분 항목 2개 이상
                        # low: 그 외
                        if missing_count >= 3 or (missing_count + insufficient_count) >= 5:
                            severity = 'high'
                        elif missing_count >= 2 or insufficient_count >= 2:
                            severity = 'medium'
                        else:
                            severity = 'low'

                        suggestion = {
                            'selected_standard_articles': selected_article_ids,
                            'issue_type': 'content',
                            'missing_items': comparison_result.get('missing_items', []),
                            'insufficient_items': comparison_result.get('insufficient_items', []),
                            'analysis': analysis_text,
                            'severity': severity
                        }
                        analysis.suggestions.append(suggestion)
                        logger.info(f"      내용 분석: 문제 발견 (누락: {missing_count}개, 불충분: {insufficient_count}개, 심각도: {severity})")
                    else:
                        # 문제가 없는 경우 (긍정적 분석)
                        suggestion = {
                            'selected_standard_articles': selected_article_ids,
                            'issue_type': 'content',
                            'missing_items': [],
                            'insufficient_items': [],
                            'analysis': analysis_text,
                            'severity': 'info'  # 정보성 (문제 없음)
                        }
                        analysis.suggestions.append(suggestion)
                        logger.info(f"      내용 분석: 문제 없음 (긍정적 분석 포함)")

        except Exception as e:
            logger.error(f"    조항 분석 중 오류: {e}")
            analysis.reasoning = f"분석 중 오류 발생: {str(e)}"

        return analysis

    def _load_a1_matching_results(self, contract_id: str) -> List[Dict[str, Any]]:
        """
        A1 노드의 매칭 결과를 DB에서 로드

        Args:
            contract_id: 계약서 ID

        Returns:
            A1 매칭 결과의 matching_details (조항별 매칭 정보 리스트)
        """
        try:
            from backend.shared.database import SessionLocal, ValidationResult

            db = SessionLocal()
            try:
                # ValidationResult에서 completeness_check 필드 로드
                validation_result = db.query(ValidationResult).filter(
                    ValidationResult.contract_id == contract_id
                ).first()

                if not validation_result:
                    logger.warning(f"  ValidationResult를 찾을 수 없음: {contract_id}")
                    return []

                completeness_check = validation_result.completeness_check
                if not completeness_check:
                    logger.warning(f"  A1 완전성 검증 결과가 없음: {contract_id}")
                    return []

                matching_details = completeness_check.get('matching_details', [])

                logger.debug(f"  A1 매칭 결과 로드: {len(matching_details)}개 조항")

                return matching_details

            finally:
                db.close()

        except Exception as e:
            logger.error(f"  A1 매칭 결과 로드 실패: {e}")
            return []

    def _log_token_usage(
        self,
        contract_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        extra_info: dict = None
    ):
        """
        토큰 사용량을 데이터베이스에 로깅

        Args:
            contract_id: 계약서 ID
            prompt_tokens: 입력 토큰 수
            completion_tokens: 출력 토큰 수
            total_tokens: 총 토큰 수
            extra_info: 추가 정보 (operation, article_no 등)
        """
        try:
            from backend.shared.database import SessionLocal, TokenUsage
            from datetime import datetime

            db = SessionLocal()
            try:
                token_record = TokenUsage(
                    contract_id=contract_id,
                    component="consistency_agent",
                    api_type="chat_completion",
                    model=self.content_comparator.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    created_at=datetime.utcnow(),
                    extra_info=extra_info
                )
                db.add(token_record)
                db.commit()
                logger.debug(f"      토큰 사용량 로깅 완료: {total_tokens} tokens")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"      토큰 사용량 로깅 실패: {e}")
