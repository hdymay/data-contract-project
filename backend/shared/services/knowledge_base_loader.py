"""
지식베이스 로더
Ingestion에서 생성한 인덱스 및 청크 데이터를 로드
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging
import pickle

import faiss

logger = logging.getLogger(__name__)


class KnowledgeBaseLoader:
    """
    지식베이스 로더
    
    Ingestion에서 생성한 데이터를 로드:
    - FAISS 인덱스
    - Whoosh 인덱스
    - 청크 메타데이터
    """
    
    def __init__(
        self,
        data_dir: Path = Path("/app/data"),
        index_dir: Path = Path("/app/search_indexes")
    ):
        """
        초기화
        
        Args:
            data_dir: 데이터 디렉토리 경로
            index_dir: 인덱스 디렉토리 경로
        """
        self.data_dir = data_dir
        self.index_dir = index_dir
        
        self.chunked_dir = data_dir / "chunked_documents"
        self.faiss_dir = index_dir / "faiss"
        self.whoosh_dir = index_dir / "whoosh"
        
        # 캐시
        self._faiss_cache: Dict[str, Any] = {}
        self._chunks_cache: Dict[str, list] = {}
    
    def load_faiss_index(self, contract_type: str) -> Optional[Any]:
        """
        FAISS 인덱스 로드
        
        Args:
            contract_type: 계약 유형 (provide, create, process, brokerage_provider, brokerage_user)
            
        Returns:
            FAISS 인덱스 또는 None
        """
        # 캐시 확인
        if contract_type in self._faiss_cache:
            logger.info(f"FAISS 인덱스 캐시 히트: {contract_type}")
            return self._faiss_cache[contract_type]
        
        # 파일 경로
        index_file = self.faiss_dir / f"{contract_type}_std_contract.faiss"
        
        if not index_file.exists():
            logger.error(f"FAISS 인덱스 파일을 찾을 수 없습니다: {index_file}")
            return None
        
        try:
            # FAISS 인덱스 로드
            index = faiss.read_index(str(index_file))
            
            # 캐시 저장
            self._faiss_cache[contract_type] = index
            
            logger.info(f"FAISS 인덱스 로드 완료: {contract_type} ({index.ntotal} vectors)")
            return index
            
        except Exception as e:
            logger.error(f"FAISS 인덱스 로드 실패: {e}")
            return None
    
    def load_chunks(self, contract_type: str) -> Optional[list]:
        """
        청크 메타데이터 로드
        
        Args:
            contract_type: 계약 유형
            
        Returns:
            청크 리스트 또는 None
        """
        # 캐시 확인
        if contract_type in self._chunks_cache:
            logger.info(f"청크 메타데이터 캐시 히트: {contract_type}")
            return self._chunks_cache[contract_type]
        
        # 파일 경로 (chunks.json)
        chunks_file = self.chunked_dir / f"{contract_type}_std_contract_chunks.json"
        
        if not chunks_file.exists():
            logger.error(f"청크 파일을 찾을 수 없습니다: {chunks_file}")
            return None
        
        try:
            # 청크 로드
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            
            # 캐시 저장
            self._chunks_cache[contract_type] = chunks
            
            logger.info(f"청크 메타데이터 로드 완료: {contract_type} ({len(chunks)} chunks)")
            return chunks
            
        except Exception as e:
            logger.error(f"청크 로드 실패: {e}")
            return None
    
    def load_whoosh_index(self, contract_type: str):
        """
        Whoosh 인덱스 로드
        
        Args:
            contract_type: 계약 유형
            
        Returns:
            WhooshIndexer 인스턴스 또는 None
        """
        whoosh_path = self.whoosh_dir / f"{contract_type}_std_contract"
        
        if not whoosh_path.exists():
            logger.error(f"Whoosh 인덱스 디렉토리를 찾을 수 없습니다: {whoosh_path}")
            return None
        
        try:
            # WhooshIndexer 임포트 및 초기화
            import sys
            sys.path.append('/app')
            from ingestion.indexers.whoosh_indexer import WhooshIndexer
            
            indexer = WhooshIndexer(whoosh_path)
            logger.info(f"Whoosh 인덱스 로드 완료: {contract_type}")
            return indexer
            
        except Exception as e:
            logger.error(f"Whoosh 인덱스 로드 실패: {e}")
            return None
    
    def get_available_contract_types(self) -> list:
        """
        사용 가능한 계약 유형 목록 반환
        
        Returns:
            계약 유형 리스트
        """
        available_types = []
        
        for contract_type in ['provide', 'create', 'process', 'brokerage_provider', 'brokerage_user']:
            faiss_file = self.faiss_dir / f"{contract_type}_std_contract.faiss"
            chunks_file = self.chunked_dir / f"{contract_type}_std_contract_chunks.json"
            
            if faiss_file.exists() and chunks_file.exists():
                available_types.append(contract_type)
        
        return available_types
    
    def verify_knowledge_base(self) -> Dict[str, Any]:
        """
        지식베이스 상태 확인
        
        Returns:
            {
                "status": "ok" | "incomplete" | "missing",
                "available_types": [...],
                "missing_types": [...],
                "details": {...}
            }
        """
        all_types = ['provide', 'create', 'process', 'brokerage_provider', 'brokerage_user']
        available_types = self.get_available_contract_types()
        missing_types = [t for t in all_types if t not in available_types]
        
        details = {}
        for contract_type in all_types:
            faiss_file = self.faiss_dir / f"{contract_type}_std_contract.faiss"
            chunks_file = self.chunked_dir / f"{contract_type}_std_contract_chunks.json"
            whoosh_dir = self.whoosh_dir / f"{contract_type}_std_contract"
            
            details[contract_type] = {
                "faiss": faiss_file.exists(),
                "chunks": chunks_file.exists(),
                "whoosh": whoosh_dir.exists()
            }
        
        if len(available_types) == len(all_types):
            status = "ok"
        elif len(available_types) > 0:
            status = "incomplete"
        else:
            status = "missing"
        
        return {
            "status": status,
            "available_types": available_types,
            "missing_types": missing_types,
            "details": details
        }


# 싱글톤 인스턴스
_knowledge_base_loader = None


def get_knowledge_base_loader() -> KnowledgeBaseLoader:
    """
    KnowledgeBaseLoader 싱글톤 인스턴스 반환
    
    Returns:
        KnowledgeBaseLoader 인스턴스
    """
    global _knowledge_base_loader
    if _knowledge_base_loader is None:
        _knowledge_base_loader = KnowledgeBaseLoader()
    return _knowledge_base_loader
