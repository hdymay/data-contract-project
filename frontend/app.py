"""
데이터 표준계약 검증 에이전트 - Streamlit 메인 앱
"""
import streamlit as st
import os
from pages import upload, analysis, settings

# 페이지 설정
st.set_page_config(
    page_title="데이터 표준계약 검증 에이전트",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """메인 애플리케이션"""
    # 사이드바
    st.sidebar.title("📊 데이터 표준계약 검증 에이전트")
    st.sidebar.markdown("AI 기반 데이터 계약서 분석 및 검증 도구")
    
    # 페이지 선택
    page = st.sidebar.selectbox(
        "페이지 선택",
        ["계약서 업로드", "분석 결과", "설정"]
    )
    
    # 페이지 라우팅
    if page == "계약서 업로드":
        upload.show()
    elif page == "분석 결과":
        analysis.show()
    elif page == "설정":
        settings.show()

if __name__ == "__main__":
    main()
