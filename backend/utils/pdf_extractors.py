"""
PDF 추출기들
"""
from typing import Dict, Any
import io

class PaddlePaddleExtractor:
    """PaddlePaddle PP-DocLayout 추출기"""
    
    async def extract(self, file) -> Dict[str, Any]:
        """PDF에서 텍스트 및 레이아웃 추출"""
        try:
            # TODO: PaddlePaddle 구현
            # paddleocr import
            # layout detection
            # text extraction
            pass
        except Exception as e:
            raise Exception(f"PaddlePaddle 추출 실패: {e}")

class HURIDOSExtractor:
    """HURIDOS 추출기"""
    
    async def extract(self, file) -> Dict[str, Any]:
        """PDF에서 텍스트 및 레이아웃 추출"""
        try:
            # TODO: HURIDOS 구현
            # document layout analysis
            # text extraction
            pass
        except Exception as e:
            raise Exception(f"HURIDOS 추출 실패: {e}")
