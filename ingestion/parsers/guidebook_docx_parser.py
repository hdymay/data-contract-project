"""
활용안내서 DOCX 파서 (미구현)
"""

from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class GuidebookDocxParser:
    """활용안내서 DOCX 파서 (미구현)"""
    
    def __init__(self):
        pass
    
    def parse(self, docx_path: Path, output_dir: Path) -> Dict[str, Path]:
        """
        활용안내서 DOCX를 파싱하여 구조화된 데이터 반환
        
        Args:
            docx_path: DOCX 파일 경로
            output_dir: 출력 디렉토리
            
        Returns:
            파싱된 결과 파일 경로 딕셔너리
        """
        logger.warning("활용안내서 DOCX 파서는 아직 구현되지 않았습니다.")
        # TODO: 구현
        return {}

