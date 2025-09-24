"""
파일 업로드 컴포넌트
"""
import streamlit as st

class FileUploader:
    """파일 업로드 컴포넌트"""
    
    def __init__(self):
        self.accepted_types = ["pdf"]
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def render(self):
        """파일 업로드 UI 렌더링"""
        uploaded_file = st.file_uploader(
            "PDF 파일을 선택하거나 드래그하여 업로드",
            type=self.accepted_types,
            help="최대 10MB, PDF 형식만 지원됩니다."
        )
        
        if uploaded_file:
            # 파일 정보 표시
            st.success(f"파일 업로드 완료: {uploaded_file.name}")
            st.info(f"파일 크기: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            # 파일 크기 검증
            if uploaded_file.size > self.max_file_size:
                st.error("파일 크기가 10MB를 초과합니다.")
                return None
                
        return uploaded_file
