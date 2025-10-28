# Whoosh 키워드 인덱서
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.index import create_in, open_dir, exists_in
from whoosh.qparser import MultifieldParser
from whoosh.analysis import Tokenizer, Token

logger = logging.getLogger(__name__)


class KoreanAnalyzer(Tokenizer):
    """
    한국어 형태소 분석기
    KoNLPy의 Mecab 사용, 없으면 에러 발생

    중요: 인덱스 구축과 검색 시 동일한 토크나이저를 사용해야 함
    """

    def __init__(self):
        """형태소 분석기 초기화"""
        self._mecab = None
        self._dicpath = None
        self._init_mecab()

    def _init_mecab(self):
        """Mecab 초기화 (lazy loading)"""
        if self._mecab is not None:
            return
            
        try:
            from konlpy.tag import Mecab
            import os
            import site

            # mecab-ko-dic-msvc 사전 경로 찾기
            # mecab-ko-dic-msvc 패키지는 Python 모듈이 아니라 사전 파일만 설치함
            dicpath = None
            
            # site-packages 경로에서 mecab-ko-dic 찾기
            for site_path in site.getsitepackages():
                potential_dicpath = os.path.join(site_path, 'mecab-ko-dic')
                if os.path.exists(potential_dicpath):
                    dicpath = potential_dicpath
                    logger.info(f"✓ mecab-ko-dic 사전 경로 발견: {dicpath}")
                    break
            
            self._dicpath = dicpath
            
            if dicpath:
                self._mecab = Mecab(dicpath)
            else:
                logger.warning("mecab-ko-dic 사전을 찾을 수 없습니다. 기본 경로 시도...")
                self._mecab = Mecab()

            logger.info("✓ KoNLPy Mecab 초기화 완료")
        except (ImportError, Exception) as e:
            logger.error(f"✗ Mecab 초기화 실패: {e}")
            logger.error("Mecab을 설치해주세요. 자세한 내용: http://konlpy.org/en/latest/install/")
            raise RuntimeError(f"Mecab 형태소 분석기가 필요합니다: {e}")

    @property
    def mecab(self):
        """Mecab 인스턴스 (lazy loading)"""
        if self._mecab is None:
            self._init_mecab()
        return self._mecab

    def __getstate__(self):
        """pickle 직렬화 시 호출"""
        # Mecab 객체는 직렬화하지 않음 (재생성 필요)
        return {'_dicpath': self._dicpath}

    def __setstate__(self, state):
        """pickle 역직렬화 시 호출"""
        self._dicpath = state.get('_dicpath')
        self._mecab = None
        # Mecab은 사용 시점에 lazy loading됨

    def __call__(self, value, positions=False, chars=False,
                 keeporiginal=False, removestops=True,
                 start_pos=0, start_char=0, mode='', **kwargs):
        """
        텍스트를 토큰화

        Args:
            value: 토큰화할 텍스트
            positions: 위치 정보 포함 여부
            chars: 문자 위치 정보 포함 여부

        Yields:
            Token 객체
        """
        assert isinstance(value, str), "Value must be string"

        # Mecab 형태소 분석
        morphs = self.mecab.morphs(value)

        # 토큰 생성
        token = Token(positions, chars, removestops=removestops, mode=mode)

        for pos, morph in enumerate(morphs):
            if not morph.strip():
                continue

            token.text = morph
            token.boost = 1.0

            if positions:
                token.pos = start_pos + pos

            if chars:
                token.startchar = start_char
                token.endchar = start_char + len(morph)
                start_char = token.endchar

            yield token


