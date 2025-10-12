# Whoosh 키워드 인덱서
from pathlib import Path
from typing import List, Dict, Any


class WhooshIndexer:
    
    def __init__(self, index_path: Path):
        """
        Args:
            index_path: 인덱스 저장 경로
        """
        self.index_path = index_path
        self.index_path.mkdir(parents=True, exist_ok=True)
    
    def build(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Whoosh 인덱스 구축
        
        Args:
            chunks: 임베딩된 청크 리스트
        """
        # TODO: 구현
        pass
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        키워드 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            
        Returns:
            검색 결과 리스트
        """
        # TODO: 구현
        pass

