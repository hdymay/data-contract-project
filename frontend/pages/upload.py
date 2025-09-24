"""
계약서 업로드 페이지
"""
import streamlit as st
from components.file_uploader import FileUploader
from components.contract_type_selector import ContractTypeSelector
from utils.api_client import APIClient

def show():
    """업로드 페이지 표시"""
    st.title("📄 계약서 업로드")
    st.markdown("검증하고자 하는 데이터 계약서를 업로드해주세요.")
    
    # 파일 업로드 컴포넌트
    file_uploader = FileUploader()
    uploaded_file = file_uploader.render()
    
    if uploaded_file:
        # 계약 유형 선택 컴포넌트
        contract_type_selector = ContractTypeSelector()
        contract_type = contract_type_selector.render()
        
        if contract_type:
            # 분석 시작 버튼
            if st.button("🔍 검증 시작", type="primary"):
                with st.spinner("계약서를 분석 중입니다..."):
                    # API 호출
                    api_client = APIClient()
                    result = api_client.analyze_contract(uploaded_file, contract_type)
                    
                    if result:
                        st.success("분석이 완료되었습니다!")
                        st.session_state['analysis_result'] = result
                        st.rerun()
                    else:
                        st.error("분석 중 오류가 발생했습니다.")
