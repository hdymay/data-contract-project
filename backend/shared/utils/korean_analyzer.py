"""
한국어 형태소 분석기 (공통 모듈)
Ingestion과 Backend 모두에서 사용
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class KoreanTokenizer:
    """
    한국어 형태소 분석기
    MeCab을 사용하여 텍스트를 토크나이징
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

            # mecab-ko-dic 사전 경로 찾기
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

    def tokenize(self, text: str) -> List[str]:
        """
        텍스트를 형태소로 분리
        
        Args:
            text: 입력 텍스트
            
        Returns:
            형태소 리스트
        """
        return self.mecab.morphs(text)
