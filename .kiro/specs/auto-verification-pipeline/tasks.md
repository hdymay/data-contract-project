# Implementation Plan

- [ ] 1. VerificationPipelineService 구현
  - 기존 검증 로직을 API에서 사용할 수 있도록 래핑하는 서비스 클래스
  - `backend/clause_verification/verification_pipeline_service.py` 파일 생성
  - 기존 ContractDataLoader, ContractVerificationEngine, ReportGenerator 재사용
  - _Requirements: 1.4, 5.1, 5.2_

- [ ] 1.1 파이프라인 서비스 구현
  - `VerificationPipelineService` 클래스 생성
  - `run_pipeline(user_contract_path, output_format)` 메서드 구현
  - 기존 CLI 로직(`ingestion/ingest.py`의 `do_verify`)을 참고하여 API용으로 래핑
  - 단계: 텍스트 파싱 → ContractDataLoader로 ClauseData 변환 → VerificationEngine 실행 → ReportGenerator 호출
  - 실행 시간 측정 및 로깅
  - 오류 처리 (파싱 실패, 검증 실패 등)
  - _Requirements: 1.2, 1.4, 1.5, 4.1, 4.4, 4.5, 5.1, 5.2_

- [ ] 2. FastAPI 엔드포인트 구현
  - `/verify` 및 `/report/{report_id}` 엔드포인트 추가
  - `backend/fastapi/main.py` 수정
  - _Requirements: 1.1, 1.5, 3.1, 3.2_

- [ ] 2.1 VerificationPipelineService 초기화
  - FastAPI 앱 시작 시 VerificationPipelineService 인스턴스 생성
  - 의존성 주입 (EmbeddingService, VerificationEngine, ReportGenerator)
  - 표준 계약서 및 FAISS 인덱스 사전 로드 (캐싱)
  - _Requirements: 5.1_

- [ ] 2.2 /verify 엔드포인트 구현
  - `POST /verify` 엔드포인트 추가
  - 파일 업로드 처리 (UploadFile)
  - 파일 형식 검증 (PDF, DOCX, TXT)
  - 파일 크기 제한 (최대 10MB)
  - 임시 파일 저장 (`data/source_documents/`)
  - VerificationPipelineService.run_pipeline() 호출
  - 검증 결과 요약 반환 (매칭률, 매칭 조항 수, 누락 조항 수)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 2.3 /report/{report_id} 엔드포인트 구현
  - `GET /report/{report_id}` 엔드포인트 추가
  - report_id로 리포트 파일 경로 찾기
  - FileResponse로 리포트 파일 반환
  - 파일이 없을 경우 404 반환
  - _Requirements: 3.2, 3.3_

- [ ] 2.4 오류 처리 및 로깅 추가
  - 각 엔드포인트에 try-except 블록 추가
  - HTTPException으로 적절한 HTTP 상태 코드 반환
  - 오류 로깅 (logger.error)
  - _Requirements: 2.3, 4.1, 4.2, 4.3_

- [ ] 3. Streamlit 프론트엔드 업데이트
  - 검증 버튼 및 결과 표시 UI 추가
  - `frontend/app.py` 수정
  - _Requirements: 1.1, 2.2, 2.4, 3.3, 3.4, 3.5_

- [ ] 3.1 업로드 버튼을 "업로드 및 검증 시작"으로 변경
  - 기존 "업로드하기" 버튼을 "업로드 및 검증 시작"으로 변경
  - 버튼 클릭 시 `/verify` 엔드포인트 호출
  - _Requirements: 1.1_

- [ ] 3.2 검증 진행 상태 표시
  - `st.spinner()`로 "검증 진행 중... (1-2분 소요)" 메시지 표시
  - 백엔드 응답 대기
  - _Requirements: 2.2, 2.4_

- [ ] 3.3 검증 결과 요약 표시
  - 검증 완료 후 `st.success("✅ 검증 완료!")` 메시지 표시
  - 3개 컬럼으로 매칭률, 매칭 조항 수, 누락 조항 수 표시 (`st.metric()`)
  - _Requirements: 2.4, 3.4_

- [ ] 3.4 리포트 다운로드 버튼 추가
  - `st.download_button()`으로 리포트 다운로드 버튼 추가
  - `/report/{report_id}` 엔드포인트에서 리포트 파일 가져오기
  - 파일명: `verification_report_{report_id}.txt`
  - _Requirements: 3.2, 3.3_

- [ ] 3.5 상세 결과 expander 추가
  - `st.expander()`로 "📋 상세 검증 결과 보기" 추가
  - 리포트 전체 내용을 `st.text()`로 표시
  - _Requirements: 3.5_

- [ ] 3.6 오류 처리 추가
  - 백엔드 응답이 실패한 경우 `st.error()` 메시지 표시
  - 연결 오류 처리 (timeout, connection error)
  - _Requirements: 2.3_

- [ ] 4. 데이터 모델 추가 (선택사항)
  - API 응답용 데이터 구조 정의
  - 기존 VerificationResult를 그대로 사용하거나, 필요시 래퍼 클래스 추가
  - _Requirements: 5.2_

- [ ]* 4.1 VerificationPipelineResult 클래스 추가
  - `backend/clause_verification/node_1_clause_matching/models.py`에 추가
  - `@dataclass` 데코레이터 사용
  - 필드: success, report_path, verification_result, execution_time, error
  - `to_dict()` 메서드: JSON 직렬화용
  - _Requirements: 5.2_

- [ ] 5. 통합 테스트
  - 전체 플로우 테스트 (업로드 → 검증 → 리포트 다운로드)
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 3.2, 3.3_

- [ ] 5.1 TXT 파일 E2E 테스트
  - `data/user_contract_sample.txt` 파일로 테스트
  - Streamlit에서 업로드 → 검증 → 결과 확인 → 리포트 다운로드
  - 매칭률, 매칭 조항 수, 누락 조항 수 정상 표시 확인
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 3.3, 3.4, 3.5_

- [ ]* 6. 문서화
  - README 업데이트 (선택사항)
  - _Requirements: 5.5_

- [ ]* 6.1 README 업데이트
  - 자동 검증 기능 사용법 추가
  - Streamlit 실행 방법 업데이트
  - _Requirements: 5.5_
