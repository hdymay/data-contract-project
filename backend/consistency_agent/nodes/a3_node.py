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
        
        # TODO: 다른 컴포넌트들 초기화
        # self.content_comparator = ContentComparator(azure_client)
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
                analysis = self.analyze_article(article, contract_type)
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
        contract_type: str
    ) -> ArticleAnalysis:
        """
        단일 조항 분석
        
        Args:
            user_article: 사용자 계약서 조항
            contract_type: 계약 유형
            
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
                contract_type
            )
            
            # 매칭 정보 업데이트
            analysis.matched = matching_result['matched']
            analysis.is_special = matching_result['is_special']
            analysis.sub_item_results = matching_result.get('sub_item_results', [])
            
            if analysis.matched:
                # Primary 조 정보
                primary = matching_result['primary_article']
                analysis.similarity = primary['score']
                analysis.std_article_id = primary['parent_id']
                analysis.std_article_title = primary.get('title', '')
                
                # 매칭 성공
                logger.info(f"    매칭 성공: {analysis.std_article_id} (유사도: {analysis.similarity:.3f})")
                logger.info(f"    하위항목 결과: {len(analysis.sub_item_results)}개")
                
                # 여러 조가 매칭된 경우
                matched_articles = matching_result.get('matched_articles', [])
                if len(matched_articles) > 1:
                    other_articles = [a['parent_id'] for a in matched_articles[1:]]
                    logger.info(f"    기타 매칭 조: {', '.join(other_articles)}")
                    analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨 (유사도: {analysis.similarity:.3f}). 기타 매칭: {', '.join(other_articles)}"
                else:
                    analysis.reasoning = f"표준계약서 {analysis.std_article_id}와 매칭됨 (유사도: {analysis.similarity:.3f})"
                
                # TODO: ContentComparator로 내용 비교 및 제안 생성
                # comparison_result = self.content_comparator.compare_articles(
                #     user_article, std_chunks
                # )
                # analysis.suggestions = self.suggestion_generator.generate_suggestions(
                #     user_article, std_chunks, comparison_result
                # )
                
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
