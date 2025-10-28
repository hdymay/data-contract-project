"""
HybridSearcher for Consistency Agent
FAISS + Whoosh 하이브리드 검색 (0.85 / 0.15 가중치)
"""

import logging
import numpy as np
from typing import List, Dict, Any
from collections import defaultdict
from openai import AzureOpenAI
from backend.shared.database import SessionLocal, TokenUsage

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    하이브리드 검색기
    
    - Dense: FAISS 벡터 유사도 검색 (가중치 0.85)
    - Sparse: Whoosh BM25 키워드 검색 (가중치 0.15)
    - Fusion: 정규화 + 가중합
    """
    
    def __init__(
        self,
        azure_client: AzureOpenAI,
        embedding_model: str = "text-embedding-3-large",
        dense_weight: float = 0.85
    ):
        """
        Args:
            azure_client: Azure OpenAI 클라이언트
            embedding_model: 임베딩 모델명
            dense_weight: Dense 검색 가중치 (기본 0.85)
        """
        self.client = azure_client
        self.embedding_model = embedding_model
        self.dense_weight = dense_weight
        self.sparse_weight = 1.0 - dense_weight
        
        # 로드된 인덱스
        self.faiss_index = None
        self.chunks = None
        self.whoosh_indexer = None
        
        logger.info(f"HybridSearcher 초기화 (Dense: {dense_weight:.2f}, Sparse: {self.sparse_weight:.2f})")
    
    def load_indexes(
        self,
        faiss_index,
        chunks: List[Dict],
        whoosh_indexer
    ):
        """
        인덱스 로드
        
        Args:
            faiss_index: FAISS 인덱스
            chunks: 청크 메타데이터 리스트
            whoosh_indexer: Whoosh 인덱서
        """
        self.faiss_index = faiss_index
        self.chunks = chunks
        self.whoosh_indexer = whoosh_indexer
        
        logger.info(f"인덱스 로드 완료: {len(chunks)} chunks")
    
    def embed_query(self, query: str, contract_id: str = None) -> np.ndarray:
        """
        쿼리를 임베딩 벡터로 변환

        Args:
            query: 검색 쿼리
            contract_id: 계약서 ID (토큰 로깅용)

        Returns:
            임베딩 벡터 (numpy array)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query
            )

            # 토큰 사용량 로깅
            if hasattr(response, 'usage') and response.usage and contract_id:
                self._log_token_usage(
                    contract_id=contract_id,
                    api_type="embedding",
                    model=self.embedding_model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=0,
                    total_tokens=response.usage.total_tokens,
                    extra_info={"purpose": "article_matching_query"}
                )

            embedding = response.data[0].embedding
            return np.array([embedding], dtype=np.float32)

        except Exception as e:
            logger.error(f"쿼리 임베딩 실패: {e}")
            raise
    
    def dense_search(self, query: str, top_k: int = 50, contract_id: str = None) -> List[Dict[str, Any]]:
        """
        Dense 검색 (FAISS 벡터 유사도)

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수
            contract_id: 계약서 ID (토큰 로깅용)

        Returns:
            검색 결과 리스트
        """
        if self.faiss_index is None or self.chunks is None:
            logger.error("FAISS 인덱스가 로드되지 않았습니다")
            return []

        try:
            # 쿼리 임베딩
            query_vector = self.embed_query(query, contract_id)
            
            # FAISS 검색
            distances, indices = self.faiss_index.search(
                query_vector,
                min(top_k, self.faiss_index.ntotal)
            )
            
            # 결과 구성
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    # L2 거리를 유사도로 변환
                    similarity = 1.0 / (1.0 + float(distance))
                    
                    results.append({
                        'chunk': chunk,
                        'score': similarity,
                        'source': 'dense'
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Dense 검색 실패: {e}")
            return []
    
    def sparse_search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Sparse 검색 (Whoosh BM25)

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수

        Returns:
            검색 결과 리스트
        """
        if self.whoosh_indexer is None:
            logger.error("Whoosh 인덱스가 로드되지 않았습니다")
            return []

        try:
            # Whoosh BM25 검색
            whoosh_results = self.whoosh_indexer.search(query, top_k=top_k)

            # 진단: 검색 결과 개수 및 점수 범위
            if not whoosh_results:
                logger.warning(f"Sparse 검색 결과 없음 (쿼리 길이: {len(query)})")
                logger.debug(f"  쿼리 미리보기: {query[:200]}...")
                return []

            scores = [hit['score'] for hit in whoosh_results]
            logger.debug(f"Sparse 검색 완료: {len(whoosh_results)}개, 점수 범위 [{min(scores):.4f} ~ {max(scores):.4f}]")

            # 결과 변환
            results = []
            for hit in whoosh_results:
                chunk = {
                    'id': hit['id'],
                    'global_id': hit['global_id'],
                    'unit_type': hit['unit_type'],
                    'parent_id': hit['parent_id'],
                    'title': hit['title'],
                    'text_raw': hit['text_raw'],
                    'text_norm': hit['text_norm'],
                    'source_file': hit['source_file'],
                    'order_index': hit['order_index'],
                    'anchors': hit.get('anchors', [])
                }

                results.append({
                    'chunk': chunk,
                    'score': hit['score'],
                    'source': 'sparse'
                })

            return results

        except Exception as e:
            logger.error(f"Sparse 검색 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def normalize_scores(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과 점수를 Min-Max 정규화 (0~1 범위)
        
        Args:
            results: 검색 결과 리스트
            
        Returns:
            정규화된 검색 결과 리스트
        """
        if not results:
            return results
        
        scores = [r['score'] for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        # 모든 점수가 같은 경우
        if max_score == min_score:
            for r in results:
                r['normalized_score'] = 1.0
            return results
        
        # Min-Max 정규화
        for r in results:
            r['normalized_score'] = (r['score'] - min_score) / (max_score - min_score)
        
        return results
    
    def fuse_scores(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Dense와 Sparse 검색 결과를 융합

        Adaptive Weighting:
        - Sparse 결과가 없으면 자동으로 Dense 가중치를 1.0으로 조정
        - 이를 통해 0.85 상한 문제 해결

        Args:
            dense_results: Dense 검색 결과
            sparse_results: Sparse 검색 결과

        Returns:
            융합된 검색 결과 리스트
        """
        # Adaptive Weighting: Sparse 결과 부재 시 가중치 조정
        if not sparse_results and dense_results:
            logger.warning(f"Sparse 검색 결과 없음 - Adaptive Weighting 적용 (Dense: 1.0)")
            effective_dense_weight = 1.0
            effective_sparse_weight = 0.0
        else:
            effective_dense_weight = self.dense_weight
            effective_sparse_weight = self.sparse_weight

        # 1. 점수 정규화
        dense_normalized = self.normalize_scores(dense_results)
        sparse_normalized = self.normalize_scores(sparse_results)

        # 2. 청크 ID별로 결과 수집
        chunk_scores = {}

        # Dense 결과 추가
        for result in dense_normalized:
            chunk_id = result['chunk']['id']
            chunk_scores[chunk_id] = {
                'chunk': result['chunk'],
                'dense_score': result['normalized_score'],
                'sparse_score': 0.0
            }

        # Sparse 결과 추가/병합
        sparse_contribution_count = 0
        for result in sparse_normalized:
            chunk_id = result['chunk']['id']
            if chunk_id in chunk_scores:
                chunk_scores[chunk_id]['sparse_score'] = result['normalized_score']
                sparse_contribution_count += 1
            else:
                chunk_scores[chunk_id] = {
                    'chunk': result['chunk'],
                    'dense_score': 0.0,
                    'sparse_score': result['normalized_score']
                }

        # 진단: Sparse 기여도
        if sparse_results:
            overlap_rate = sparse_contribution_count / len(chunk_scores) * 100
            logger.debug(f"Sparse-Dense 중복: {sparse_contribution_count}/{len(chunk_scores)} ({overlap_rate:.1f}%)")

        # 3. 가중합 계산 (Adaptive Weighting 적용)
        fused_results = []
        for chunk_id, data in chunk_scores.items():
            final_score = (
                effective_dense_weight * data['dense_score'] +
                effective_sparse_weight * data['sparse_score']
            )

            fused_results.append({
                'chunk': data['chunk'],
                'score': final_score,
                'dense_score': data['dense_score'],
                'sparse_score': data['sparse_score'],
                'parent_id': data['chunk'].get('parent_id'),
                'title': data['chunk'].get('title')
            })

        # 4. 최종 점수로 정렬
        fused_results.sort(key=lambda x: x['score'], reverse=True)

        return fused_results
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        dense_top_k: int = 50,
        sparse_top_k: int = 50,
        contract_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 수행

        Args:
            query: 검색 쿼리
            top_k: 최종 반환할 결과 개수
            dense_top_k: Dense 검색에서 가져올 결과 수
            sparse_top_k: Sparse 검색에서 가져올 결과 수
            contract_id: 계약서 ID (토큰 로깅용)

        Returns:
            검색 결과 리스트 (청크 레벨)
        """
        if self.faiss_index is None or self.whoosh_indexer is None:
            logger.error("인덱스가 로드되지 않았습니다")
            return []

        try:
            logger.debug(f"하이브리드 검색: {query[:100]}...")

            # 1. Dense 검색
            dense_results = self.dense_search(query, top_k=dense_top_k, contract_id=contract_id)
            logger.debug(f"  Dense: {len(dense_results)}개")
            
            # 2. Sparse 검색
            sparse_results = self.sparse_search(query, top_k=sparse_top_k)
            logger.debug(f"  Sparse: {len(sparse_results)}개")
            
            # 3. Score Fusion
            fused_results = self.fuse_scores(dense_results, sparse_results)
            logger.debug(f"  Fusion: {len(fused_results)}개")
            
            # 4. Top-K 선택
            final_results = fused_results[:top_k]
            
            return final_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _log_token_usage(
        self,
        contract_id: str,
        api_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        extra_info: dict = None
    ):
        """토큰 사용량을 DB에 저장"""
        try:
            db = SessionLocal()
            token_usage = TokenUsage(
                contract_id=contract_id,
                component="consistency_agent",
                api_type=api_type,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                extra_info=extra_info
            )
            db.add(token_usage)
            db.commit()
            logger.info(f"토큰 사용량 로깅: {api_type} - {total_tokens} tokens")
        except Exception as e:
            logger.error(f"토큰 사용량 로깅 실패: {e}")
        finally:
            db.close()
