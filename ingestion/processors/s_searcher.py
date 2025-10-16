"""
간이 검색기 (Simple Searcher)
FAISS 인덱스를 사용한 유사도 검색
"""

import json
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class SimpleSearcher:
    """
    간이 검색기 클래스
    FAISS 인덱스를 로드하고 쿼리에 대한 유사 청크를 검색
    """
    
    def __init__(
        self, 
        api_key: str, 
        azure_endpoint: str,
        embedding_model: str = "text-embedding-3-large",
        api_version: str = "2024-02-01"
    ):
        """
        Args:
            api_key: Azure OpenAI API 키
            azure_endpoint: Azure OpenAI 엔드포인트
            embedding_model: 사용할 임베딩 모델 (Azure deployment name)
            api_version: Azure OpenAI API 버전
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        self.embedding_model = embedding_model
        self.index = None
        self.chunks = None
        self.metadata = None
    
    def load_index(self, index_dir: Path, index_name: str) -> bool:
        """
        FAISS 인덱스와 메타데이터 로드
        
        Args:
            index_dir: 인덱스 디렉토리
            index_name: 인덱스 이름 (확장자 제외)
            
        Returns:
            성공 여부
        """
        try:
            # FAISS 인덱스 로드
            index_path = index_dir / f"{index_name}.faiss"
            if not index_path.exists():
                logger.error(f"   [ERROR] FAISS 인덱스를 찾을 수 없습니다: {index_path}")
                return False
            
            self.index = faiss.read_index(str(index_path))
            logger.info(f"  FAISS 인덱스 로드: {index_path.name}")
            logger.info(f"    - 벡터 수: {self.index.ntotal}")
            logger.info(f"    - 차원: {self.index.d}")
            
            # 청크 데이터 로드
            chunks_path = index_dir / f"{index_name}_chunks.pkl"
            if chunks_path.exists():
                with open(chunks_path, 'rb') as f:
                    self.chunks = pickle.load(f)
                logger.info(f"  청크 데이터 로드: {len(self.chunks)}개")
            else:
                logger.warning(f"  청크 데이터를 찾을 수 없습니다: {chunks_path}")
            
            # 메타데이터 로드 (선택사항)
            metadata_path = index_dir / f"{index_name}_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            
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
    
    def search(
        self, 
        query: str, 
        top_k: int = 5
    ) -> List[Tuple[Dict, float]]:
        """
        쿼리로 유사한 청크 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수
            
        Returns:
            (청크, 거리) 튜플의 리스트
        """
        if self.index is None:
            logger.error("   [ERROR] 인덱스가 로드되지 않았습니다")
            return []
        
        try:
            # 쿼리 임베딩
            logger.info(f"\n  쿼리: {query}")
            query_vector = self.embed_query(query)
            
            # FAISS 검색
            distances, indices = self.index.search(query_vector, top_k)
            
            # 결과 구성
            results = []
            for i, (idx, distance) in enumerate(zip(indices[0], distances[0])):
                if idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    results.append((chunk, float(distance)))
            
            return results
        
        except Exception as e:
            logger.error(f"   [ERROR] 검색 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def display_results(self, results: List[Tuple[Dict, float]]):
        """
        검색 결과를 보기 좋게 출력
        
        Args:
            results: (청크, 거리) 튜플의 리스트
        """
        if not results:
            logger.info("  검색 결과가 없습니다.")
            return
        
        logger.info(f"\n  === 검색 결과 (상위 {len(results)}개) ===\n")
        
        for i, (chunk, distance) in enumerate(results, 1):
            logger.info(f"  [{i}] 거리: {distance:.4f}")
            logger.info(f"      제목: {chunk.get('title', 'N/A')}")
            logger.info(f"      타입: {chunk.get('type', 'N/A')} {chunk.get('number', '')}")
            
            # 내용 미리보기 (처음 200자)
            content = chunk.get('content', '')
            preview = content[:200] + '...' if len(content) > 200 else content
            logger.info(f"      내용: {preview}")
            logger.info("")
    
    def get_context(self, results: List[Tuple[Dict, float]], max_length: int = 2000) -> str:
        """
        검색 결과를 LLM 컨텍스트용 문자열로 변환
        
        Args:
            results: (청크, 거리) 튜플의 리스트
            max_length: 최대 문자 길이
            
        Returns:
            컨텍스트 문자열
        """
        context_parts = []
        current_length = 0
        
        for chunk, distance in results:
            title = chunk.get('title', '')
            content = chunk.get('content', '')
            
            part = f"[{title}]\n{content}\n\n"
            part_length = len(part)
            
            if current_length + part_length > max_length:
                break
            
            context_parts.append(part)
            current_length += part_length
        
        return ''.join(context_parts)