class WhooshIndexer:
    """표준계약서 청크를 위한 Whoosh 키워드 인덱서"""

    def __init__(self, index_path: Path):
        """
        Args:
            index_path: 인덱스 저장 경로
        """
        self.index_path = index_path
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 한국어 분석기 (검색 시 재사용)
        self.korean_analyzer = KoreanAnalyzer()

        # 스키마 정의 (analyzer 없이 - pickle 문제 방지)
        # 인덱싱 시에는 수동으로 토크나이징하여 저장
        from whoosh.analysis import StandardAnalyzer
        
        self.schema = Schema(
            id=ID(stored=True, unique=True),                              # 청크 ID
            global_id=ID(stored=True),                                    # 전역 ID
            text_norm=TEXT(analyzer=StandardAnalyzer(), stored=True),     # 정규화된 텍스트 (주 검색 대상)
            title=TEXT(analyzer=StandardAnalyzer(), stored=True),         # 조 제목 (검색 대상)
            text_raw=STORED,                                              # 원본 텍스트 (표시용)
            metadata=STORED                                               # 기타 메타데이터 (JSON)
        )

        # 인덱스 초기화
        logger.info(f"Whoosh 인덱스 초기화: {self.index_path}")
        index_exists = exists_in(str(self.index_path))
        logger.info(f"  인덱스 존재 여부: {index_exists}")

        if not index_exists:
            self.ix = create_in(str(self.index_path), self.schema)
            logger.warning(f"새로운 Whoosh 인덱스 생성됨 (기존 인덱스 없음): {self.index_path}")
        else:
            self.ix = open_dir(str(self.index_path))
            logger.info(f"기존 Whoosh 인덱스 열기 완료: {self.index_path}")

    def build(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Whoosh 인덱스 구축

        Args:
            chunks: 청크 리스트 (ClauseChunker에서 생성된 형식)
        """
        writer = self.ix.writer()

        for chunk in chunks:
            # 메타데이터를 JSON 문자열로 저장
            metadata = {
                'unit_type': chunk.get('unit_type', ''),
                'parent_id': chunk.get('parent_id', ''),
                'source_file': chunk.get('source_file', ''),
                'order_index': chunk.get('order_index', 0),
                'anchors': chunk.get('anchors', [])
            }
            metadata_json = json.dumps(metadata, ensure_ascii=False)

            # 텍스트를 MeCab으로 미리 토크나이징 (공백으로 구분)
            text_norm_tokenized = " ".join(self.korean_analyzer.mecab.morphs(chunk['text_norm']))
            title_tokenized = " ".join(self.korean_analyzer.mecab.morphs(chunk['title']))

            writer.add_document(
                id=chunk['id'],
                global_id=chunk['global_id'],
                text_norm=text_norm_tokenized,  # 토크나이징된 텍스트 저장
                title=title_tokenized,          # 토크나이징된 제목 저장
                text_raw=chunk['text_raw'],
                metadata=metadata_json
            )

        writer.commit()
        logger.info(f"Whoosh 인덱스 구축 완료: {len(chunks)}개 청크")

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
                # 진단: 인덱스 문서 개수 확인
                doc_count = searcher.doc_count_all()
                logger.debug(f"Whoosh 인덱스 총 문서 수: {doc_count}")

                if doc_count == 0:
                    logger.error(f"Whoosh 인덱스가 비어있습니다!")
                    return []

                # 한국어 쿼리를 MeCab으로 토크나이징
                # Whoosh의 기본 QueryParser는 공백 기반이므로 한국어에 적합하지 않음
                morphs = self.korean_analyzer.mecab.morphs(query)
                tokenized_query = " ".join(morphs)
                
                logger.debug(f"원본 쿼리: {query[:100]}...")
                logger.debug(f"토크나이징된 쿼리: {tokenized_query[:100]}...")

                # Whoosh 특수문자 이스케이프
                escaped_query = self._escape_query(tokenized_query)
                logger.debug(f"이스케이프된 쿼리: {escaped_query[:100]}...")

                # text_norm과 title 필드에서 검색
                from whoosh.qparser import QueryParser
                from whoosh.query import Or
                
                # 각 필드별로 쿼리 파싱
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
                    logger.debug(f"  이스케이프 후: {escaped_query[:100]}")

                    # 테스트: 전체 문서 샘플 확인
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
                # 파싱 실패 시 빈 결과 반환
                return []

    def _escape_query(self, query: str) -> str:
        """
        Whoosh 쿼리 특수문자 이스케이프

        Args:
            query: 원본 쿼리

        Returns:
            이스케이프된 쿼리
        """
        # Whoosh 특수문자: AND, OR, NOT, -, +, ^, ~, :, (, ), [, ], {, }, !, "
        # 대문자 불린 연산자는 공백으로 감싸진 경우만 의미가 있으므로 단어 단위로 체크
        import re

        # 괄호와 같은 특수문자만 이스케이프 (공백 유지)
        # 불린 연산자(AND, OR, NOT)는 단어 경계에서만 이스케이프
        special_chars = [':', '(', ')', '[', ']', '{', '}', '!', '"', '^', '~']

        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, f'\\{char}')

        # 불린 연산자 이스케이프 (단어 경계에서만)
        escaped = re.sub(r'\bAND\b', 'and', escaped)
        escaped = re.sub(r'\bOR\b', 'or', escaped)
        escaped = re.sub(r'\bNOT\b', 'not', escaped)

        return escaped

