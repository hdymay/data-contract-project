"""
Consistency Agent 통합 테스트
"""

import pytest
import os
import sys
from pathlib import Path

# PYTHONPATH 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.shared.database import SessionLocal, ContractDocument, ValidationResult, init_db
from backend.shared.services.knowledge_base_loader import KnowledgeBaseLoader
from backend.consistency_agent.nodes.a3_node import ContentAnalysisNode
from backend.consistency_agent.nodes.article_matcher import ArticleMatcher
from backend.consistency_agent.hybrid_searcher import HybridSearcher


class TestConsistencyAgentIntegration:
    """Consistency Agent 통합 테스트"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """테스트 설정"""
        # 데이터베이스 초기화
        init_db()
        
        # 테스트용 계약서 데이터
        self.test_contract_id = "test_contract_001"
        self.test_contract_type = "provide"
        
        self.test_user_contract = {
            "articles": [
                {
                    "number": "1",
                    "title": "목적",
                    "content": [
                        "이 계약은 데이터 제공자와 이용자 간의 데이터 제공에 관한 사항을 정함을 목적으로 한다."
                    ]
                },
                {
                    "number": "2",
                    "title": "정의",
                    "content": [
                        "이 계약에서 사용하는 용어의 정의는 다음과 같다.",
                        "1. 데이터: 제공자가 보유한 정보",
                        "2. 이용자: 데이터를 제공받는 자"
                    ]
                }
            ]
        }
    
    def test_knowledge_base_loader(self):
        """KnowledgeBaseLoader 테스트"""
        kb_loader = KnowledgeBaseLoader()
        
        # FAISS 인덱스 로드
        faiss_index = kb_loader.load_faiss_index(self.test_contract_type)
        assert faiss_index is not None, "FAISS 인덱스 로드 실패"
        
        # 청크 로드
        chunks = kb_loader.load_chunks(self.test_contract_type)
        assert chunks is not None, "청크 로드 실패"
        assert len(chunks) > 0, "청크가 비어있음"
        
        # Whoosh 인덱스 로드
        whoosh_indexer = kb_loader.load_whoosh_index(self.test_contract_type)
        assert whoosh_indexer is not None, "Whoosh 인덱스 로드 실패"
    
    def test_hybrid_searcher(self):
        """HybridSearcher 테스트"""
        # Azure OpenAI 클라이언트 필요 (환경 변수 확인)
        if not os.getenv('AZURE_OPENAI_API_KEY'):
            pytest.skip("Azure OpenAI 환경 변수 없음")
        
        from openai import AzureOpenAI
        
        azure_client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_version="2024-02-01"
        )
        
        searcher = HybridSearcher(
            azure_client=azure_client,
            embedding_model="text-embedding-3-large"
        )
        
        # 인덱스 로드
        kb_loader = KnowledgeBaseLoader()
        faiss_index = kb_loader.load_faiss_index(self.test_contract_type)
        chunks = kb_loader.load_chunks(self.test_contract_type)
        whoosh_indexer = kb_loader.load_whoosh_index(self.test_contract_type)
        
        searcher.load_indexes(faiss_index, chunks, whoosh_indexer)
        
        # 검색 수행
        query = "데이터 제공 범위"
        results = searcher.search(query, self.test_contract_type, top_k=5)
        
        assert results is not None, "검색 결과 없음"
        assert len(results) > 0, "검색 결과가 비어있음"
        
        # 결과 구조 확인
        for result in results:
            assert 'chunk_id' in result
            assert 'parent_id' in result
            assert 'score' in result
    
    def test_article_matcher(self):
        """ArticleMatcher 테스트"""
        kb_loader = KnowledgeBaseLoader()
        
        matcher = ArticleMatcher(
            knowledge_base_loader=kb_loader,
            similarity_threshold=0.7
        )
        
        # 테스트 조항
        test_article = self.test_user_contract['articles'][0]
        
        # 매칭 수행
        matching_result = matcher.find_matching_article(
            test_article,
            self.test_contract_type
        )
        
        assert matching_result is not None
        assert 'matched' in matching_result
        assert 'similarity' in matching_result
        assert 'std_article_id' in matching_result
    
    def test_a3_node(self):
        """A3 노드 테스트"""
        # Azure OpenAI 클라이언트 필요
        if not os.getenv('AZURE_OPENAI_API_KEY'):
            pytest.skip("Azure OpenAI 환경 변수 없음")
        
        from openai import AzureOpenAI
        
        azure_client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_version="2024-02-01"
        )
        
        kb_loader = KnowledgeBaseLoader()
        
        a3_node = ContentAnalysisNode(
            knowledge_base_loader=kb_loader,
            azure_client=azure_client
        )
        
        # 분석 수행
        result = a3_node.analyze_contract(
            contract_id=self.test_contract_id,
            user_contract=self.test_user_contract,
            contract_type=self.test_contract_type
        )
        
        assert result is not None
        assert result.total_articles == len(self.test_user_contract['articles'])
        assert result.analyzed_articles >= 0
        assert result.overall_scores is not None
    
    def test_database_models(self):
        """데이터베이스 모델 테스트"""
        db = SessionLocal()
        
        try:
            # ContractDocument 생성
            contract = ContractDocument(
                contract_id=self.test_contract_id,
                filename="test_contract.docx",
                parsed_data=self.test_user_contract,
                classification_result={
                    "predicted_type": self.test_contract_type,
                    "confidence": 0.95
                }
            )
            
            db.add(contract)
            db.commit()
            
            # 조회
            loaded_contract = db.query(ContractDocument).filter(
                ContractDocument.contract_id == self.test_contract_id
            ).first()
            
            assert loaded_contract is not None
            assert loaded_contract.contract_id == self.test_contract_id
            assert loaded_contract.classification_result is not None
            
            # ValidationResult 생성
            validation = ValidationResult(
                contract_id=self.test_contract_id,
                contract_type=self.test_contract_type,
                content_analysis={"status": "completed"},
                overall_score=0.85
            )
            
            db.add(validation)
            db.commit()
            
            # 조회
            loaded_validation = db.query(ValidationResult).filter(
                ValidationResult.contract_id == self.test_contract_id
            ).first()
            
            assert loaded_validation is not None
            assert loaded_validation.contract_type == self.test_contract_type
            
        finally:
            # 정리
            db.query(ValidationResult).filter(
                ValidationResult.contract_id == self.test_contract_id
            ).delete()
            db.query(ContractDocument).filter(
                ContractDocument.contract_id == self.test_contract_id
            ).delete()
            db.commit()
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
