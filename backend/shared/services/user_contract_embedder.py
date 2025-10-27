"""
사용자 계약서 임베딩 서비스
backend/shared/services/embedding_service.py 재사용
"""

import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class UserContractEmbedder:
    """
    사용자 계약서 임베딩 생성
    EmbeddingService를 래핑하여 사용
    """
    
    def __init__(self, embedding_service):
        """
        초기화
        
        Args:
            embedding_service: EmbeddingService 인스턴스
        """
        self.embedding_service = embedding_service
    
    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        청크 리스트에 임베딩 추가
        
        Args:
            chunks: 청크 리스트
            
        Returns:
            임베딩이 추가된 청크 리스트
        """
        logger.info(f"사용자 계약서 임베딩 생성 시작: {len(chunks)}개 청크")
        
        # text_norm 추출
        texts = [chunk['text_norm'] for chunk in chunks]
        
        # 배치 임베딩 생성
        embeddings = self.embedding_service.generate_embeddings_batch(texts)
        
        # 청크에 임베딩 추가
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding
        
        logger.info(f"임베딩 생성 완료: {len(chunks)}개")
        
        return chunks
    
    def save_embeddings(self, chunks: List[Dict[str, Any]], output_path: str):
        """
        임베딩을 NumPy 배열로 저장
        
        Args:
            chunks: 임베딩이 포함된 청크 리스트
            output_path: 저장 경로 (확장자 제외)
        """
        from pathlib import Path
        import json
        
        # 임베딩 추출
        embeddings = [chunk['embedding'] for chunk in chunks]
        embeddings_array = np.array(embeddings)
        
        # NumPy 배열 저장
        np.save(f"{output_path}.npy", embeddings_array)
        
        # 메타데이터 저장 (임베딩 제외)
        metadata = []
        for chunk in chunks:
            meta = {k: v for k, v in chunk.items() if k != 'embedding'}
            metadata.append(meta)
        
        with open(f"{output_path}_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"임베딩 저장 완료: {output_path}")
