"""
계약 유형 선택 컴포넌트
"""
import streamlit as st

class ContractTypeSelector:
    """계약 유형 선택 컴포넌트"""
    
    def __init__(self):
        self.contract_types = [
            "데이터 제공형",
            "데이터 창출형",
            "데이터 가공서비스형",
            "데이터 중개거래형(운영자-제공자)",
            "데이터 중개거래형(운영자-이용자)"
        ]
    
    def render(self):
        """계약 유형 선택 UI 렌더링"""
        st.subheader("계약 유형 선택")
        
        # 자동 분류 결과 표시 (시뮬레이션)
        predicted_type = st.selectbox(
            "자동 분류 결과",
            options=self.contract_types,
            help="AI가 자동으로 분류한 계약 유형입니다. 필요시 수정할 수 있습니다."
        )
        
        # 수동 선택 옵션
        st.markdown("**수동 선택**")
        manual_type = st.radio(
            "직접 선택",
            options=self.contract_types,
            horizontal=True
        )
        
        # 최종 선택
        selected_type = st.selectbox(
            "최종 선택",
            options=self.contract_types,
            index=self.contract_types.index(predicted_type)
        )
        
        return selected_type
