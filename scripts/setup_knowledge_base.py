"""
지식베이스 구축 스크립트
"""
import os
import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.services.embedding_service import EmbeddingService
from backend.services.search_service import SearchService
from backend.utils.text_processors import TextProcessor

async def setup_knowledge_base():
    """지식베이스 구축"""
    print("지식베이스 구축을 시작합니다...")
    
    try:
        # 임베딩 서비스 초기화
        embedding_service = EmbeddingService()
        search_service = SearchService()
        text_processor = TextProcessor()
        
        # 표준계약서 처리
        await process_standard_contracts(embedding_service, text_processor)
        
        # 활용안내서 처리
        await process_guide_documents(embedding_service, text_processor)
        
        # 인덱스 구축
        await build_indexes(search_service)
        
        print("지식베이스 구축이 완료되었습니다!")
        
    except Exception as e:
        print(f"지식베이스 구축 실패: {e}")

async def process_standard_contracts(embedding_service, text_processor):
    """표준계약서 처리"""
    print("표준계약서를 처리합니다...")
    # TODO: 표준계약서 처리 로직

async def process_guide_documents(embedding_service, text_processor):
    """활용안내서 처리"""
    print("활용안내서를 처리합니다...")
    # TODO: 활용안내서 처리 로직

async def build_indexes(search_service):
    """인덱스 구축"""
    print("검색 인덱스를 구축합니다...")
    # TODO: 인덱스 구축 로직

if __name__ == "__main__":
    asyncio.run(setup_knowledge_base())
