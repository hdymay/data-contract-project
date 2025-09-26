"""
검색 서비스 (최소한의 틀)
"""
import os
from pathlib import Path

class SearchService:
    """검색 서비스 기본 틀"""
    
    def __init__(self):
        # 검색 인덱스 경로 설정
        self.index_path = Path("/app/search_indexes")
        self.index_path.mkdir(exist_ok=True)
    
    def search(self, query: str, top_k: int = 10):
        """검색 (기본 틀)"""
        # TODO: whoosh/faiss 구현
        return []
    
    def add_document(self, doc_id: str, content: str):
        """문서 추가 (기본 틀)"""
        # TODO: 인덱스에 문서 추가
        pass
