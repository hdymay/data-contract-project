# Implementation Plan

- [ ] 1. 활용안내서 지식베이스 구축
- [ ] 1.1 활용안내서 DOCX 파서 구현
  - guidebook_docx_parser.py에 파싱 로직 구현
  - 조문별 해설, 조문비교표, 체크리스트 섹션 구분
  - 구조화된 JSON 출력 (guidebook_structured.json)
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 1.2 활용안내서 청커 구현
  - guidebook_chunker.py 생성
  - commentary, comparison, checklist 청크 타입별 처리
  - 계약 유형별 필터링 가능하도록 메타데이터 구성
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 1.3 활용안내서 임베딩 및 인덱싱
  - 기존 TextEmbedder 및 WhooshIndexer 재사용
  - 계약 유형별 독립 인덱스 생성 (5개)
  - ingestion CLI에 활용안내서 처리 명령 추가
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. 사용자 계약서 처리 파이프라인
- [x] 2.1 사용자 계약서 DOCX 파서 구현
  - user_contract_parser.py 생성 완료
  - 간단한 "제n조" 패턴 매칭 구현 (Phase 1)
  - 서문(preamble) 수집 기능 추가
  - 파싱 신뢰도 메타데이터 포함
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 2.2 사용자 계약서 청킹
  - 기존 ClauseChunker 재사용
  - 항/호 단위 청킹 및 anchors 생성
  - _Requirements: 2.1, 2.2, 2.3_
  - _Note: Phase 1에서는 청킹 없이 조 단위로만 처리_

- [x] 2.3 FastAPI 엔드포인트 구현
  - POST /upload: DOCX 파일 업로드 및 파싱 완료
  - Redis Queue에 Classification 작업 자동 전달 완료
  - 작업 상태 추적 로직 구현 완료
  - _Requirements: 2.1, 2.2, 2.3, 8.1, 8.2_

- [x] 3. Classification Agent 구현
- [x] 3.1 RAG 기반 유사도 계산
  - 사용자 계약서 주요 조항 추출 (처음 5개 조항)
  - 5종 표준계약서 인덱스에서 각각 검색
  - 유형별 평균 유사도 점수 산출
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3.2 LLM 기반 최종 분류
  - Few-shot prompting 구현
  - RAG 검색 결과를 컨텍스트로 제공
  - 분류 이유(reasoning) 생성 (내부 로깅용)
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3.3 Celery Task 및 Redis 통신
  - classification_agent/agent.py에 Celery task 구현 완료
  - Redis에서 작업 수신 및 결과 저장 완료
  - DB에 분류 결과 저장 완료
  - _Requirements: 3.1, 3.2, 3.3, 8.1, 8.2, 8.3_
  - _Note: Consistency Agent 연동은 미구현_

- [x] 3.4 프론트엔드 분류 확인 UI
  - 분류 결과 표시 페이지 구현 완료
  - 신뢰도 점수 및 유형별 점수 표시 완료
  - 유형 변경 드롭다운 및 확인 버튼 완료
  - _Requirements: 3.4, 3.5, 3.6_

- [ ] 4. Multi-Vector 검색 시스템 개선
- [ ] 4.1 조 단위 집계 로직 검증
  - 기존 HybridSearcher의 _aggregate_results_by_article() 검증
  - WeightedPooling 전략 테스트
  - 특수 조항 감지 로직 추가 (점수 임계값 0.5)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.2 유연한 매칭 전략 구현
  - 사용자 계약서 1개 조 → 표준계약서 여러 조 매칭
  - 여러 조 내용이 합쳐진 경우 부분 점수 산출
  - 표준계약서에 없는 조항 "특수 조항" 플래그
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 9.1, 9.2, 9.3_


- [ ] 5. Consistency Validation Agent 구현
- [ ] 5.1 Node A1: Completeness Check 구현
  - 표준계약서 조 목록 추출
  - 사용자 계약서에서 대응 조항 검색 (제목 + 내용 기반)
  - 매칭 상태 분류 (present, partial, absent, merged)
  - 조항 커버리지 계산
  - _Requirements: 5.1, 5.2, 9.1, 9.2, 9.3_

