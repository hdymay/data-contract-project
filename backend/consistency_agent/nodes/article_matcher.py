"""
ArticleMatcher - 대응 조항 검색 (멀티벡터 방식)
사용자 계약서 조항과 표준계약서 조항 매칭
"""

import logging
import re
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict, Counter
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class ArticleMatcher:
    """
    대응 조항 검색기
    
    멀티벡터 검색 방식:
    1. 사용자 조항의 각 하위항목으로 개별 검색
    2. Top-K 청크 검색 (FAISS + Whoosh 하이브리드)
    3. 청크를 조 단위로 취합 (정규화된 평균 점수)
    4. 최고 점수 조 선택
    """
    
    def __init__(
        self,
        knowledge_base_loader,
        azure_client: AzureOpenAI,
        embedding_model: str = "text-embedding-3-large",
        similarity_threshold: float = 0.7,
        special_threshold: float = 0.3
    ):
        """
        Args:
            knowledge_base_loader: KnowledgeBaseLoader 인스턴스
            azure_client: Azure OpenAI 클라이언트
            embedding_model: 임베딩 모델명
            similarity_threshold: 매칭 성공 임계값 (기본 0.7)
            special_threshold: 특수 조항 임계값 (기본 0.3, 이 값 미만이면 특수 조항)
        """
        self.kb_loader = knowledge_base_loader
        self.azure_client = azure_client
        self.embedding_model = embedding_model
        self.threshold = similarity_threshold
        self.special_threshold = special_threshold
        
        # 조별 청크 개수 캐싱 (정규화 계산용)
        self.article_chunk_counts = {}
        
        # HybridSearcher 인스턴스 (계약 유형별)
        self.searchers = {}
        
        logger.info(f"ArticleMatcher 초기화 완료 (match_threshold={similarity_threshold}, special_threshold={special_threshold})")
    
    def find_matching_article(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        대응 조항 검색 (멀티벡터 방식)
        
        각 하위항목별로:
        1. top_k 청크 검색
        2. 조별 평균 점수 계산
        3. 최고 점수 조 선정
        
        최종적으로 하위항목별 결과를 조 단위로 집계
        
        Args:
            user_article: 사용자 조항 (content 배열 포함)
            contract_type: 계약 유형
            top_k: 청크 레벨 검색 결과 개수 (기본 5)
            
        Returns:
            {
                "matched": bool,
                "matched_articles": List[Dict],  # 매칭된 조 목록 (여러 개 가능)
                "primary_article": Dict,  # 최고 점수 조
                "sub_item_results": List[Dict],  # 하위항목별 결과
                "is_special": bool
            }
        """
        user_article_no = user_article.get('number')
        user_article_title = user_article.get('title', '')
        
        logger.info(f"조항 매칭 시작: 제{user_article_no}조 ({user_article_title})")
        
        # 멀티벡터 검색
        matched_articles, sub_item_results = self._search_with_sub_items(
            user_article,
            contract_type,
            top_k
        )
        
        if not matched_articles:
            logger.warning(f"  매칭 실패: 검색 결과 없음")
            return {
                "matched": False,
                "matched_articles": [],
                "primary_article": None,
                "sub_item_results": sub_item_results,
                "is_special": False
            }
        
        # Primary 조 (최고 점수)
        primary_article = matched_articles[0]
        
        logger.info(f"  매칭 완료: {len(matched_articles)}개 조")
        logger.info(f"  Primary: {primary_article['parent_id']} (유사도 {primary_article['score']:.3f})")
        if len(matched_articles) > 1:
            logger.info(f"  기타 매칭 조:")
            for article in matched_articles[1:]:
                logger.info(f"    - {article['parent_id']}: {article['score']:.3f} (하위항목 {article['num_sub_items']}개)")
        
        return {
            "matched": True,
            "matched_articles": matched_articles,  # 모든 매칭 조
            "primary_article": primary_article,  # 최고 점수 조
            "sub_item_results": sub_item_results,  # 하위항목별 결과
            "is_special": False
        }
    
    def _search_with_sub_items(
        self,
        user_article: Dict[str, Any],
        contract_type: str,
        top_k: int = 5
    ) -> tuple[List[Dict], List[Dict]]:
        """
        사용자 조항의 각 하위항목으로 검색
        
        각 하위항목별로:
        1. top_k 청크 검색
        2. 조별로 평균 점수 계산
        3. 최고 점수 조 1개 선정
        
        Returns:
            (article_scores, sub_item_results)
            - article_scores: 조 단위 최종 결과 (하위항목별 결과 집계)
            - sub_item_results: 하위항목별 매칭 결과
        """
        content_items = user_article.get('content', [])
        article_title = user_article.get('title', '')
        
        if not content_items:
            logger.warning("  하위항목이 없습니다")
            return [], []
        
        # 하위항목별 매칭 결과
        sub_item_results = []
        
        for idx, sub_item in enumerate(content_items, 1):
            # 정규화
            normalized = self._normalize_sub_item(sub_item)
            
            if not normalized:
                continue
            
            # 검색 쿼리 생성
            query = self._build_search_query(normalized, article_title)
            
            logger.debug(f"    하위항목 {idx} 검색: {query[:100]}...")
            
            # 하이브리드 검색 수행 (top_k 청크)
            chunk_results = self._hybrid_search(query, contract_type, top_k)
            
            if not chunk_results:
                continue
            
            # 이 하위항목의 top_k 결과에서 조별 평균 점수 계산
            best_article = self._select_best_article_from_chunks(chunk_results)
            
            if best_article:
                sub_item_results.append({
                    'sub_item_index': idx,
                    'sub_item_text': sub_item,
                    'normalized_text': normalized,
                    'matched_article_id': best_article['parent_id'],
                    'matched_article_title': best_article['title'],
                    'score': best_article['score'],
                    'matched_chunks': best_article['chunks']
                })
                
                logger.debug(f"      → {best_article['parent_id']}: {best_article['score']:.3f}")
        
        if not sub_item_results:
            return [], []
        
        # 하위항목별 결과를 조 단위로 집계
        article_scores = self._aggregate_sub_item_results(sub_item_results)
        
        return article_scores, sub_item_results
    
    def _normalize_sub_item(self, content: str) -> str:
        """
        사용자 계약서 하위항목 정규화
        
        - 앞뒤 공백 제거
        - ①②③ 등의 원문자 제거
        - 1. 2. 3. 등의 번호 제거
        - (가) (나) 등의 괄호 번호 제거
        """
        # 앞뒤 공백 제거
        text = content.strip()
        
        # 원문자 제거 (①②③...)
        text = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]+\s*', '', text)
        
        # 숫자 + 점 제거 (1. 2. 3. ...)
        text = re.sub(r'^\d+\.\s*', '', text)
        
        # 괄호 번호 제거 ((가) (나) ...)
        text = re.sub(r'^\([가-힣]\)\s*', '', text)
        
        # 다시 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def _build_search_query(
        self,
        sub_item: str,
        article_title: str
    ) -> str:
        """
        검색 쿼리 생성
        
        하위항목 전체 내용 + 조 제목 (제목은 뒤에 배치하여 가중치 과다 방지)
        
        Args:
            sub_item: 정규화된 하위항목 내용 (전체)
            article_title: 조 제목 (예: "데이터 제공 범위 및 방식")
            
        Returns:
            "{sub_item} {article_title}"
        """
        # 하위항목 전체 내용 사용 (제목은 뒤에 배치)
        return f"{sub_item} {article_title}"
    
    def _get_or_create_searcher(self, contract_type: str):
        """
        계약 유형별 HybridSearcher 가져오기 (없으면 생성)
        
        Args:
            contract_type: 계약 유형
            
        Returns:
            HybridSearcher 인스턴스
        """
        if contract_type in self.searchers:
            return self.searchers[contract_type]
        
        # HybridSearcher 생성
        from backend.consistency_agent.hybrid_searcher import HybridSearcher
        
        searcher = HybridSearcher(
            azure_client=self.azure_client,
            embedding_model=self.embedding_model,
            dense_weight=0.85
        )
        
        # 인덱스 로드
        faiss_index = self.kb_loader.load_faiss_index(contract_type)
        chunks = self.kb_loader.load_chunks(contract_type)
        whoosh_indexer = self.kb_loader.load_whoosh_index(contract_type)
        
        if not faiss_index or not chunks or not whoosh_indexer:
            logger.error(f"인덱스 로드 실패: {contract_type}")
            return None
        
        searcher.load_indexes(faiss_index, chunks, whoosh_indexer)
        
        # 캐싱
        self.searchers[contract_type] = searcher
        
        return searcher
    
    def _hybrid_search(
        self,
        query: str,
        contract_type: str,
        top_k: int
    ) -> List[Dict]:
        """
        하이브리드 검색 수행 (FAISS + Whoosh)
        
        Returns:
            검색 결과 청크 리스트
        """
        searcher = self._get_or_create_searcher(contract_type)
        
        if not searcher:
            logger.error(f"Searcher를 생성할 수 없습니다: {contract_type}")
            return []
        
        # 하이브리드 검색 수행
        results = searcher.search(query, top_k=top_k)
        
        return results
    
    def _select_best_article_from_chunks(
        self,
        chunk_results: List[Dict]
    ) -> Optional[Dict]:
        """
        청크 검색 결과에서 최고 점수 조 1개 선정
        
        각 조별로 평균 점수를 계산하고 최고 점수 조 반환
        
        Args:
            chunk_results: 하이브리드 검색 결과 (top_k 청크)
            
        Returns:
            {
                'parent_id': str,
                'title': str,
                'score': float,  # 조 평균 점수
                'chunks': List[Dict]  # 해당 조의 청크들
            }
        """
        # parent_id로 그룹화
        article_groups = defaultdict(list)
        
        for result in chunk_results:
            parent_id = result.get('parent_id')
            if not parent_id:
                continue
            
            article_groups[parent_id].append(result)
        
        if not article_groups:
            return None
        
        # 조별 평균 점수 계산
        article_scores = []
        
        for parent_id, chunks in article_groups.items():
            # 평균 점수
            avg_score = sum(c.get('score', 0.0) for c in chunks) / len(chunks)
            
            # 제목 추출
            title = chunks[0].get('title', '') if chunks else ''
            
            article_scores.append({
                'parent_id': parent_id,
                'title': title,
                'score': avg_score,
                'chunks': chunks
            })
        
        # 최고 점수 조 선택
        best_article = max(article_scores, key=lambda x: x['score'])
        
        return best_article
    
    def _aggregate_sub_item_results(
        self,
        sub_item_results: List[Dict]
    ) -> List[Dict]:
        """
        하위항목별 매칭 결과를 조 단위로 집계
        
        같은 조를 선택한 하위항목들의 점수를 평균내고,
        다른 조를 선택한 경우 모두 결과에 포함
        
        Args:
            sub_item_results: 하위항목별 매칭 결과
            
        Returns:
            조 단위 집계 결과 (점수 순 정렬)
        """
        # 조별로 그룹화
        article_groups = defaultdict(list)
        
        for result in sub_item_results:
            article_id = result['matched_article_id']
            article_groups[article_id].append(result)
        
        # 조별 평균 점수 계산
        article_scores = []
        
        for article_id, results in article_groups.items():
            # 평균 점수
            avg_score = sum(r['score'] for r in results) / len(results)
            
            # 제목 (첫 번째 결과에서)
            title = results[0]['matched_article_title']
            
            # 매칭된 하위항목 인덱스
            matched_sub_items = [r['sub_item_index'] for r in results]
            
            # 모든 청크 수집 (중복 제거)
            all_chunks = []
            seen_chunk_ids = set()
            for r in results:
                for chunk in r['matched_chunks']:
                    chunk_id = chunk.get('chunk', {}).get('id')
                    if chunk_id and chunk_id not in seen_chunk_ids:
                        all_chunks.append(chunk)
                        seen_chunk_ids.add(chunk_id)
            
            article_scores.append({
                'parent_id': article_id,
                'title': title,
                'score': avg_score,
                'matched_sub_items': matched_sub_items,
                'num_sub_items': len(results),
                'matched_chunks': all_chunks
            })
        
        # 점수 순 정렬
        article_scores.sort(key=lambda x: x['score'], reverse=True)
        
        logger.debug(f"    조 단위 집계 완료: {len(article_scores)}개 조")
        for i, article in enumerate(article_scores, 1):
            logger.debug(f"      {i}. {article['parent_id']}: {article['score']:.3f} (하위항목: {article['num_sub_items']}개)")
        
        return article_scores
    
    def _build_article_chunk_count_map(self, contract_type: str):
        """
        각 조별 하위항목 개수를 미리 계산하여 캐싱
        
        구조: {contract_type: {parent_id: count}}
        예: {'provide': {'제1조': 1, '제2조': 6, '제3조': 4, ...}}
        """
        logger.info(f"  조별 청크 개수 캐싱 중: {contract_type}")
        
        try:
            # KnowledgeBaseLoader를 통해 chunks 데이터 로드
            chunks = self.kb_loader.load_chunks(contract_type)
            
            if not chunks:
                logger.warning(f"    청크 데이터를 로드할 수 없습니다")
                self.article_chunk_counts[contract_type] = {}
                return
            
            # parent_id별 개수 계산
            parent_ids = [chunk.get('parent_id') for chunk in chunks if chunk.get('parent_id')]
            count_map = dict(Counter(parent_ids))
            
            self.article_chunk_counts[contract_type] = count_map
            
            logger.info(f"    캐싱 완료: {len(count_map)}개 조")
            
        except Exception as e:
            logger.error(f"    청크 개수 캐싱 실패: {e}")
            self.article_chunk_counts[contract_type] = {}
    
    def load_full_article_chunks(
        self,
        parent_id: str,
        contract_type: str
    ) -> List[Dict]:
        """
        표준계약서 조의 모든 청크 로드
        
        해당 조에 속한 모든 하위항목 청크 반환 (조 본문 포함)
        """
        logger.debug(f"  조 청크 로드: {parent_id}")
        
        try:
            # KnowledgeBaseLoader를 통해 chunks 로드
            chunks = self.kb_loader.load_chunks(contract_type)
            
            if not chunks:
                logger.warning(f"    청크 데이터 로드 실패: {contract_type}")
                return []
            
            # 해당 parent_id의 청크만 필터링
            article_chunks = [
                chunk for chunk in chunks
                if chunk.get('parent_id') == parent_id
            ]
            
            # order_index로 정렬 (있는 경우)
            article_chunks.sort(key=lambda x: x.get('order_index', 0))
            
            logger.debug(f"    로드 완료: {len(article_chunks)}개 청크")
            return article_chunks
            
        except Exception as e:
            logger.error(f"    조 청크 로드 실패: {e}")
            return []
