"""
PDF 처리 서비스
"""
import uuid
from typing import Dict, Any
from utils.pdf_extractors import PaddlePaddleExtractor, HURIDOSExtractor

class PDFProcessor:
    """PDF 처리 서비스"""
    
    def __init__(self):
        self.extractors = {
            "paddlepaddle": PaddlePaddleExtractor(),
            "huridos": HURIDOSExtractor()
        }
    
    async def process_file(self, file) -> Dict[str, Any]:
        """PDF 파일 처리"""
        try:
            # 파일 ID 생성
            file_id = str(uuid.uuid4())
            
            # PDF 추출 (PaddlePaddle 사용)
            extractor = self.extractors["paddlepaddle"]
            extracted_data = await extractor.extract(file)
            
            return {
                "file_id": file_id,
                "extracted_text": extracted_data.get("text"),
                "layout_info": extracted_data.get("layout"),
                "status": "success"
            }
            
        except Exception as e:
            return {
                "file_id": None,
                "error": str(e),
                "status": "failed"
            }
