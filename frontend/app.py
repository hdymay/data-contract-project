import streamlit as st
import requests


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

    # 파일 업로드 (PDF, DOCX, TXT 지원)
    file = st.file_uploader(
        "계약서 파일을 업로드하세요", 
        type=["pdf", "docx", "txt"], 
        accept_multiple_files=False,
        help="지원 형식: PDF, DOCX, TXT"
    )

    if file is not None:
        # 세션 상태 초기화
        if 'contract_id' not in st.session_state:
            st.session_state.contract_id = None
        if 'classification_done' not in st.session_state:
            st.session_state.classification_done = False
        if 'confirmed_type' not in st.session_state:
            st.session_state.confirmed_type = None
        
        # 디버깅: 현재 세션 상태 표시
        with st.sidebar:
            st.write("### 🔧 세션 상태")
            st.write(f"Contract ID: {st.session_state.get('contract_id', 'None')}")
            st.write(f"Classification Done: {st.session_state.get('classification_done', False)}")
            st.write(f"Confirmed Type: {st.session_state.get('confirmed_type', 'None')}")
        
        # 1단계: 업로드 및 파싱
        if st.button("업로드 및 분석 시작", type="primary"):
            try:
                file_ext = file.name.split('.')[-1].lower()
                
                # DOCX 파일인 경우 분류 기능 사용
                if file_ext == 'docx':
                    with st.spinner("파일 업로드 및 파싱 중..."):
                        backend_url = "http://localhost:8000/upload"
                        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        files = {"file": (file.name, file.getvalue(), mime_type)}
                        resp = requests.post(backend_url, files=files, timeout=60)
                    
                    if resp.status_code == 200 and resp.json().get("success"):
                        data = resp.json()
                        st.session_state.contract_id = data.get('contract_id')
                        
                        st.success("✅ 업로드 및 파싱 성공")
                        st.info(data.get('message', '분류 작업이 진행 중입니다.'))
                        
                        # 파일 정보
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**파일명**", f"`{data.get('filename')}`")
                        with col2:
                            st.write("**크기**", f"{len(file.getbuffer())/1024:.1f} KB")
                        
                        st.write(f"**계약서 ID**: `{st.session_state.contract_id}`")
                        
                        # 파싱 메타데이터
                        metadata = data.get('parsed_metadata', {})
                        st.write("**파싱 결과**")
                        st.write(f"- 인식된 조항: {metadata.get('recognized_articles', 0)}개")
                        # 파싱 신뢰도는 항상 1.0이므로 표시하지 않음
                        
                        # 구조화된 데이터 미리보기
                        with st.expander("📄 계약서 구조 미리보기"):
                            st.markdown("")
                            
                            structured_data = data.get('structured_data', {})
                            preamble = structured_data.get('preamble', [])
                            articles = structured_data.get('articles', [])
                            
                            # Preamble 표시
                            if preamble:
                                if len(preamble) > 0:
                                    st.markdown(f"<p style='font-size:1.15rem; font-weight:600; margin-bottom:0.5rem; margin-left:1rem; margin-right:1rem;'>{preamble[0]}</p>", unsafe_allow_html=True)
                                
                                if len(preamble) > 1:
                                    for line in preamble[1:]:
                                        line_with_br = line.replace('\n', '<br>')
                                        st.markdown(f"<p style='font-size:0.85rem; margin:0.2rem 1rem; color:#d1d5db;'>{line_with_br}</p>", unsafe_allow_html=True)
                            
                            # 조항 목록
                            if articles:
                                st.divider()
                                st.markdown(f"<p style='font-weight:600; margin-bottom:0.5rem; margin-left:1rem; margin-right:1rem;'><strong>총 {len(articles)}개 조항</strong></p>", unsafe_allow_html=True)
                                
                                for i, article in enumerate(articles, 1):
                                    st.markdown(f"<p style='margin:0.2rem 1rem;'>{i}. {article.get('text', 'N/A')}</p>", unsafe_allow_html=True)
                                
                                st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
                            else:
                                st.warning("조항을 찾을 수 없습니다.")
                    
                    else:
                        st.error(f"❌ 업로드 실패: {resp.status_code} - {resp.text}")
                
                else:
                    # PDF, TXT는 바로 검증으로 (분류 없이)
                    st.info("PDF/TXT 파일은 분류 없이 바로 검증을 진행합니다.")
                    st.session_state.classification_done = True
                    st.session_state.confirmed_type = "provide"  # 기본값
                    
            except Exception as e:
                st.error(f"❌ 연결 오류: {e}")
        
        # 2단계: 분류 결과 조회 (DOCX만)
        if st.session_state.contract_id and not st.session_state.classification_done:
            st.markdown("---")
            st.subheader("📋 계약서 분류 결과")
            
            if st.button("분류 결과 조회", type="secondary"):
                with st.spinner("분류 결과를 조회하는 중..."):
                    try:
                        classification_url = f"http://localhost:8000/api/classification/{st.session_state.contract_id}"
                        class_resp = requests.get(classification_url, timeout=30)
                        
                        if class_resp.status_code == 200:
                            classification = class_resp.json()
                            
                            # 계약 유형 매핑
                            type_names = {
                                "provide": "데이터 제공 계약",
                                "create": "데이터 생성 계약",
                                "process": "데이터 가공 계약",
                                "brokerage_provider": "데이터 중개 계약 (제공자용)",
                                "brokerage_user": "데이터 중개 계약 (이용자용)"
                            }
                            
                            predicted_type = classification.get('predicted_type')
                            confidence = classification.get('confidence', 0)
                            scores = classification.get('scores', {})
                            classification_method = classification.get('classification_method', 'unknown')
                            
                            # 분류 결과 표시
                            st.success(f"✅ 분류 완료: **{type_names.get(predicted_type, predicted_type)}**")
                            
                            # 신뢰도 표시 (분류 방법에 따라 다르게 표시)
                            if classification_method == 'embedding':
                                st.write(f"**분류 신뢰도**: {confidence:.2%} (임베딩 기반)")
                            elif classification_method == 'llm_fewshot':
                                st.write(f"**분류 신뢰도**: {confidence:.2%} (LLM 정밀 분석)")
                            else:
                                st.write(f"**분류 신뢰도**: {confidence:.2%}")
                            
                            # 각 유형별 점수 표시
                            with st.expander("📊 유형별 유사도 점수"):
                                for ctype, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                                    st.write(f"- {type_names.get(ctype, ctype)}: {score:.3f}")
                            
                            # 사용자 확인/수정 UI
                            st.markdown("### 분류 유형 확인")
                            st.write("AI가 분류한 유형이 맞는지 확인하거나 수정해주세요.")
                            
                            # 드롭다운으로 유형 선택
                            confirmed_type = st.selectbox(
                                "계약서 유형",
                                options=list(type_names.keys()),
                                format_func=lambda x: type_names[x],
                                index=list(type_names.keys()).index(predicted_type) if predicted_type in type_names else 0
                            )
                            
                            # 확인 버튼
                            if st.button("유형 확인 및 검증 준비", type="primary"):
                                try:
                                    confirm_url = f"http://localhost:8000/api/classification/{st.session_state.contract_id}/confirm?confirmed_type={confirmed_type}"
                                    st.write(f"🔗 API 호출: {confirm_url}")  # 디버깅
                                    
                                    with st.spinner("유형 확인 중..."):
                                        confirm_resp = requests.post(confirm_url, timeout=30)
                                    
                                    st.write(f"📡 응답 코드: {confirm_resp.status_code}")  # 디버깅
                                    
                                    if confirm_resp.status_code == 200:
                                        st.session_state.classification_done = True
                                        st.session_state.confirmed_type = confirmed_type
                                        
                                        if confirmed_type != predicted_type:
                                            st.success(f"✅ 유형이 **{type_names[confirmed_type]}**(으)로 수정되었습니다.")
                                        else:
                                            st.success("✅ 분류 유형이 확인되었습니다.")
                                        
                                        st.info("이제 아래에서 검증을 시작할 수 있습니다.")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ 확인 실패 ({confirm_resp.status_code}): {confirm_resp.text}")
                                except Exception as e:
                                    st.error(f"❌ 확인 오류: {e}")
                                    import traceback
                                    st.code(traceback.format_exc())
                        
                        elif class_resp.status_code == 404:
                            st.warning("⏳ 분류 작업이 아직 완료되지 않았습니다. 잠시 후 다시 조회해주세요.")
                        else:
                            st.error(f"❌ 분류 조회 실패: {class_resp.status_code} - {class_resp.text}")
                    
                    except Exception as e:
                        st.error(f"❌ 분류 조회 오류: {e}")
        
        # 3단계: 검증 실행
        # 분류가 완료되었거나 contract_id가 있으면 표시
        if st.session_state.get('classification_done') or st.session_state.get('contract_id'):
            st.markdown("---")
            st.subheader("🔍 계약서 검증")
            
            # 확인된 유형이 있으면 표시, 없으면 기본값 사용
            confirmed_type = st.session_state.get('confirmed_type', 'provide')
            st.info(f"선택된 계약 유형: **{confirmed_type}**")
            
            if not st.session_state.get('classification_done'):
                st.warning("⚠️ 분류 유형을 먼저 확인해주세요. 또는 기본 유형(provide)으로 진행할 수 있습니다.")
            
            # 디버깅 정보
            with st.expander("🔧 디버그 정보"):
                st.write(f"Contract ID: {st.session_state.get('contract_id')}")
                st.write(f"Classification Done: {st.session_state.get('classification_done')}")
                st.write(f"Confirmed Type: {st.session_state.get('confirmed_type')}")
            
            if st.button("검증 시작", type="primary"):
                try:
                    with st.spinner("검증 작업을 시작합니다..."):
                        # 정합성 검증 시작 API 호출
                        verify_url = f"http://localhost:8000/api/consistency/{st.session_state.contract_id}/start"
                        resp = requests.post(verify_url, timeout=30)
                    
                    if resp.status_code == 200:
                        result = resp.json()
                        
                        if result.get("success"):
                            task_id = result.get("task_id")
                            st.success(f"✅ 검증 작업이 시작되었습니다!")
                            st.info(f"Task ID: `{task_id}`")
                            st.info("검증이 백그라운드에서 진행 중입니다. 잠시 후 결과를 조회해주세요.")
                            
                            # 세션 상태에 task_id 저장
                            st.session_state.verification_task_id = task_id
                        else:
                            st.error("검증 시작 실패")
                    else:
                        error_detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type") == "application/json" else resp.text
                        st.error(f"검증 시작 실패: {error_detail}")
                        
                except requests.exceptions.Timeout:
                    st.error("⏱️ 검증 시작 시간 초과")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")
            
            # 검증 결과 조회
            if 'verification_task_id' in st.session_state:
                st.markdown("---")
                
                if st.button("검증 결과 조회", type="secondary"):
                    try:
                        with st.spinner("검증 결과를 조회하는 중..."):
                            result_url = f"http://localhost:8000/api/consistency/{st.session_state.contract_id}"
                            result_resp = requests.get(result_url, timeout=30)
                        
                        if result_resp.status_code == 200:
                            data = result_resp.json()
                            status = data.get("status")
                            
                            if status == "verified":
                                st.success("✅ 검증 완료!")
                                
                                # 보고서는 백그라운드에서 생성 중
                                st.info("📄 보고서가 백그라운드에서 생성 중입니다.")
                                st.info("잠시 후 서버의 `data/reports/{contract_id}` 폴더를 확인하세요.")
                                
                            elif status == "verifying":
                                st.warning("⏳ 검증이 진행 중입니다. 잠시 후 다시 조회해주세요.")
                            elif status == "verification_error":
                                st.error("❌ 검증 중 오류가 발생했습니다.")
                            else:
                                st.info(f"현재 상태: {status}")
                        else:
                            st.error(f"결과 조회 실패: {result_resp.status_code}")
                    
                    except Exception as e:
                        st.error(f"❌ 결과 조회 오류: {e}")


if __name__ == "__main__":
    main()
