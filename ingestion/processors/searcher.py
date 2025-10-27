"""
하이브리드 검색기 (Hybrid Searcher)
BM25 + 벡터 유사도 결합 하이브리드 검색 모듈
"""

import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict

import numpy as np
import faiss
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    하이브리드 검색기 클래스

    Multi-Chunk Dense Retrieval + BM25 Sparse Retrieval 결합
    - Dense: FAISS 벡터 유사도 검색
    - Sparse: Whoosh BM25 키워드 검색
    - Fusion: 정규화 + 가중합
    """

    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        embedding_model: str = "text-embedding-3-large",
        api_version: str = "2024-02-01",
        dense_weight: float = 0.7
    ):
        """
        Args:
            api_key: Azure OpenAI API 키
            azure_endpoint: Azure OpenAI 엔드포인트
            embedding_model: 사용할 임베딩 모델
            api_version: Azure OpenAI API 버전
            dense_weight: Dense 검색 가중치 (0~1), Sparse는 1-dense_weight
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        self.embedding_model = embedding_model
        self.dense_weight = dense_weight
        self.sparse_weight = 1.0 - dense_weight

        # FAISS 인덱스 및 메타데이터
        self.faiss_index = None
        self.chunks = None

        # Whoosh 인덱서
        self.whoosh_indexer = None

    def load_indexes(
        self,
        faiss_index_dir: Path,
        whoosh_index_dir: Path,
        index_name: str
    ) -> bool:
        """
        FAISS 및 Whoosh 인덱스 로드

        Args:
            faiss_index_dir: FAISS 인덱스 디렉토리
            whoosh_index_dir: Whoosh 인덱스 디렉토리
            index_name: 인덱스 이름 (확장자 제외)

        Returns:
            성공 여부
        """
        try:
            # 1. FAISS 인덱스 로드
            logger.info("=" * 60)
            logger.info(" 인덱스 로드 중...")
            logger.info("=" * 60)

            faiss_path = faiss_index_dir / f"{index_name}.faiss"
            if not faiss_path.exists():
                logger.error(f"   [ERROR] FAISS 인덱스를 찾을 수 없습니다: {faiss_path}")
                return False

            self.faiss_index = faiss.read_index(str(faiss_path))
            logger.info(f"  [FAISS] 인덱스 로드 완료")
            logger.info(f"    - 벡터 수: {self.faiss_index.ntotal}")
            logger.info(f"    - 차원: {self.faiss_index.d}")

            # 2. 청크 메타데이터 로드
            chunks_path = faiss_index_dir / f"{index_name}_chunks.pkl"
            if chunks_path.exists():
                with open(chunks_path, 'rb') as f:
                    self.chunks = pickle.load(f)
                logger.info(f"  [FAISS] 청크 메타데이터 로드: {len(self.chunks)}개")
            else:
                # chunks.json 파일에서 로드 시도
                chunks_json_path = Path(str(faiss_index_dir).replace('search_indexes/faiss', 'data/chunked_documents')) / f"{index_name}_chunks.json"
                if chunks_json_path.exists():
                    with open(chunks_json_path, 'r', encoding='utf-8') as f:
                        self.chunks = json.load(f)
                    logger.info(f"  [FAISS] 청크 메타데이터 로드 (JSON): {len(self.chunks)}개")
                else:
                    logger.error(f"   [ERROR] 청크 메타데이터를 찾을 수 없습니다")
                    return False

            # 3. Whoosh 인덱스 로드
            whoosh_path = whoosh_index_dir / index_name
            if not whoosh_path.exists():
                logger.error(f"   [ERROR] Whoosh 인덱스를 찾을 수 없습니다: {whoosh_path}")
                return False

            from ingestion.indexers.whoosh_indexer import WhooshIndexer
            self.whoosh_indexer = WhooshIndexer(whoosh_path)
            logger.info(f"  [Whoosh] 인덱스 로드 완료: {whoosh_path.name}")

            logger.info("=" * 60)
            logger.info(" 인덱스 로드 성공")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"   [ERROR] 인덱스 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    def embed_query(self, query: str) -> np.ndarray:
        """
        쿼리를 임베딩 벡터로 변환

        Args:
            query: 검색 쿼리

        Returns:
            임베딩 벡터 (numpy array)
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            embedding = response.data[0].embedding
            return np.array([embedding], dtype=np.float32)

        except Exception as e:
            logger.error(f"   [ERROR] 쿼리 임베딩 실패: {e}")
            raise

    def dense_search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Dense 검색 (FAISS 벡터 유사도)

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수

        Returns:
            검색 결과 리스트 (청크 + 유사도)
        """
        if self.faiss_index is None or self.chunks is None:
            logger.error("   [ERROR] FAISS 인덱스가 로드되지 않았습니다")
            return []

        try:
            # 쿼리 임베딩
            query_vector = self.embed_query(query)

            # FAISS 검색 (L2 거리)
            distances, indices = self.faiss_index.search(query_vector, min(top_k, self.faiss_index.ntotal))

            # 결과 구성
            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    # L2 거리를 유사도로 변환: similarity = 1 / (1 + distance)
                    similarity = 1.0 / (1.0 + float(distance))

                    results.append({
                        'chunk': chunk,
                        'score': similarity,
                        'source': 'dense'
                    })

            return results

        except Exception as e:
            logger.error(f"   [ERROR] Dense 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def sparse_search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Sparse 검색 (Whoosh BM25)

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수

        Returns:
            검색 결과 리스트 (청크 + BM25 점수)
        """
        if self.whoosh_indexer is None:
            logger.error("   [ERROR] Whoosh 인덱스가 로드되지 않았습니다")
            return []

        try:
            # Whoosh BM25 검색
            whoosh_results = self.whoosh_indexer.search(query, top_k=top_k)

            # 결과 변환
            results = []
            for hit in whoosh_results:
                # Whoosh 결과를 청크 형식으로 변환
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
                    'anchors': hit['anchors']
                }

                results.append({
                    'chunk': chunk,
                    'score': hit['score'],
                    'source': 'sparse',
                    'highlights': hit.get('highlights', '')
                })

            return results

        except Exception as e:
            logger.error(f"   [ERROR] Sparse 검색 실패: {e}")
            import traceback
            traceback.print_exc()
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

        # 모든 점수가 같은 경우 처리
        if max_score == min_score:
            for r in results:
                r['normalized_score'] = 1.0
            return results

        # Min-Max 정규화
        for r in results:
            r['normalized_score'] = (r['score'] - min_score) / (max_score - min_score)

        return results

    def aggregate_by_parent(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        청크 결과를 parent_id(조) 단위로 그룹화

        Args:
            results: 검색 결과 리스트

        Returns:
            parent_id별로 그룹화된 딕셔너리
        """
        grouped = defaultdict(list)

        for result in results:
            chunk = result['chunk']
            parent_id = chunk.get('parent_id', chunk.get('id'))
            grouped[parent_id].append(result)

        return grouped

    def fuse_scores(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Dense와 Sparse 검색 결과를 융합

        Args:
            dense_results: Dense 검색 결과
            sparse_results: Sparse 검색 결과

        Returns:
            융합된 검색 결과 리스트
        """
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
                'sparse_score': 0.0,
                'highlights': ''
            }

        # Sparse 결과 추가/병합
        for result in sparse_normalized:
            chunk_id = result['chunk']['id']
            if chunk_id in chunk_scores:
                chunk_scores[chunk_id]['sparse_score'] = result['normalized_score']
                chunk_scores[chunk_id]['highlights'] = result.get('highlights', '')
            else:
                chunk_scores[chunk_id] = {
                    'chunk': result['chunk'],
                    'dense_score': 0.0,
                    'sparse_score': result['normalized_score'],
                    'highlights': result.get('highlights', '')
                }

        # 3. 가중합 계산
        fused_results = []
        for chunk_id, data in chunk_scores.items():
            final_score = (
                self.dense_weight * data['dense_score'] +
                self.sparse_weight * data['sparse_score']
            )

            fused_results.append({
                'chunk': data['chunk'],
                'dense_score': data['dense_score'],
                'sparse_score': data['sparse_score'],
                'final_score': final_score,
                'highlights': data['highlights']
            })

        # 4. 최종 점수로 정렬
        fused_results.sort(key=lambda x: x['final_score'], reverse=True)

        return fused_results

    def search(
        self,
        query: str,
        top_k: int = 10,
        aggregate_by_article: bool = True,
        dense_top_k: int = 50,
        sparse_top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 수행

        Args:
            query: 검색 쿼리
            top_k: 최종 반환할 결과 개수
            aggregate_by_article: 조 단위로 집계할지 여부
            dense_top_k: Dense 검색에서 가져올 결과 수
            sparse_top_k: Sparse 검색에서 가져올 결과 수

        Returns:
            검색 결과 리스트
        """
        if self.faiss_index is None or self.whoosh_indexer is None:
            logger.error("   [ERROR] 인덱스가 로드되지 않았습니다")
            return []

        try:
            logger.info("\n" + "=" * 60)
            logger.info(" 하이브리드 검색 시작")
            logger.info("=" * 60)
            logger.info(f"  쿼리: {query}")
            logger.info(f"  Dense 가중치: {self.dense_weight:.1f}")
            logger.info(f"  Sparse 가중치: {self.sparse_weight:.1f}")
            logger.info("")

            # 1. Dense 검색
            logger.info(f"  [1/3] Dense 검색 (FAISS) - Top {dense_top_k}")
            dense_results = self.dense_search(query, top_k=dense_top_k)
            logger.info(f"    → {len(dense_results)}개 결과")

            # 2. Sparse 검색
            logger.info(f"  [2/3] Sparse 검색 (Whoosh BM25) - Top {sparse_top_k}")
            sparse_results = self.sparse_search(query, top_k=sparse_top_k)
            logger.info(f"    → {len(sparse_results)}개 결과")

            # 3. Score Fusion
            logger.info(f"  [3/3] Score Fusion (가중합)")
            fused_results = self.fuse_scores(dense_results, sparse_results)
            logger.info(f"    → {len(fused_results)}개 융합 결과")

            # 4. 조 단위 집계 (선택적)
            if aggregate_by_article:
                logger.info(f"  [추가] 조 단위 집계 (MaxPooling)")
                fused_results = self._aggregate_results_by_article(fused_results)
                logger.info(f"    → {len(fused_results)}개 조 단위 결과")

            # 5. Top-K 선택
            final_results = fused_results[:top_k]

            logger.info("=" * 60)
            logger.info(f" 검색 완료: 상위 {len(final_results)}개 반환")
            logger.info("=" * 60)

            return final_results

        except Exception as e:
            logger.error(f"   [ERROR] 하이브리드 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _aggregate_results_by_article(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        청크 결과를 조 단위로 집계 (MaxPooling)

        Args:
            results: 융합된 검색 결과

        Returns:
            조 단위로 집계된 결과
        """
        # parent_id별로 그룹화
        grouped = defaultdict(list)
        for result in results:
            parent_id = result['chunk'].get('parent_id', result['chunk']['id'])
            grouped[parent_id].append(result)

        # 각 조에서 최고 점수 선택 (MaxPooling)
        aggregated = []
        for parent_id, group in grouped.items():
            # 최고 점수 결과 선택
            best_result = max(group, key=lambda x: x['final_score'])

            # 같은 조의 모든 청크 정보 추가
            best_result['related_chunks'] = [
                {
                    'id': r['chunk']['id'],
                    'unit_type': r['chunk'].get('unit_type', ''),
                    'score': r['final_score']
                }
                for r in group
            ]
            best_result['chunk_count'] = len(group)

            aggregated.append(best_result)

        # 점수로 재정렬
        aggregated.sort(key=lambda x: x['final_score'], reverse=True)

        return aggregated

    def display_results(self, results: List[Dict[str, Any]]):
        """
        검색 결과를 보기 좋게 출력

        Args:
            results: 검색 결과 리스트
        """
        if not results:
            logger.info("  검색 결과가 없습니다.")
            return

        logger.info(f"\n{'=' * 60}")
        logger.info(f" 검색 결과 (상위 {len(results)}개)")
        logger.info(f"{'=' * 60}\n")

        for i, result in enumerate(results, 1):
            chunk = result['chunk']

            logger.info(f"[{i}] {chunk.get('parent_id', chunk['id'])} - {chunk.get('title', 'N/A')}")
            logger.info(f"    ID: {chunk['id']}")
            logger.info(f"    타입: {chunk.get('unit_type', 'N/A')}")
            logger.info(f"    최종 점수: {result['final_score']:.4f}")
            logger.info(f"      ├─ Dense:  {result['dense_score']:.4f}")
            logger.info(f"      └─ Sparse: {result['sparse_score']:.4f}")

            # 조 단위 집계 정보
            if 'chunk_count' in result:
                logger.info(f"    관련 청크: {result['chunk_count']}개")

            # 하이라이트
            if result.get('highlights'):
                logger.info(f"    하이라이트: {result['highlights'][:100]}...")

            # 내용 미리보기
            content = chunk.get('text_norm', chunk.get('text_raw', ''))
            preview = content[:150] + '...' if len(content) > 150 else content
            logger.info(f"    내용: {preview}")
            logger.info("")

    def get_context(
        self,
        results: List[Dict[str, Any]],
        max_length: int = 3000
    ) -> str:
        """
        검색 결과를 LLM 컨텍스트용 문자열로 변환

        Args:
            results: 검색 결과 리스트
            max_length: 최대 문자 길이

        Returns:
            컨텍스트 문자열
        """
        context_parts = []
        current_length = 0

        for result in results:
            chunk = result['chunk']
            parent_id = chunk.get('parent_id', chunk['id'])
            title = chunk.get('title', '')
            content = chunk.get('text_raw', chunk.get('text_norm', ''))

            part = f"[{parent_id} - {title}]\n{content}\n\n"
            part_length = len(part)

            if current_length + part_length > max_length:
                break

            context_parts.append(part)
            current_length += part_length

        return ''.join(context_parts)