- [ ] 5.2 Node A2: Checklist Validation 구현
  - 계약 유형별 체크리스트 로드
  - 각 항목에 대해 RAG 검색 수행
  - LLM으로 항목 충족 여부 판단
  - 충족도 점수 및 증거 추출
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 5.3 Node A3: Content Analysis 구현
  - 사용자 계약서 각 조항에 대해 표준계약서 + 활용안내서 검색
  - LLM으로 내용 비교 (완전성, 명확성, 실무적 적절성)
  - 누락 요소 및 개선 제안 생성
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 5.4 맥락 기반 검증 로직 구현
  - 의미적 유사도 기반 조항 매칭
  - 내용 기반 검증 (다른 조항에 포함 여부 확인)
  - 특수 목적 감지 및 특이사항 분류
  - 유연한 판단 기준 적용
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 5.5 Celery Task 및 Redis 통신
  - consistency_agent/agent.py에 Celery task 구현
  - 3개 노드 순차 실행
  - 검증 결과 구조화 및 저장
  - Report Agent로 작업 전달
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 8.1, 8.2, 8.3_

- [ ] 6. Report Agent 구현
- [ ] 6.1 QA: Over-Standardization Check
  - fail/warning 항목 추출
  - 사용자 계약서 전체 맥락 재검토
  - 과도한 규격화 감지 및 심각도 조정
  - _Requirements: 6.1, 6.2_

- [ ] 6.2 QA: Missing Issue Detection
  - 사용자 계약서 전체 재스캔
  - 법적 리스크 높은 항목 체크
  - 발견된 이슈 검증 결과에 추가
  - _Requirements: 6.1, 6.2_

- [ ] 6.3 보고서 생성
  - 검증 결과를 사용자 친화적 보고서로 변환
  - 전체 평가 요약 (점수, 등급, 요약문)
  - 이슈 목록 (심각도별 분류)
  - 긍정적 평가 및 개선 권장사항
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.4 Feedback Loop 구현
  - 과도한 규격화 또는 누락 문제 발견 시 Consistency Agent로 피드백
  - 재검증 요청 메시지 생성
  - 최대 2회 반복 제한
  - _Requirements: 6.1, 6.2_

- [ ] 6.5 Celery Task 및 Redis 통신
  - report_agent/agent.py에 Celery task 구현
  - QA 프로세스 실행
  - 최종 보고서 생성 및 저장
  - FastAPI로 결과 전달
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.4_

- [ ] 7. Frontend 통합
- [ ] 7.1 업로드 페이지 개선
  - DOCX 파일 업로드 UI
  - 진행 상황 표시 (파싱 → 분류 → 검증 → 보고서)
  - 실시간 상태 업데이트
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 7.2 보고서 표시 페이지 구현
  - 전체 평가 요약 표시
  - 이슈 목록 (심각도별 필터링)
  - 이슈 상세 보기 (클릭 시 확장)
  - 긍정적 평가 및 개선 권장사항 표시
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 7.3 보고서 다운로드 기능
  - PDF 다운로드 구현
  - DOCX 다운로드 구현
  - 다운로드 버튼 UI
  - _Requirements: 7.4_

- [x] 8. API 엔드포인트 구현
- [x] 8.1 GET /api/classification/{contract_id}
  - 분류 결과 및 신뢰도 반환 완료
  - _Requirements: 3.4, 3.5_

- [x] 8.2 POST /api/classification/{contract_id}/confirm
  - 사용자 선택 유형 저장 완료
  - _Requirements: 3.5, 3.6_
  - _Note: Consistency Agent 연동은 미구현_

- [ ] 8.3 GET /api/validation/{contract_id}/status
  - 검증 진행 상황 반환
  - _Requirements: 8.2_

- [ ] 8.4 GET /api/report/{contract_id}
  - 최종 보고서 JSON 반환
  - _Requirements: 8.4_

- [ ] 8.5 GET /api/report/{contract_id}/download
  - PDF/DOCX 파일 다운로드
  - _Requirements: 7.4_

- [x] 9. 데이터 모델 및 DB 스키마
- [x] 9.1 ContractDocument 모델 구현
  - SQLAlchemy 모델 정의 완료
  - _Requirements: 2.1, 2.2, 2.3_
  - _Note: Alembic 마이그레이션은 미사용 (SQLite 자동 생성)_

- [x] 9.2 ClassificationResult 모델 구현
  - SQLAlchemy 모델 정의 완료
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - _Note: Alembic 마이그레이션은 미사용 (SQLite 자동 생성)_

- [x] 9.3 ValidationResult 모델 구현
  - SQLAlchemy 모델 정의 완료
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - _Note: 아직 사용되지 않음_

- [x] 9.4 Report 모델 구현
  - SQLAlchemy 모델 정의 완료
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - _Note: 아직 사용되지 않음_

