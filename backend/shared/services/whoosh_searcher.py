"""
Whoosh 검색기 (Backend용)
Ingestion에서 생성한 Whoosh 인덱스를 검색하는 기능만 제공
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import re

from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from whoosh.query import Or

from backend.shared.utils.korean_analyzer import KoreanTokenizer

logger = logging.getLogger(__name__)


class WhooshSearcher:
    """
    Whoosh 인덱스 검색기 (Backend용)
    Ingestion에서 생성한 인덱스를 읽기 전용으로 검색
    """

    def __init__(self, index_path: Path):
        """
        Args:
            index_path: Whoosh 인덱스 디렉토리 경로
        """
        self.index_path = index_path
        self.tokenizer = KoreanTokenizer()
        
        # 인덱스 열기 (읽기 전용)
        try:
            self.ix = open_dir(str(index_path))
            logger.info(f"Whoosh 인덱스 열기 완료: {index_path}")
        except Exception as e:
            logger.error(f"Whoosh 인덱스 열기 실패: {e}")
            raise

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        키워드 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        with self.ix.searcher() as searcher:
            try:
                # 인덱스 문서 개수 확인
                doc_count = searcher.doc_count_all()
                logger.debug(f"Whoosh 인덱스 총 문서 수: {doc_count}")

                if doc_count == 0:
                    logger.error("Whoosh 인덱스가 비어있습니다!")
                    return []

                # 한국어 쿼리를 MeCab으로 토크나이징
                # 인덱스도 토크나이징되어 저장되어 있으므로 동일하게 처리
                morphs = self.tokenizer.tokenize(query)
                tokenized_query = " ".join(morphs)
                
                logger.debug(f"원본 쿼리: {query[:100]}...")
                logger.debug(f"토크나이징된 쿼리: {tokenized_query[:100]}...")

                # 이미 토크나이징되었으므로 특수문자 이스케이프만 수행
                escaped_query = self._escape_query(tokenized_query)
                logger.debug(f"이스케이프된 쿼리: {escaped_query[:100]}...")

                # text_norm과 title 필드에서 검색
                parser_text = QueryParser("text_norm", schema=self.ix.schema)
                parser_title = QueryParser("title", schema=self.ix.schema)
                
                # 쿼리 파싱
                query_text = parser_text.parse(escaped_query)
                query_title = parser_title.parse(escaped_query)
                
                logger.debug(f"파싱된 쿼리 (text_norm): {str(query_text)[:100]}")
                logger.debug(f"파싱된 쿼리 (title): {str(query_title)[:100]}")
                
                # OR 조합
                parsed_query = Or([query_text, query_title])
                logger.debug(f"최종 쿼리 타입: {type(parsed_query).__name__}")

                # 검색 실행
                results = searcher.search(parsed_query, limit=top_k)
                logger.debug(f"Whoosh 검색 결과: {len(results)}개")

                # 결과가 없는 경우 추가 진단
                if len(results) == 0:
                    logger.warning(f"Whoosh 검색 결과 0개 - 쿼리: {query[:100]}")
                    
                    # 샘플 문서 확인
                    sample_docs = list(searcher.documents())[:3]
                    if sample_docs:
                        logger.debug(f"  인덱스 샘플 문서 {len(sample_docs)}개:")
                        for i, doc in enumerate(sample_docs, 1):
                            logger.debug(f"    Doc {i}: id={doc.get('id')}, text_norm={doc.get('text_norm', '')[:50]}...")

                # 결과 변환
                search_results = []
                for hit in results:
                    # 메타데이터 파싱
                    metadata = json.loads(hit['metadata'])

                    result = {
                        'id': hit['id'],
                        'global_id': hit['global_id'],
                        'text_norm': hit['text_norm'],
                        'title': hit['title'],
                        'text_raw': hit['text_raw'],
                        'score': hit.score,
                        'highlights': hit.highlights('text_norm', top=3),
                        # 메타데이터 풀어서 추가
                        'unit_type': metadata.get('unit_type', ''),
                        'parent_id': metadata.get('parent_id', ''),
                        'source_file': metadata.get('source_file', ''),
                        'order_index': metadata.get('order_index', 0),
                        'anchors': metadata.get('anchors', [])
                    }
                    search_results.append(result)

                return search_results

            except Exception as e:
                logger.error(f"Whoosh 쿼리 파싱/검색 실패: {e}")
                logger.debug(f"  실패한 쿼리: {query[:200]}...")
                import traceback
                logger.error(traceback.format_exc())
                return []

    def _escape_query(self, query: str) -> str:
        """
        Whoosh 쿼리 특수문자 이스케이프

        Args:
            query: 원본 쿼리

        Returns:
            이스케이프된 쿼리
        """
        # 특수문자 이스케이프
        special_chars = [':', '(', ')', '[', ']', '{', '}', '!', '"', '^', '~']
        
        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, f'\\{char}')

        # 불린 연산자 이스케이프
        escaped = re.sub(r'\bAND\b', 'and', escaped)
        escaped = re.sub(r'\bOR\b', 'or', escaped)
        escaped = re.sub(r'\bNOT\b', 'not', escaped)

        return escaped
