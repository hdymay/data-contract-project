#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
임베딩 서비스 모듈

Azure OpenAI를 사용하여 텍스트 임베딩을 생성합니다.
"""

import logging
import numpy as np
from typing import List, Optional
from openai import AzureOpenAI

try:
    from backend.clause_verification.node_1_clause_matching.config import config
except ImportError:
    from .config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Azure OpenAI를 사용한 임베딩 생성 서비스
    """
    
    def __init__(self):
        """
        EmbeddingService 초기화
        """
        self.client = AzureOpenAI(
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_ENDPOINT
        )
        self.embedding_model = config.AZURE_EMBEDDING_DEPLOYMENT
        logger.info(f"EmbeddingService initialized with model: {self.embedding_model}")
    
    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        텍스트에 대한 임베딩 생성
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            임베딩 벡터 (numpy array) 또는 None (실패 시)
        """
        try:
            # 텍스트 전처리
            text = text.strip().replace('\n', ' ')
            if not text:
                logger.warning("Empty text provided for embedding")
                return None
            
            # Azure OpenAI API 호출
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            
            # 임베딩 벡터 추출
            embedding = np.array(response.data[0].embedding, dtype=np.float32)
            
            logger.debug(f"Generated embedding for text: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        여러 텍스트에 대한 임베딩 일괄 생성
        
        Args:
            texts: 임베딩을 생성할 텍스트 리스트
            
        Returns:
            임베딩 벡터 리스트
        """
        embeddings = []
        
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        
        logger.info(f"Generated {len([e for e in embeddings if e is not None])} embeddings out of {len(texts)} texts")
        return embeddings
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        여러 텍스트에 대한 임베딩 일괄 생성 (별칭 메서드)
        
        Args:
            texts: 임베딩을 생성할 텍스트 리스트
            
        Returns:
            임베딩 벡터 리스트
        """
        return self.generate_embeddings_batch(texts)
    
    def get_embedding_dimension(self) -> int:
        """
        임베딩 차원 수 반환
        
        Returns:
            임베딩 벡터의 차원 수
        """
        # text-embedding-3-large의 차원은 3072
        return 3072
