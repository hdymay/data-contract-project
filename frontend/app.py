import streamlit as st


st.set_page_config(
    page_title="데이터 표준계약 검증",
    page_icon="",
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

    file = st.file_uploader("DOCX 파일을 업로드하세요", type=["docx"], accept_multiple_files=False)

    if file is not None:
        if st.button("업로드하기", type="primary"):
            try:
                import requests
                backend_url = "http://localhost:8000/upload"
                files = {"file": (file.name, file.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                resp = requests.post(backend_url, files=files, timeout=60)
                
                if resp.status_code == 200 and resp.json().get("success"):
                    data = resp.json()
                    contract_id = data.get('contract_id')

                    st.success("업로드 및 파싱 성공")
                    st.info(data.get('message', '분류 작업이 진행 중입니다.'))

                    # 파일 정보
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**파일명**", f"`{data.get('filename')}`")
                    with col2:
                        st.write("**크기**", f"{len(file.getbuffer())/1024:.1f} KB")

                    st.write(f"**계약서 ID**: `{contract_id}`")

                    # 파싱 메타데이터
                    metadata = data.get('parsed_metadata', {})
                    st.write("**파싱 결과**")
                    st.write(f"- 인식된 조항: {metadata.get('recognized_articles', 0)}개")
                    st.write(f"- 신뢰도: {metadata.get('confidence', 0):.2%}")

                    # 구조화된 데이터 미리보기 (조 타이틀 전체 목록)
                    with st.expander("📄 계약서 구조 미리보기"):
                        # 좌우 패딩을 위한 마진 추가
                        st.markdown("")  # 약간의 상단 여백

                        structured_data = data.get('structured_data', {})
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

                    # 분류 결과 섹션
                    st.markdown("---")
                    st.subheader("📋 계약서 분류 결과")

                    # 분류 결과 조회 버튼
                    if st.button("분류 결과 조회", type="primary"):
                        with st.spinner("분류 결과를 조회하는 중..."):
                            try:
                                classification_url = f"http://localhost:8000/api/classification/{contract_id}"
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

                                    # 분류 결과 표시
                                    st.success(f"✅ 분류 완료: **{type_names.get(predicted_type, predicted_type)}**")
                                    st.write(f"**신뢰도**: {confidence:.2%}")

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
                                    if st.button("유형 확인", type="secondary"):
                                        try:
                                            confirm_url = f"http://localhost:8000/api/classification/{contract_id}/confirm?confirmed_type={confirmed_type}"
                                            confirm_resp = requests.post(confirm_url, timeout=30)

                                            if confirm_resp.status_code == 200:
                                                if confirmed_type != predicted_type:
                                                    st.success(f"✅ 유형이 **{type_names[confirmed_type]}**(으)로 수정되었습니다.")
                                                else:
                                                    st.success("✅ 분류 유형이 확인되었습니다.")

                                                st.info("다음 단계: 정합성 검증이 진행됩니다. (미구현)")
                                            else:
                                                st.error(f"❌ 확인 실패: {confirm_resp.text}")
                                        except Exception as e:
                                            st.error(f"❌ 확인 오류: {e}")

                                elif class_resp.status_code == 404:
                                    st.warning("⏳ 분류 작업이 아직 완료되지 않았습니다. 잠시 후 다시 조회해주세요.")
                                else:
                                    st.error(f"❌ 분류 조회 실패: {class_resp.status_code} - {class_resp.text}")

                            except Exception as e:
                                st.error(f"❌ 분류 조회 오류: {e}")

                else:
                    st.error(f"❌ 업로드 실패: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ 연결 오류: {e}")


if __name__ == "__main__":
    main()


