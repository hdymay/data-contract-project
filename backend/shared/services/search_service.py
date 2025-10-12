import os
from pathlib import Path

class SearchService:
    
    def __init__(self):
        # 검색 인덱스 경로 설정
        self.index_path = Path("/app/search_indexes")
        self.index_path.mkdir(exist_ok=True)
    
    def search(self, query: str, top_k: int = 10):
        # TODO: whoosh/faiss 구현
        return []
    
    def add_document(self, doc_id: str, content: str):
        # TODO: 인덱스에 문서 추가
        pass
