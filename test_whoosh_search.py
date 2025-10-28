"""
Whoosh 검색 테스트 스크립트
Whoosh 인덱스가 실제로 작동하는지 확인
"""

import sys
from pathlib import Path

# 경로 추가
sys.path.append(str(Path(__file__).parent))

from ingestion.indexers.whoosh_indexer import WhooshIndexer
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_whoosh_search():
    """Whoosh 검색 테스트"""

    # Whoosh 인덱스 경로
    whoosh_path = Path("./data/search_indexes/whoosh/provide_std_contract")

    if not whoosh_path.exists():
        logger.error(f"Whoosh 인덱스 경로가 존재하지 않습니다: {whoosh_path}")
        return

    logger.info(f"Whoosh 인덱스 로드 시도: {whoosh_path}")

    try:
        # WhooshIndexer 초기화
        indexer = WhooshIndexer(whoosh_path)

        # 인덱스 상태 확인
        with indexer.ix.searcher() as searcher:
            doc_count = searcher.doc_count_all()
            logger.info(f"✓ 인덱스 문서 수: {doc_count}")

            # 샘플 문서 확인
            sample_docs = list(searcher.documents())[:3]
            logger.info(f"✓ 샘플 문서 {len(sample_docs)}개:")
            for i, doc in enumerate(sample_docs, 1):
                logger.info(f"  {i}. id={doc.get('id')}, title={doc.get('title', '')[:30]}")

        # 테스트 쿼리들
        test_queries = [
            "데이터 제공",
            "계약의 목적",
            "개인정보 보호",
            "손해배상",
            "계약 기간"
        ]

        logger.info("\n" + "="*60)
        logger.info("테스트 쿼리 검색 시작")
        logger.info("="*60)

        for query in test_queries:
            logger.info(f"\n쿼리: '{query}'")
            results = indexer.search(query, top_k=5)

            if results:
                logger.info(f"  ✓ 결과: {len(results)}개")
                for i, result in enumerate(results[:3], 1):
                    logger.info(f"    {i}. {result['parent_id']}: {result['title']} (점수: {result['score']:.4f})")
            else:
                logger.warning(f"  ✗ 결과 없음")

        logger.info("\n" + "="*60)
        logger.info("테스트 완료")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_whoosh_search()
