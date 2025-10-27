#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공유 임베딩 서비스 모듈

Azure OpenAI를 사용하여 텍스트 임베딩을 생성합니다.
분류 에이전트와 검증 엔진에서 공통으로 사용됩니다.
"""

import os
import logging
import numpy as np
from typing import List, Optional
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Azure OpenAI를 사용한 임베딩 생성 서비스 (공유)
    """
    
    def __init__(
        self,
        api_key: str = None,
        azure_endpoint: str = None,
        embedding_model: str = "text-embedding-3-large",
        api_version: str = "2024-02-01"
    ):
        """
        EmbeddingService 초기화
        
        Args:
            api_key: Azure OpenAI API 키 (기본값: 환경변수)
            azure_endpoint: Azure OpenAI 엔드포인트 (기본값: 환경변수)
            embedding_model: 임베딩 모델명 (기본값: text-embedding-3-large)
            api_version: API 버전 (기본값: 2024-02-01)
        """
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.embedding_model = embedding_model
        
        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI API 키와 엔드포인트가 필요합니다")
        
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.azure_endpoint
        )
        
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
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        텍스트 임베딩 생성 (리스트 반환)
        
        분류 에이전트 호환용 메서드
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            임베딩 벡터 (리스트) 또는 None
        """
        embedding = self.generate_embedding(text)
        if embedding is not None:
            return embedding.tolist()
        return None
    
    def get_embedding_dimension(self) -> int:
        """
        임베딩 차원 수 반환
        
        Returns:
            임베딩 벡터의 차원 수
        """
        # text-embedding-3-large의 차원은 3072
        return 3072


# 싱글톤 인스턴스
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """
    EmbeddingService 싱글톤 인스턴스 반환
    
    Returns:
        EmbeddingService 인스턴스
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
