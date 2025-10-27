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
        contract_type: str
    ) -> ContentAnalysisResult:
        """
        계약서 전체 분석
        
        Args:
            contract_id: 계약서 ID
            user_contract: 사용자 계약서 파싱 결과
            contract_type: 분류된 계약 유형
            
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
        
        # 각 조항 분석
        for article in articles:
            try:
                analysis = self.analyze_article(article, contract_type, contract_id)
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
        contract_id: str = None
    ) -> ArticleAnalysis:
        """
        단일 조항 분석

        Args:
            user_article: 사용자 계약서 조항
            contract_type: 계약 유형
            contract_id: 계약서 ID (토큰 로깅용)

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
            # 1. 대응 조항 검색
            matching_result = self.article_matcher.find_matching_article(
                user_article,
                contract_type,
                contract_id=contract_id
            )

            # 매칭 정보 업데이트
            analysis.matched = matching_result['matched']
            analysis.is_special = matching_result['is_special']
            analysis.sub_item_results = matching_result.get('sub_item_results', [])
            analysis.matched_articles = matching_result.get('matched_articles', [])

            if analysis.matched and analysis.matched_articles:
                # 첫 번째 조 정보 (UI 표시용)
                first_article = analysis.matched_articles[0]
                analysis.similarity = first_article['score']
                analysis.std_article_id = first_article['parent_id']
                analysis.std_article_title = first_article.get('title', '')

                # 매칭 성공
                logger.info(f"    매칭 성공: {analysis.std_article_id} (유사도: {analysis.similarity:.3f})")
                logger.info(f"    하위항목 결과: {len(analysis.sub_item_results)}개")

                # 여러 조가 매칭된 경우
                if len(analysis.matched_articles) > 1:
                    other_articles = [a['parent_id'] for a in analysis.matched_articles[1:]]
                    logger.info(f"    기타 매칭 조: {', '.join(other_articles)}")
                    analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨 (유사도: {analysis.similarity:.3f}). 기타 매칭: {', '.join(other_articles)}"
                else:
                    analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨 (유사도: {analysis.similarity:.3f})"

                # ContentComparator로 내용 비교
                # 모든 매칭된 조의 청크 로드
                standard_chunks_list = []
                for matched_article in analysis.matched_articles:
                    parent_id = matched_article['parent_id']

                    # 해당 조의 모든 청크 로드
                    chunks = self.article_matcher.load_full_article_chunks(
                        parent_id,
                        contract_type
                    )

                    if chunks:
                        standard_chunks_list.append(chunks)
                    else:
                        logger.warning(f"      표준계약서 조 청크 로드 실패: {parent_id}")

                if not standard_chunks_list:
                    logger.warning(f"      모든 표준계약서 조 청크 로드 실패")
                else:
                    # LLM 비교 수행
                    # 1개: 직접 비교
                    # 2개 이상: LLM이 관련 조항 선택 후 비교
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

            else:
                # 매칭 실패 (검색 결과 없음)
                analysis.similarity = 0.0
                analysis.std_article_id = None
                analysis.std_article_title = None
                logger.info(f"    매칭 실패: 검색 결과 없음")
                analysis.reasoning = "매칭 실패: 검색 결과 없음"

        except Exception as e:
            logger.error(f"    조항 분석 중 오류: {e}")
            analysis.reasoning = f"분석 중 오류 발생: {str(e)}"

        return analysis

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
