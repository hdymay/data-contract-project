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
    KoNLPy의 Mecab 사용, 없으면 간단한 토크나이저로 폴백
    """

    def __init__(self):
        """형태소 분석기 초기화"""
        self.use_mecab = False
        try:
            from konlpy.tag import Mecab
            self.mecab = Mecab()
            self.use_mecab = True
            logger.info("KoNLPy Mecab을 사용합니다")
        except (ImportError, Exception) as e:
            logger.warning(f"Mecab을 사용할 수 없습니다. 기본 토크나이저를 사용합니다: {e}")

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

        if self.use_mecab:
            # Mecab 형태소 분석
            morphs = self.mecab.morphs(value)
        else:
            # 폴백: 공백과 특수문자로 단순 분리
            import re
            morphs = re.findall(r'[\w]+', value)

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

        # 한국어 분석기
        korean_analyzer = KoreanAnalyzer()

        # 스키마 정의 (심플하게)
        self.schema = Schema(
            id=ID(stored=True, unique=True),                        # 청크 ID
            global_id=ID(stored=True),                              # 전역 ID
            text_norm=TEXT(analyzer=korean_analyzer, stored=True),  # 정규화된 텍스트 (주 검색 대상)
            title=TEXT(analyzer=korean_analyzer, stored=True),      # 조 제목 (검색 대상)
            text_raw=STORED,                                        # 원본 텍스트 (표시용)
            metadata=STORED                                         # 기타 메타데이터 (JSON)
        )

        # 인덱스 초기화
        if not exists_in(str(self.index_path)):
            self.ix = create_in(str(self.index_path), self.schema)
            logger.info(f"새로운 Whoosh 인덱스 생성: {self.index_path}")
        else:
            self.ix = open_dir(str(self.index_path))
            logger.info(f"기존 Whoosh 인덱스 열기: {self.index_path}")

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

            writer.add_document(
                id=chunk['id'],
                global_id=chunk['global_id'],
                text_norm=chunk['text_norm'],
                title=chunk['title'],
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
            # text_norm과 title 필드에서 검색
            parser = MultifieldParser(["text_norm", "title"], schema=self.schema)
            parsed_query = parser.parse(query)

            # 검색 실행
            results = searcher.search(parsed_query, limit=top_k)

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

