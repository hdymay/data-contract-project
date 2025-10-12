
# 임베딩 생성 모듈
from typing import List, Dict, Any
import numpy as np


class TextEmbedder:
    
    def __init__(self, model_name: str = "ko-sroberta"):
        """
        Args:
            model_name: 사용할 임베딩 모델 이름
        """
        self.model_name = model_name
        self.model = None
    
    def embed(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        청크에 임베딩 추가
        
        Args:
            chunks: 청크 리스트
            
        Returns:
            임베딩이 추가된 청크 리스트
        """
        # TODO: 구현
        pass

