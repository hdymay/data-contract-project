"""
분석 결과 페이지
"""
import streamlit as st
from components.report_display import ReportDisplay
from components.progress_tracker import ProgressTracker

def show():
    """분석 결과 페이지 표시"""
    st.title("📊 분석 결과")
    
    # 분석 결과 확인
    if 'analysis_result' not in st.session_state:
        st.warning("아직 분석 결과가 없습니다. 계약서를 업로드하고 분석을 시작해주세요.")
        return
    
    analysis_result = st.session_state['analysis_result']
    
    # 진행률 표시
    progress_tracker = ProgressTracker()
    progress_tracker.render(analysis_result.get('progress', {}))
    
    # 결과 표시
    report_display = ReportDisplay()
    report_display.render(analysis_result)
