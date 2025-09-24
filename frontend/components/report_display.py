"""
리포트 표시 컴포넌트
"""
import streamlit as st

class ReportDisplay:
    """리포트 표시 컴포넌트"""
    
    def render(self, analysis_result):
        """분석 결과 표시"""
        # 종합 점수
        st.subheader("📊 종합 분석 결과")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("종합 점수", f"{analysis_result.get('overall_score', 0)}/100")
        with col2:
            st.metric("일치 조항", analysis_result.get('matched_clauses', 0))
        with col3:
            st.metric("누락 조항", analysis_result.get('missing_clauses', 0))
        
        # 탭으로 결과 분류
        tab1, tab2, tab3, tab4 = st.tabs(["분류 결과", "정합성 검증", "발견된 이슈", "권장사항"])
        
        with tab1:
            self._render_classification_result(analysis_result.get('classification', {}))
        
        with tab2:
            self._render_validation_result(analysis_result.get('validation', {}))
        
        with tab3:
            self._render_issues(analysis_result.get('issues', []))
        
        with tab4:
            self._render_recommendations(analysis_result.get('recommendations', []))
    
    def _render_classification_result(self, classification_result):
        """분류 결과 표시"""
        st.write("**계약 유형:**", classification_result.get('contract_type', 'N/A'))
        st.write("**신뢰도:**", f"{classification_result.get('confidence', 0)}%")
        st.write("**분류 근거:**", classification_result.get('reasoning', 'N/A'))
    
    def _render_validation_result(self, validation_result):
        """정합성 검증 결과 표시"""
        for node, result in validation_result.items():
            st.subheader(f"노드 {node}")
            st.write(f"점수: {result.get('score', 0)}/100")
            st.write(f"상태: {result.get('status', 'N/A')}")
    
    def _render_issues(self, issues):
        """발견된 이슈 표시"""
        for issue in issues:
            st.error(f"**{issue.get('title', 'N/A')}**")
            st.write(issue.get('description', 'N/A'))
    
    def _render_recommendations(self, recommendations):
        """권장사항 표시"""
        for rec in recommendations:
            st.info(f"**{rec.get('title', 'N/A')}**")
            st.write(rec.get('description', 'N/A'))
