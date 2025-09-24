"""
설정 페이지
"""
import streamlit as st

def show():
    """설정 페이지 표시"""
    st.title("⚙️ 설정")
    
    # API 설정
    st.subheader("API 설정")
    backend_url = st.text_input(
        "백엔드 URL",
        value="http://localhost:8000",
        help="FastAPI 백엔드 서버 URL"
    )
    
    # OpenAI 설정
    st.subheader("OpenAI 설정")
    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        help="OpenAI API 키를 입력하세요"
    )
    
    # 저장 버튼
    if st.button("설정 저장"):
        # TODO: 설정 저장 로직
        st.success("설정이 저장되었습니다!")
