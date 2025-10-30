"""
검색 점수 디버깅 스크립트
유사도가 100%를 넘는 문제 분석
"""

import os
import sys
from pathlib import Path

# PYTHONPATH 설정
sys.path.insert(0, str(Path(__file__).parent))

from openai import AzureOpenAI
from backend.shared.services.knowledge_base_loader import KnowledgeBaseLoader
from backend.consistency_agent.hybrid_searcher import HybridSearcher
from backend.consistency_agent.a3_node.article_matcher import ArticleMatcher


def debug_search_scores():
    """검색 점수 범위 확인"""
    
    # Azure OpenAI 클라이언트
    if not os.getenv('AZURE_OPENAI_API_KEY'):
        print("❌ Azure OpenAI 환경 변수 없음")
        return
    
    azure_client = AzureOpenAI(
        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
        azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
        api_version="2024-02-01"
    )
    
    # KnowledgeBaseLoader
    kb_loader = KnowledgeBaseLoader()
    contract_type = "provide"
    
    # HybridSearcher 생성
    searcher = HybridSearcher(
        azure_client=azure_client,
        embedding_model="text-embedding-3-large"
    )
    
    # 인덱스 로드
    print(f"📚 인덱스 로드 중: {contract_type}")
    faiss_index = kb_loader.load_faiss_index(contract_type)
    chunks = kb_loader.load_chunks(contract_type)
    whoosh_indexer = kb_loader.load_whoosh_index(contract_type)
    
    if not faiss_index or not chunks or not whoosh_indexer:
        print("❌ 인덱스 로드 실패")
        return
    
    searcher.load_indexes(faiss_index, chunks, whoosh_indexer)
    print(f"✅ 인덱스 로드 완료: {len(chunks)}개 청크")
    
    # 테스트 쿼리들
    test_queries = [
        "데이터 제공 범위 및 방식",
        "계약의 목적",
        "데이터 이용 목적 및 범위",
        "데이터 제공 기간",
        "비밀유지 의무"
    ]
    
    print("\n" + "="*80)
    print("검색 점수 분석")
    print("="*80)
    
    for query in test_queries:
        print(f"\n🔍 쿼리: {query}")
        print("-" * 80)
        
        # Dense 검색
        dense_results = searcher.dense_search(query, top_k=10)
        print(f"\n  [Dense 검색] {len(dense_results)}개 결과")
        if dense_results:
            scores = [r['score'] for r in dense_results]
            print(f"    점수 범위: {min(scores):.4f} ~ {max(scores):.4f}")
            print(f"    Top-3:")
            for i, r in enumerate(dense_results[:3], 1):
                print(f"      {i}. {r['chunk'].get('parent_id', 'N/A')} - {r['score']:.4f}")
        
        # Sparse 검색
        sparse_results = searcher.sparse_search(query, top_k=10)
        print(f"\n  [Sparse 검색] {len(sparse_results)}개 결과")
        if sparse_results:
            scores = [r['score'] for r in sparse_results]
            print(f"    점수 범위: {min(scores):.4f} ~ {max(scores):.4f}")
            print(f"    Top-3:")
            for i, r in enumerate(sparse_results[:3], 1):
                print(f"      {i}. {r['chunk'].get('parent_id', 'N/A')} - {r['score']:.4f}")
        
        # 하이브리드 검색
        hybrid_results = searcher.search(query, top_k=10)
        print(f"\n  [하이브리드 검색] {len(hybrid_results)}개 결과")
        if hybrid_results:
            scores = [r['score'] for r in hybrid_results]
            print(f"    점수 범위: {min(scores):.4f} ~ {max(scores):.4f}")
            print(f"    Top-3:")
            for i, r in enumerate(hybrid_results[:3], 1):
                dense_score = r.get('dense_score', 0.0)
                sparse_score = r.get('sparse_score', 0.0)
                final_score = r['score']
                print(f"      {i}. {r.get('parent_id', 'N/A')} - Final: {final_score:.4f} (Dense: {dense_score:.4f}, Sparse: {sparse_score:.4f})")
                
                # 100% 초과 여부 확인
                if final_score > 1.0:
                    print(f"        ⚠️  점수가 1.0을 초과했습니다!")
    
    print("\n" + "="*80)
    print("ArticleMatcher 테스트")
    print("="*80)
    
    # ArticleMatcher 테스트
    matcher = ArticleMatcher(
        knowledge_base_loader=kb_loader,
        azure_client=azure_client,
        similarity_threshold=0.7
    )
    
    test_article = {
        "number": "5",
        "title": "데이터 제공 범위 및 방식",
        "content": [
            "제공자는 이용자에게 다음 각 호의 데이터를 제공한다.",
            "1. 데이터의 종류: 고객 거래 데이터",
            "2. 데이터의 형식: CSV 파일",
            "3. 제공 방식: API를 통한 실시간 제공"
        ]
    }
    
    print(f"\n🔍 테스트 조항: 제{test_article['number']}조 ({test_article['title']})")
    print("-" * 80)
    
    matching_result = matcher.find_matching_article(
        test_article,
        contract_type,
        top_k=5
    )
    
    print(f"\n  매칭 결과:")
    print(f"    - 매칭 성공: {matching_result['matched']}")
    print(f"    - 유사도: {matching_result['similarity']:.4f}")
    if matching_result['similarity'] > 1.0:
        print(f"      ⚠️  유사도가 1.0을 초과했습니다!")
    print(f"    - 표준 조항: {matching_result.get('std_article_id', 'N/A')}")
    print(f"    - 표준 제목: {matching_result.get('std_article_title', 'N/A')}")
    
    # 하위항목별 결과
    sub_item_results = matching_result.get('sub_item_results', [])
    if sub_item_results:
        print(f"\n  하위항목별 Top-1 결과:")
        for sub_result in sub_item_results:
            idx = sub_result['sub_item_index']
            score = sub_result['score']
            parent_id = sub_result.get('parent_id', 'N/A')
            print(f"    {idx}. {parent_id} - {score:.4f}")
            if score > 1.0:
                print(f"       ⚠️  점수가 1.0을 초과했습니다!")


if __name__ == "__main__":
    debug_search_scores()
