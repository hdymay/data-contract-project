"""
진행률 추적 컴포넌트
"""
import streamlit as st

class ProgressTracker:
    """진행률 추적 컴포넌트"""
    
    def __init__(self):
        self.steps = [
            "파일 업로드",
            "PDF 추출",
            "계약 유형 분류",
            "정합성 검증",
            "리포트 생성"
        ]
    
    def render(self, progress_data):
        """진행률 UI 렌더링"""
        st.subheader("분석 진행 상황")
        
        # 전체 진행률
        overall_progress = progress_data.get('overall', 0)
        st.progress(overall_progress / 100)
        st.write(f"전체 진행률: {overall_progress}%")
        
        # 단계별 진행률
        for i, step in enumerate(self.steps):
            step_progress = progress_data.get(f'step_{i}', 0)
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(step)
            with col2:
                st.write(f"{step_progress}%")
        
        # 현재 단계 표시
        current_step = progress_data.get('current_step', '')
        if current_step:
            st.info(f"현재 단계: {current_step}")
