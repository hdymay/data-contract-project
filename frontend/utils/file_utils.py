"""
파일 처리 유틸리티
"""
import tempfile
import os
from typing import Optional

class FileUtils:
    """파일 처리 유틸리티"""
    
    @staticmethod
    def save_uploaded_file(uploaded_file) -> Optional[str]:
        """업로드된 파일을 임시 저장"""
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                return tmp_file.name
        except Exception:
            return None
    
    @staticmethod
    def cleanup_temp_file(file_path: str):
        """임시 파일 정리"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass
    
    @staticmethod
    def validate_file_size(file, max_size_mb: int = 10) -> bool:
        """파일 크기 검증"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return file.size <= max_size_bytes
    
    @staticmethod
    def get_file_info(file) -> dict:
        """파일 정보 추출"""
        return {
            "name": file.name,
            "size": file.size,
            "type": file.type
        }
