import streamlit as st
import time
import requests


st.set_page_config(
    page_title="데이터 표준계약 검증",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def poll_classification_result(contract_id: str, max_attempts: int = 30, interval: int = 2):
    """
    분류 결과를 폴링하여 조회

    Args:
        contract_id: 계약서 ID
        max_attempts: 최대 시도 횟수 (기본 30회 = 1분)
        interval: 폴링 간격(초) (기본 2초)

    Returns:
        (success: bool, data: dict or None)
    """
    import requests

    for _ in range(max_attempts):
        try:
            classification_url = f"http://localhost:8000/api/classification/{contract_id}"
            class_resp = requests.get(classification_url, timeout=10)

            if class_resp.status_code == 200:
                return True, class_resp.json()
            elif class_resp.status_code == 404:
                # 아직 분류 완료되지 않음 - 계속 대기
                time.sleep(interval)
                continue
            else:
                # 오류 발생
                return False, {"error": f"HTTP {class_resp.status_code}: {class_resp.text}"}
        except Exception as e:
            return False, {"error": str(e)}

    # 타임아웃
    return False, {"error": "분류 작업이 너무 오래 걸립니다. 잠시 후 페이지를 새로고침해주세요."}


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

    # selectbox 텍스트 커서 제거 및 기본 포인터 유지 CSS
    st.markdown("""
        <style>
        /* selectbox의 input 요소에서 텍스트 커서 제거하고 기본 포인터 유지 */
        div[data-baseweb="select"] input {
            cursor: default !important;
            caret-color: transparent !important;
        }
        /* selectbox 전체 영역에서 기본 포인터 */
        div[data-baseweb="select"] {
            cursor: default !important;
        }
        /* selectbox 드롭다운 화살표 영역만 포인터 */
        div[data-baseweb="select"] svg {
            cursor: pointer !important;
        }
        </style>
    """, unsafe_allow_html=True)

    file = st.file_uploader("DOCX 파일을 업로드하세요", type=["docx"], accept_multiple_files=False)

    # session_state 초기화
    if 'uploaded_contract_data' not in st.session_state:
        st.session_state.uploaded_contract_data = None

    # 버튼 레이아웃: 파일 선택 또는 업로드 완료 시 표시
    if file is not None:
        is_classification_done = st.session_state.get('classification_done', False)
        col_btn1, _, col_btn3 = st.columns([2, 6, 2])

        with col_btn1:
            # 업로드하기 버튼 (분류 완료 시 secondary, 아니면 primary)
            upload_button_type = "secondary" if is_classification_done else "primary"
            upload_clicked = st.button("업로드하기", type=upload_button_type, use_container_width=False)

        with col_btn3:
            # 분류 완료 후에만 검증 버튼 표시
            if is_classification_done:
                validate_clicked = st.button("계약서 검증", type="primary", use_container_width=True)
                if validate_clicked:
                    # TODO: 검증 로직 구현 예정
                    pass

        # 업로드 버튼 클릭 처리
        if upload_clicked:
            try:
                backend_url = "http://localhost:8000/upload"
                files = {"file": (file.name, file.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                resp = requests.post(backend_url, files=files, timeout=60)

                if resp.status_code == 200 and resp.json().get("success"):
                    data = resp.json()
                    contract_id = data.get('contract_id')

                    # session_state에 업로드 데이터 저장
                    st.session_state.uploaded_contract_data = {
                        'contract_id': contract_id,
                        'filename': data.get('filename'),
                        'file_size': len(file.getbuffer()),
                        'parsed_metadata': data.get('parsed_metadata', {}),
                        'structured_data': data.get('structured_data', {})
                    }

                    # 분류 상태 초기화
                    st.session_state.classification_done = False

                    # 페이지 리렌더링 강제
                    st.rerun()

                else:
                    st.error(f"❌ 업로드 실패: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ 연결 오류: {e}")

    # session_state에 업로드된 데이터가 있으면 UI 표시
    if st.session_state.uploaded_contract_data is not None:
        uploaded_data = st.session_state.uploaded_contract_data
        contract_id = uploaded_data['contract_id']

        st.markdown('<div style="height: 2rem;"></div>', unsafe_allow_html=True)

        # 파일 정보
        col1, col2 = st.columns(2)
        with col1:
            st.write("**파일명**", f"`{uploaded_data['filename']}`")
        with col2:
            st.write("**크기**", f"{uploaded_data['file_size']/1024:.1f} KB")

        st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True)

        # 분류 결과 - 상태 표시
        status_placeholder = st.empty()

        # 분류가 아직 안된 경우에만 폴링
        if 'classification_done' not in st.session_state or not st.session_state.classification_done:
            # 초기 상태: 업로드 및 파싱 성공
            status_placeholder.success("업로드 및 파싱 성공")

            # 자동으로 분류 결과 조회
            with st.spinner("분류 작업이 진행 중입니다..."):
                success, result = poll_classification_result(contract_id)

            # 계약 유형 매핑
            type_names = {
                "provide": "데이터 제공형 계약",
                "create": "데이터 창출형 계약",
                "process": "데이터 가공서비스형 계약",
                "brokerage_provider": "데이터 중개거래형 계약 (제공자-운영자)",
                "brokerage_user": "데이터 중개거래형 계약 (이용자-운영자)"
            }

            if success:
                classification = result
                predicted_type = classification.get('predicted_type')
                confidence = classification.get('confidence', 0)

                # session_state에 분류 결과 저장
                st.session_state.classification_done = True
                st.session_state.predicted_type = predicted_type
                st.session_state.confidence = confidence
                st.session_state.user_modified = False  # AI 분류 결과

                # 검증 버튼을 렌더링하기 위해 페이지 리렌더링
                st.rerun()
            else:
                # 분류 실패
                status_placeholder.error(f"❌ 분류 실패: {result.get('error', '알 수 없는 오류')}")
                st.session_state.classification_done = False
        else:
            # 이미 분류가 완료된 경우 저장된 정보 표시
            type_names = {
                "provide": "데이터 제공형 계약",
                "create": "데이터 창출형 계약",
                "process": "데이터 가공서비스형 계약",
                "brokerage_provider": "데이터 중개거래형 계약 (제공자-운영자)",
                "brokerage_user": "데이터 중개거래형 계약 (이용자-운영자)"
            }
            predicted_type = st.session_state.predicted_type

            # 사용자가 수동으로 수정했는지 확인
            if st.session_state.get('user_modified', False):
                status_placeholder.success(f"분류 완료: **{type_names.get(predicted_type, predicted_type)}** (선택)")
            else:
                confidence = st.session_state.confidence
                status_placeholder.success(f"분류 완료: **{type_names.get(predicted_type, predicted_type)}** (신뢰도: {confidence:.1%})")

        # 파싱 메타데이터
        metadata = uploaded_data['parsed_metadata']

        st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True)

        # 분류 결과가 성공한 경우에만 유형 선택 UI 표시
        if st.session_state.get('classification_done', False):
            # 드롭다운으로 유형 선택
            def on_type_change():
                """드롭다운 선택 변경 시 호출되는 콜백"""
                selected = st.session_state[f"contract_type_{contract_id}"]
                original = st.session_state.get('predicted_type')

                if selected != original:
                    try:
                        confirm_url = f"http://localhost:8000/api/classification/{contract_id}/confirm?confirmed_type={selected}"
                        confirm_resp = requests.post(confirm_url, timeout=30)

                        if confirm_resp.status_code == 200:
                            st.session_state.predicted_type = selected  # 업데이트
                            st.session_state.user_modified = True  # 사용자가 수동으로 수정함
                    except Exception:
                        pass  # 오류 발생 시 무시

            st.selectbox(
                "계약서 유형",
                options=list(type_names.keys()),
                format_func=lambda x: type_names[x],
                index=list(type_names.keys()).index(st.session_state.get('predicted_type', predicted_type)) if st.session_state.get('predicted_type', predicted_type) in type_names else 0,
                key=f"contract_type_{contract_id}",
                on_change=on_type_change
            )

        st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True)

        # 계약서 구조 미리보기
        st.markdown('<p style="font-size: 0.875rem; font-weight: 400; margin-bottom: 0.5rem;">계약서 구조 미리보기</p>', unsafe_allow_html=True)
        with st.expander(f"인식된 조항: {metadata.get('recognized_articles', 0)}개"):
            # 좌우 패딩을 위한 마진 추가
            st.markdown("")  # 약간의 상단 여백

            structured_data = uploaded_data['structured_data']
            preamble = structured_data.get('preamble', [])
            articles = structured_data.get('articles', [])

            # Preamble 표시 (제1조 이전 텍스트)
            if preamble:
                # 첫 번째 문단 (제목) - 조금 크게
                if len(preamble) > 0:
                    st.markdown(f"<p style='font-size:1.15rem; font-weight:600; margin-bottom:0.5rem; margin-left:1rem; margin-right:1rem;'>{preamble[0]}</p>", unsafe_allow_html=True)

                # 나머지 문단들 - 작게 (줄바꿈 보존)
                if len(preamble) > 1:
                    for line in preamble[1:]:
                        # 줄바꿈을 <br>로 변환
                        line_with_br = line.replace('\n', '<br>')
                        st.markdown(f"<p style='font-size:0.85rem; margin:0.2rem 1rem; color:#d1d5db;'>{line_with_br}</p>", unsafe_allow_html=True)

            # 조항 목록
            if articles:
                st.divider()
                st.markdown(f"<p style='font-weight:600; margin-bottom:0.5rem; margin-left:1rem; margin-right:1rem;'><strong>총 {len(articles)}개 조항</strong></p>", unsafe_allow_html=True)

                # 모든 조항의 타이틀만 표시
                for i, article in enumerate(articles, 1):
                    st.markdown(f"<p style='margin:0.2rem 1rem;'>{i}. {article.get('text', 'N/A')}</p>", unsafe_allow_html=True)

                # 하단 여백
                st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
            else:
                st.warning("조항을 찾을 수 없습니다.")


if __name__ == "__main__":
    main()


