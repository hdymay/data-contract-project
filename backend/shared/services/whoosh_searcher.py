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
from whoosh.qparser import QueryParser, OrGroup
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

                # Whoosh 검색용: 플레이스홀더 제거
                # (FAISS는 원본 쿼리를 사용하므로 여기서만 제거)
                query_for_whoosh = self._remove_placeholders(query)

                # 한국어 쿼리를 MeCab으로 토크나이징
                # 인덱스도 토크나이징되어 저장되어 있으므로 동일하게 처리
                morphs = self.tokenizer.tokenize(query_for_whoosh)
                tokenized_query = " ".join(morphs)

                logger.debug(f"원본 쿼리: {query[:100]}...")
                logger.debug(f"Whoosh용 쿼리 (placeholder 제거): {query_for_whoosh[:100]}...")
                logger.debug(f"토크나이징된 쿼리: {tokenized_query[:100]}...")

                # 이미 토크나이징되었으므로 특수문자 이스케이프만 수행
                escaped_query = self._escape_query(tokenized_query)
                logger.debug(f"이스케이프된 쿼리: {escaped_query[:100]}...")

                # text_norm과 title 필드에서 검색
                # OrGroup: 기본 AND 대신 OR 연산자 사용 (더 관대한 매칭)
                parser_text = QueryParser("text_norm", schema=self.ix.schema, group=OrGroup)
                parser_title = QueryParser("title", schema=self.ix.schema, group=OrGroup)
                
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

                # 결과 로깅 (INFO 레벨로 변경하여 항상 표시)
                if len(results) > 0:
                    scores = [hit.score for hit in results]
                    logger.info(f"✓ Whoosh 검색 성공: {len(results)}개, 점수 범위 [{min(scores):.4f} ~ {max(scores):.4f}]")
                    logger.debug(f"  상위 3개 결과: {[hit['id'] for hit in results[:3]]}")
                else:
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

    def _remove_placeholders(self, query: str) -> str:
        """
        Whoosh 검색용 플레이스홀더 제거

        사용자 계약서의 ○○○, □□□ 등의 플레이스홀더 문자를 제거합니다.
        표준계약서 인덱스에는 이런 플레이스홀더가 없으므로 제거해야 매칭이 가능합니다.

        참고: FAISS 임베딩은 원본 텍스트를 사용하므로 영향받지 않습니다.

        Args:
            query: 원본 쿼리

        Returns:
            플레이스홀더가 제거된 쿼리
        """
        # 원형 플레이스홀더 제거 (○, ●)
        result = re.sub(r'[○●]+', '', query)

        # 사각형 플레이스홀더 제거 (□, ■)
        result = re.sub(r'[□■]+', '', result)

        # 기타 도형 플레이스홀더 제거 (◆, ◇, ▲, △, ▼, ▽)
        result = re.sub(r'[◆◇▲△▼▽]+', '', result)

        # 여러 연속 공백을 단일 공백으로 변환
        result = re.sub(r'\s+', ' ', result)

        # 앞뒤 공백 제거
        return result.strip()

    def search_with_field_weights(
        self,
        text_query: str,
        title_query: str,
        text_weight: float = 0.7,
        title_weight: float = 0.3,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        제목과 본문을 별도로 검색하고 가중합

        Args:
            text_query: 본문 검색 쿼리
            title_query: 제목 검색 쿼리
            text_weight: 본문 가중치 (기본 0.7)
            title_weight: 제목 가중치 (기본 0.3)
            top_k: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트 (text_score, title_score 포함)
        """
        with self.ix.searcher() as searcher:
            try:
                # 1. 본문 검색 (text_norm 필드)
                text_results = {}
                if text_query and text_query.strip():
                    query_for_whoosh = self._remove_placeholders(text_query)
                    morphs = self.tokenizer.tokenize(query_for_whoosh)
                    tokenized_query = " ".join(morphs)
                    escaped_query = self._escape_query(tokenized_query)
                    
                    parser_text = QueryParser("text_norm", schema=self.ix.schema, group=OrGroup)
                    parsed_query_text = parser_text.parse(escaped_query)
                    
                    results = searcher.search(parsed_query_text, limit=top_k * 2)
                    
                    for hit in results:
                        chunk_id = hit['id']
                        text_results[chunk_id] = {
                            'hit': hit,
                            'text_score': hit.score
                        }
                    
                    logger.debug(f"본문 검색 결과: {len(text_results)}개")
                
                # 2. 제목 검색 (title 필드)
                title_results = {}
                if title_query and title_query.strip():
                    query_for_whoosh = self._remove_placeholders(title_query)
                    morphs = self.tokenizer.tokenize(query_for_whoosh)
                    tokenized_query = " ".join(morphs)
                    escaped_query = self._escape_query(tokenized_query)
                    
                    parser_title = QueryParser("title", schema=self.ix.schema, group=OrGroup)
                    parsed_query_title = parser_title.parse(escaped_query)
                    
                    results = searcher.search(parsed_query_title, limit=top_k * 2)
                    
                    for hit in results:
                        chunk_id = hit['id']
                        title_results[chunk_id] = {
                            'hit': hit,
                            'title_score': hit.score
                        }
                    
                    logger.debug(f"제목 검색 결과: {len(title_results)}개")
                
                # 3. 결과 병합 및 가중합 계산
                all_chunk_ids = set(text_results.keys()) | set(title_results.keys())
                
                if not all_chunk_ids:
                    logger.warning("Whoosh 검색 결과 없음 (제목/본문 모두)")
                    return []
                
                search_results = []
                for chunk_id in all_chunk_ids:
                    text_score = text_results.get(chunk_id, {}).get('text_score', 0.0)
                    title_score = title_results.get(chunk_id, {}).get('title_score', 0.0)
                    
                    # Hit 정보 (text 또는 title 결과에서 가져오기)
                    hit = text_results.get(chunk_id, title_results.get(chunk_id))['hit']
                    
                    # 가중합 계산
                    weighted_score = text_weight * text_score + title_weight * title_score
                    
                    # 메타데이터 파싱
                    metadata = json.loads(hit['metadata'])
                    
                    result = {
                        'id': hit['id'],
                        'global_id': hit['global_id'],
                        'text_norm': hit['text_norm'],
                        'title': hit['title'],
                        'text_raw': hit['text_raw'],
                        'score': weighted_score,
                        'text_score': text_score,
                        'title_score': title_score,
                        'highlights': hit.highlights('text_norm', top=3),
                        # 메타데이터
                        'unit_type': metadata.get('unit_type', ''),
                        'parent_id': metadata.get('parent_id', ''),
                        'source_file': metadata.get('source_file', ''),
                        'order_index': metadata.get('order_index', 0),
                        'anchors': metadata.get('anchors', [])
                    }
                    search_results.append(result)
                
                # 점수 순으로 정렬
                search_results.sort(key=lambda x: x['score'], reverse=True)

                logger.info(f"✓ Whoosh 검색 완료: {len(search_results)}개 (본문: {len(text_results)}, 제목: {len(title_results)})")

                return search_results[:top_k]
                
            except Exception as e:
                logger.error(f"Whoosh 필드별 검색 실패: {e}")
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