- [ ] 10. 에러 처리 및 로깅
- [ ] 10.1 파싱 에러 처리
  - 사용자 계약서 파싱 실패 시 fallback
  - 활용안내서 파싱 실패 시 시스템 알림
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 10.2 Classification 에러 처리
  - 낮은 신뢰도(<0.5) 시 사용자 수동 선택 요청
  - RAG 검색 실패 시 fallback
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 10.3 Validation 에러 처리
  - 검색 인덱스 unavailable 시 재시도
  - LLM API 실패 시 재시도 (최대 3회)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 10.4 Report 에러 처리
  - QA 프로세스 실패 시 원본 검증 결과 사용
  - PDF/DOCX 생성 실패 시 JSON 다운로드 옵션
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 10.5 Redis Queue 에러 처리
  - 메시지 손실 방지 (DB 상태 저장)
  - Worker 실패 시 Celery 자동 재시도
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 11. 테스트 및 검증
- [ ] 11.1 활용안내서 파이프라인 테스트
  - 파싱 정확도 검증
  - 청킹 로직 검증
  - 인덱스 생성 검증
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 11.2 Classification 정확도 테스트
  - 5종 표준계약서로 분류 테스트
  - 변형된 계약서 샘플로 테스트
  - 신뢰도 점수 검증
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 11.3 Validation 품질 테스트
  - 실제 계약서 샘플로 검증 테스트
  - 맥락 기반 검증 로직 검증
  - 과도한 규격화 방지 검증
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 11.4 End-to-End 시스템 테스트
  - 전체 파이프라인 통합 테스트
  - 다양한 계약 유형 및 형식 테스트
  - 성능 테스트 (검증 시간, 메모리 사용량)
  - _Requirements: 모든 요구사항_

- [ ] 12. 문서화 및 배포 준비
- [ ] 12.1 스티어링 문서 업데이트
  - 활용안내서 처리 방법 추가
  - 맥락 기반 검증 원칙 명시
  - 에러 처리 가이드 추가
  - _Requirements: 모든 요구사항_

- [ ] 12.2 README 업데이트
  - 시스템 아키텍처 다이어그램
  - 설치 및 실행 가이드
  - API 문서
  - _Requirements: 모든 요구사항_

- [ ] 12.3 Docker Compose 설정 검증
  - 모든 서비스 정상 실행 확인
  - 환경 변수 설정 검증
  - 볼륨 마운트 확인
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_


---

## Implementation Notes

### Execution Order

위 태스크 목록은 논리적 순서로 작성되었으나, 실제 구현은 다음 우선순위로 진행:

**Phase 1: Core Validation Pipeline (활용안내서 및 복잡한 파싱 제외)**
1. 사용자 계약서 간단 파싱 (규격화된 샘플 DOCX 사용)
2. Classification Agent 구현
3. Multi-Vector 검색 개선
4. Consistency Validation Agent 구현 (표준계약서만 사용)
5. Report Agent 구현
6. Frontend 통합 및 API 엔드포인트

**Phase 2: Advanced Features (추후 구현)**
1. 활용안내서 파싱, 청킹, 인덱싱
2. 사용자 계약서 고도화 파싱 (VLM 기반 유연한 파싱)
3. 활용안내서 통합 검증

### Simplified User Contract Parsing

Phase 1에서는 사용자 계약서를 다음과 같이 간소화:
- 규격화된 샘플 DOCX만 지원 (자체 제작)
- 조 제목: "제n조(제목)" 형식 통일
- 항: "①, ②, ③" 형식 통일
- 호: "1., 2., 3." 형식 통일
- 기존 표준계약서 파서(StdContractDocxParser) 재사용 가능

Phase 2에서 VLM 기반 유연한 파싱으로 전환:
- 다양한 형식의 계약서 지원
- 비정형 구조 인식
- 이미지 기반 레이아웃 분석

### Guidebook Exclusion

Phase 1에서는 활용안내서 관련 태스크 제외:
- Task 1.1, 1.2, 1.3 제외
- Consistency Validation에서 표준계약서만 참조
- Checklist Validation 제외 (활용안내서 필요)

Phase 2에서 활용안내서 통합:
- 활용안내서 파싱 및 인덱싱
- Checklist Validation 추가
- Content Analysis에 활용안내서 해설 통합

### Flexibility

이 spec은 가이드라인이며, 구현 중 다음 사항은 유연하게 조정 가능:
- 태스크 순서 변경
- 요구사항 수정 (requirements.md 업데이트)
- 설계 변경 (design.md 업데이트)
- 태스크 추가/삭제

중요한 변경사항은 spec 문서에 반영하여 일관성 유지.
