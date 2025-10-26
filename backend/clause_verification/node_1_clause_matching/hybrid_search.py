"""
Hybrid Search Engine for Contract Clause Verification System

이 모듈은 BM25 키워드 검색과 FAISS 벡터 검색을 결합한 하이브리드 검색 엔진을 제공합니다.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np

try:
    import faiss
except ImportError:
    raise ImportError("faiss-cpu is required. Install it with: pip install faiss-cpu")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank-bm25 is required. Install it with: pip install rank-bm25")

try:
    from backend.clause_verification.node_1_clause_matching.models import ClauseData
    from backend.clause_verification.node_1_clause_matching.config import config
except ImportError:
    from models import ClauseData
    from config import config

# Configure logging
logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    BM25와 FAISS를 결합한 하이브리드 검색 엔진
    
    BM25는 키워드 기반 검색을, FAISS는 의미론적 유사도 검색을 수행하며,
    두 점수를 가중치를 적용하여 결합합니다.
    
    Attributes:
        bm25_weight: BM25 점수 가중치 (기본값: 0.2)
        faiss_weight: FAISS 점수 가중치 (기본값: 0.8)
        clauses: 인덱싱된 조문 리스트
        bm25_index: BM25 인덱스
        faiss_index: FAISS 인덱스
    """
    
    def __init__(
        self,
        faiss_index_path: Optional[Path] = None,
        bm25_weight: float = 0.2,
        faiss_weight: float = 0.8
    ):
        """
        하이브리드 검색 엔진 초기화
        
        Args:
            faiss_index_path: FAISS 인덱스 저장 경로 (None인 경우 config에서 로드)
            bm25_weight: BM25 점수 가중치 (기본값: 0.2)
            faiss_weight: FAISS 점수 가중치 (기본값: 0.8)
        
        Raises:
            ValueError: 가중치 합이 1.0이 아닌 경우
        """
        if abs(bm25_weight + faiss_weight - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0, got {bm25_weight + faiss_weight}"
            )
        
        self.bm25_weight = bm25_weight
        self.faiss_weight = faiss_weight
        
        # Set paths
        if faiss_index_path is None:
            faiss_index_path = config.VECTORSTORE_PATH / "faiss"
        self.faiss_index_path = faiss_index_path
        
        # 디렉토리 생성 (이미 존재하면 건너뜀)
        try:
            if not self.faiss_index_path.exists():
                self.faiss_index_path.mkdir(parents=True, exist_ok=True)
            elif not self.faiss_index_path.is_dir():
                # 파일로 존재하는 경우 삭제하고 디렉토리 생성
                logger.warning(f"Removing file at {self.faiss_index_path} to create directory")
                self.faiss_index_path.unlink()
                self.faiss_index_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create directory {self.faiss_index_path}: {e}")
        
        # Initialize indices
        self.clauses: List[ClauseData] = []
        self.bm25_index: Optional[BM25Okapi] = None
        self.faiss_index: Optional[faiss.Index] = None
        self.dimension: Optional[int] = None
        
        logger.info(
            f"Hybrid search engine initialized (BM25: {bm25_weight}, FAISS: {faiss_weight})"
        )
    
    def build_faiss_index(self, clauses: List[ClauseData]) -> None:
        """
        FAISS 인덱스 구축
        
        Args:
            clauses: 임베딩이 포함된 조문 리스트
        
        Raises:
            ValueError: 임베딩이 없는 조문이 있는 경우
        """
        if not clauses:
            raise ValueError("Cannot build FAISS index with empty clause list")
        
        # Store clauses
        self.clauses = clauses
        
        # Validate that all clauses have embeddings
        missing_embeddings = [c.id for c in clauses if c.embedding is None]
        if missing_embeddings:
            raise ValueError(
                f"Clauses missing embeddings: {missing_embeddings[:5]}... "
                f"({len(missing_embeddings)} total)"
            )
        
        # Extract embeddings
        embeddings = np.array([c.embedding for c in clauses], dtype=np.float32)
        
        # Set dimension from first embedding
        self.dimension = embeddings.shape[1]
        
        # Create FAISS index (using L2 distance)
        self.faiss_index = faiss.IndexFlatL2(self.dimension)
        
        # Add vectors to index
        self.faiss_index.add(embeddings)
        
        logger.info(
            f"Built FAISS index with {len(clauses)} clauses (dimension: {self.dimension})"
        )
    
    def save_faiss_index(self, index_name: Optional[str] = None) -> Path:
        """
        FAISS 인덱스와 BM25 인덱스를 디스크에 저장
        
        Args:
            index_name: 인덱스 이름 (None인 경우 config에서 로드)
        
        Returns:
            저장된 인덱스 파일 경로
        
        Raises:
            ValueError: 인덱스가 구축되지 않은 경우
        """
        if self.faiss_index is None:
            raise ValueError("FAISS index not built. Call build_faiss_index() first.")
        
        if index_name is None:
            index_name = config.FAISS_INDEX_NAME
        
        # Save FAISS index
        index_file = self.faiss_index_path / f"{index_name}.index"
        faiss.write_index(self.faiss_index, str(index_file))
        
        # Save metadata (clauses, dimension, and BM25 index)
        metadata_file = self.faiss_index_path / f"{index_name}.metadata"
        metadata = {
            "clauses": [c.to_dict() for c in self.clauses],
            "dimension": self.dimension,
            "bm25_index": self.bm25_index,  # BM25 인덱스도 저장
        }
        with open(metadata_file, "wb") as f:
            pickle.dump(metadata, f)
        
        logger.info(f"Saved FAISS index and BM25 index to {index_file}")
        return index_file
    
    def load_faiss_index(self, index_name: Optional[str] = None) -> bool:
        """
        디스크에서 FAISS 인덱스와 BM25 인덱스 로드
        
        Args:
            index_name: 인덱스 이름 (None인 경우 config에서 로드)
        
        Returns:
            로드 성공 여부 (파일이 없으면 False 반환)
        """
        if index_name is None:
            index_name = config.FAISS_INDEX_NAME
        
        index_file = self.faiss_index_path / f"{index_name}.index"
        metadata_file = self.faiss_index_path / f"{index_name}.metadata"
        
        # Check if files exist
        if not index_file.exists():
            logger.warning(f"FAISS index file not found: {index_file}")
            return False
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            return False
        
        # Load FAISS index
        self.faiss_index = faiss.read_index(str(index_file))
        
        # Load metadata
        with open(metadata_file, "rb") as f:
            metadata = pickle.load(f)
        
        # Restore clauses (without embeddings to save memory)
        self.clauses = [
            ClauseData(
                id=c["id"],
                title=c["title"],
                subtitle=c.get("subtitle"),
                type=c["type"],
                text=c["text"],
                embedding=None  # Don't load embeddings to save memory
            )
            for c in metadata["clauses"]
        ]
        self.dimension = metadata["dimension"]
        
        # Load BM25 index if available
        if "bm25_index" in metadata and metadata["bm25_index"] is not None:
            self.bm25_index = metadata["bm25_index"]
            logger.info(
                f"Loaded FAISS and BM25 indices from {index_file} "
                f"({len(self.clauses)} clauses, dimension: {self.dimension})"
            )
        else:
            logger.info(
                f"Loaded FAISS index from {index_file} "
                f"({len(self.clauses)} clauses, dimension: {self.dimension})"
            )
            logger.warning("BM25 index not found in metadata. You may need to rebuild it.")
        
        return True

    def build_bm25_index(self, clauses: List[ClauseData]) -> None:
        """
        BM25 인덱스 구축 (키워드 기반)
        
        Args:
            clauses: 조문 리스트
        """
        if not clauses:
            raise ValueError("Cannot build BM25 index with empty clause list")
        
        # Store clauses if not already stored
        if not self.clauses:
            self.clauses = clauses
        
        # Tokenize clause texts (simple whitespace tokenization)
        # For better Korean support, consider using konlpy or similar
        # Use text_norm for better search accuracy
        tokenized_corpus = [clause.text_norm.split() for clause in clauses]
        
        # Build BM25 index
        self.bm25_index = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Built BM25 index with {len(clauses)} clauses")
    
    def get_bm25_scores(self, query_text: str) -> np.ndarray:
        """
        BM25 점수 계산
        
        Args:
            query_text: 검색 쿼리 텍스트
        
        Returns:
            각 조문에 대한 BM25 점수 배열
        
        Raises:
            ValueError: BM25 인덱스가 구축되지 않은 경우
        """
        if self.bm25_index is None:
            raise ValueError("BM25 index not built. Call build_bm25_index() first.")
        
        # Tokenize query
        tokenized_query = query_text.split()
        
        # Get BM25 scores
        scores = self.bm25_index.get_scores(tokenized_query)
        
        return scores
    
    def get_faiss_scores(
        self, 
        query_embedding: List[float], 
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        FAISS 유사도 점수 계산
        
        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 최대 결과 수
        
        Returns:
            (인덱스, 거리) 튜플 리스트 (거리가 작을수록 유사)
        
        Raises:
            ValueError: FAISS 인덱스가 구축되지 않은 경우
        """
        if self.faiss_index is None:
            raise ValueError("FAISS index not built. Call build_faiss_index() or load_faiss_index() first.")
        
        # Convert to numpy array
        query_vector = np.array([query_embedding], dtype=np.float32)
        
        # Search FAISS index (returns distances and indices)
        distances, indices = self.faiss_index.search(query_vector, top_k)
        
        # Return as list of tuples
        results = [(int(idx), float(dist)) for idx, dist in zip(indices[0], distances[0])]
        
        return results
    
    def search(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[int, float, float, float, float, float]]:
        """
        하이브리드 검색 수행 (BM25 + FAISS 점수 결합)
        
        Args:
            query_text: 검색 쿼리 텍스트
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 최대 결과 수
        
        Returns:
            (인덱스, 결합점수, BM25점수, FAISS점수, BM25원점수, FAISS거리) 튜플 리스트
        
        Raises:
            ValueError: 인덱스가 구축되지 않은 경우
        """
        if self.bm25_index is None or self.faiss_index is None:
            raise ValueError(
                "Both BM25 and FAISS indices must be built. "
                "Call build_bm25_index() and build_faiss_index() first."
            )
        
        # Get BM25 scores (higher is better)
        bm25_scores = self.get_bm25_scores(query_text)
        
        # Normalize BM25 scores to [0, 1]
        max_bm25 = np.max(bm25_scores) if np.max(bm25_scores) > 0 else 1.0
        normalized_bm25 = bm25_scores / max_bm25
        
        # Get FAISS scores (lower distance is better, so we need to convert)
        faiss_results = self.get_faiss_scores(query_embedding, top_k=len(self.clauses))
        
        # Store FAISS distances for raw score output
        faiss_distances = np.zeros(len(self.clauses))
        for idx, distance in faiss_results:
            faiss_distances[idx] = distance
        
        # Convert FAISS L2 distances to similarity scores
        # For L2 distance, smaller is better. Use exponential decay for more intuitive scoring:
        # similarity = exp(-distance^2 / 2) for better discrimination
        faiss_scores = np.zeros(len(self.clauses))
        for idx, distance in faiss_results:
            # Use exponential decay: closer to 0 for distant vectors, closer to 1 for similar vectors
            # This gives more intuitive results: distance 0.0 → 1.0, distance 1.0 → 0.61, distance 2.0 → 0.02
            faiss_scores[idx] = np.exp(-(distance ** 2) / 2.0)
        
        # Normalize FAISS scores to [0, 1]
        max_faiss = np.max(faiss_scores) if np.max(faiss_scores) > 0 else 1.0
        min_faiss = np.min(faiss_scores)
        if max_faiss > min_faiss:
            normalized_faiss = (faiss_scores - min_faiss) / (max_faiss - min_faiss)
        else:
            normalized_faiss = faiss_scores / max_faiss
        
        # Combine scores with weights
        hybrid_scores = (
            self.bm25_weight * normalized_bm25 + 
            self.faiss_weight * normalized_faiss
        )
        
        # Get top-k results with individual scores (including raw scores)
        top_indices = np.argsort(hybrid_scores)[::-1][:top_k]
        results = [
            (
                int(idx), 
                float(hybrid_scores[idx]),
                float(normalized_bm25[idx]),
                float(normalized_faiss[idx]),
                float(bm25_scores[idx]),  # BM25 원점수
                float(faiss_distances[idx])  # FAISS L2 거리
            ) 
            for idx in top_indices
        ]
        
        logger.debug(
            f"Hybrid search completed: query='{query_text[:50]}...', "
            f"top_k={top_k}, best_score={results[0][1]:.4f}"
        )
        
        return results
    
    def get_clause_by_index(self, index: int) -> ClauseData:
        """
        인덱스로 조문 조회
        
        Args:
            index: 조문 인덱스
        
        Returns:
            조문 데이터
        
        Raises:
            IndexError: 인덱스가 범위를 벗어난 경우
        """
        if index < 0 or index >= len(self.clauses):
            raise IndexError(f"Index {index} out of range [0, {len(self.clauses)})")
        
        return self.clauses[index]
