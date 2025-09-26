import os
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="데이터 표준계약 검증",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def get_upload_dir() -> Path:
    # 프로젝트 루트의 data/uploads 경로 보장
    project_root = Path(__file__).resolve().parents[1]
    upload_dir = project_root / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_uploaded_file(uploaded_file) -> Path:
    upload_dir = get_upload_dir()
    safe_name = Path(uploaded_file.name).name
    target_path = upload_dir / safe_name
    with open(target_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return target_path


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

    file = st.file_uploader("PDF 파일을 업로드하세요", type=["pdf"], accept_multiple_files=False)

    if file is not None:
        if st.button("업로드하기", type="primary"):
            try:
                import requests
                backend_url = "http://localhost:8000/upload"
                files = {"file": (file.name, file.getvalue(), "application/pdf")}
                resp = requests.post(backend_url, files=files, timeout=60)
                if resp.status_code == 200 and resp.json().get("success"):
                    data = resp.json()
                    st.success("업로드 성공")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("파일명", f"`{data.get('filename')}`")
                    with col2:
                        st.write("크기", f"{len(file.getbuffer())/1024:.1f} KB")
                    st.code(str(data.get("path")), language="bash")
                else:
                    st.error(f"업로드 실패: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"연결 오류: {e}")


if __name__ == "__main__":
    main()


