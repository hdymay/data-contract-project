import streamlit as st


st.set_page_config(
    page_title="데이터 표준계약 검증",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    # 상단 헤더
    st.markdown(
        """
        <div style="text-align:center; margin-top: 0.5rem;">
            <div style="text-align:center; font-size:3rem; font-weight:800; margin-bottom:0.5rem;">데이터 표준계약 검증</div>
            <p style="color:#6b7280;">계약서를 업로드하고 표준계약 기반 AI분석 보고서를 확인하세요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown('<div style="height: 3rem;"></div>', unsafe_allow_html=True)

    file = st.file_uploader(
        "계약서 파일을 업로드하세요", 
        type=["pdf", "docx", "txt"], 
        accept_multiple_files=False,
        help="지원 형식: PDF, DOCX, TXT"
    )

    if file is not None:
        if st.button("업로드 및 검증 시작", type="primary"):
            try:
                import requests
                
                # 파일 타입에 따른 MIME 타입 설정
                mime_types = {
                    "pdf": "application/pdf",
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "txt": "text/plain"
                }
                file_ext = file.name.split('.')[-1].lower()
                mime_type = mime_types.get(file_ext, "application/octet-stream")
                
                # 검증 진행 중 메시지
                with st.spinner("검증 진행 중... (1-2분 소요)"):
                    backend_url = "http://localhost:8000/verify"
                    files = {"file": (file.name, file.getvalue(), mime_type)}
                    resp = requests.post(backend_url, files=files, timeout=180)
                
                if resp.status_code == 200:
                    result = resp.json()
                    
                    if result.get("success"):
                        # 검증 완료 메시지
                        st.success("✅ 검증 완료!")
                        
                        # 검증 결과 요약
                        summary = result.get("verification_summary", {})
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            compliance_rate = summary.get("compliance_rate", 0)
                            st.metric("검증 완료율", f"{compliance_rate:.1f}%")
                        
                        with col2:
                            matched = summary.get("matched_clauses", 0)
                            st.metric("매칭 조항", f"{matched}개")
                        
                        with col3:
                            missing = summary.get("missing_clauses", 0)
                            st.metric("누락 조항", f"{missing}개")
                        
                        # 실행 시간
                        exec_time = result.get("execution_time", 0)
                        st.caption(f"⏱️ 실행 시간: {exec_time:.1f}초")
                        
                        # 리포트 다운로드 버튼
                        report_id = result.get("report_id")
                        if report_id:
                            report_url = f"http://localhost:8000/report/{report_id}"
                            
                            try:
                                report_resp = requests.get(report_url, timeout=30)
                                if report_resp.status_code == 200:
                                    st.download_button(
                                        label="📄 검증 리포트 다운로드",
                                        data=report_resp.content,
                                        file_name=f"verification_report_{report_id}.txt",
                                        mime="text/plain"
                                    )
                                    
                                    # 상세 결과 표시
                                    with st.expander("📋 상세 검증 결과 보기"):
                                        st.text(report_resp.text)
                            except Exception as e:
                                st.warning(f"리포트 다운로드 준비 중 오류: {e}")
                    else:
                        st.error("검증 실패")
                else:
                    error_detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type") == "application/json" else resp.text
                    st.error(f"검증 실패: {error_detail}")
                    
            except requests.exceptions.Timeout:
                st.error("⏱️ 검증 시간 초과 (3분). 파일이 너무 크거나 서버가 응답하지 않습니다.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()


