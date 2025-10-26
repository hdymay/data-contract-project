# Implementation Plan

- [x] 1. 프로젝트 구조 및 기본 설정




  - backend/clause_verification 디렉토리 생성
  - 환경 변수 설정 파일 (config.py) 작성
  - 데이터 모델 정의 (models.py)
  - _Requirements: 1.1, 2.1, 3.1, 4.1_

- [x] 2. 데이터 전처리 및 청킹 개선

  - [x] 2.1 해설 데이터 구조화 스크립트 작성
    - create_structured_chunks.py 작성
    - parsed_43_73_table_5.json에서 해설(type="해설") 추출
    - 조별로 그룹화 (같은 title끼리 묶기)
    - \n\n 기준으로 문단 단위 분리
    - text_raw와 text_norm 필드 생성
    - parsed_43_73_table_5_structured.json 생성 (해설 데이터용)
    - _Requirements: 1.1, 3.1_

  - [x] 2.2 텍스트 정규화 로직 구현
    - normalize_text 함수 작성
    - 개행 제거, 특수문자 정리
    - 항 번호 패턴 제거
    - 공백 정규화
    - _Requirements: 3.1, 3.3_

  - [x] 2.3 표준 계약서 조문 데이터 준비
    - provide_std_contract_art_chunks.json 생성
    - 27개 조문 데이터 포함 (조문 비교 검증용)
    - 각 조문에 id, global_id, anchors 등 메타데이터 포함
    - _Requirements: 1.1, 3.1_

- [x] 3. 데이터 로더 구현

  - [x] 3.1 표준 계약서 조문 로드 기능 구현
    - data/chunked_documents/provide_std_contract_art_chunks.json 로드
    - 표준 계약서 조문(doc_type="std_contract") 파싱
    - ClauseData 모델로 변환
    - 세그먼트 분리 기능 추가 (//) 
    - _Requirements: 1.1, 3.1_
  
  - [ ] 3.2 해설 데이터 로드 기능 구현 (선택적)
    - data/chunked_documents/parsed_43_73_table_5_structured.json 로드
    - 해설 데이터(doc_type="usage_guide") 파싱
    - LLM 컨텍스트 보강용으로 활용
    - _Requirements: 1.1, 3.1_
  
  - [x] 3.3 사용자 계약서 텍스트 파싱 구현
    - 평문 텍스트를 입력받아 문단 단위로 분리
    - 각 문단을 ClauseData로 변환 (간단한 구조)
    - 텍스트 파일(.txt) 로드 지원
    - _Requirements: 1.1_

- [x] 4. Azure OpenAI 임베딩 서비스 구현












  - [x] 4.1 Azure OpenAI 클라이언트 초기화
    - 환경 변수에서 API 키 및 엔드포인트 로드
    - text-embedding-3-large 모델 설정
    - _Requirements: 1.1, 3.3_

  - [x] 4.2 텍스트 임베딩 생성 기능
    - 단일 텍스트 임베딩 생성
    - 배치 임베딩 생성 (API 호출 최적화)
    - _Requirements: 3.3_

- [x] 5. 하이브리드 검색 엔진 구현









  - [x] 5.1 BM25 인덱스 구축
    - rank-bm25 라이브러리 사용
    - 항 내용(text)으로 인덱스 생성
    - _Requirements: 3.1, 3.2_
  
  - [x] 5.2 FAISS 인덱스 구축 및 로드
    - 기존 ingestion/indexers/faiss_indexer.py 참고
    - 임베딩 벡터로 FAISS 인덱스 생성
    - 인덱스 저장 및 로드 기능
    - _Requirements: 3.1, 3.3_
  
  - [x] 5.3 하이브리드 검색 구현
    - BM25 점수 계산 (가중치 0.3)
    - FAISS 유사도 점수 계산 (가중치 0.7)
    - 점수 결합 및 top-k 후보 반환 (기본값: top-3)
    - 원점수 및 정규화 점수 모두 반환
    - _Requirements: 3.2, 3.3_

- [x] 6. LLM 검증 서비스 구현









  - [x] 6.1 Azure OpenAI LLM 클라이언트 초기화
    - gpt-4o 모델 설정
    - 프롬프트 템플릿 작성
    - _Requirements: 3.3_

  - [x] 6.2 조문 매칭 검증 기능
    - 표준 항과 후보 항의 의미적 일치 여부 판단
    - 신뢰도 점수 및 판단 근거 생성
    - VerificationDecision 모델 반환
    - _Requirements: 3.3_

- [x] 7. 검증 엔진 통합









  - [x] 7.1 전체 검증 워크플로우 구현
    - 표준 계약서 로드
    - 사용자 계약서 로드
    - 각 표준 항에 대해 하이브리드 검색 수행
    - LLM으로 최종 검증
    - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 3.3_

  - [x] 7.2 누락 조문 식별
    - 매칭 실패한 항 수집
    - VerificationResult 생성
    - _Requirements: 2.1, 2.2, 2.3_

- [ ] 8. 보고서 생성 기능 구현





  - [x] 8.1 텍스트 보고서 생성
    - 검증 결과 요약
    - 누락된 조문 목록 포맷팅
    - 텍스트 파일로 저장
    - _Requirements: 2.3, 4.1, 4.2, 5.1, 5.2, 5.3_

  - [x] 8.2 PDF 보고서 생성
    - reportlab 사용
    - 한글 폰트 설정
    - 검증 결과를 PDF로 생성
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 8.3 표준 준수율 계산 버그 수정



    - 조 단위와 항 단위 혼용 문제 해결
    - 역방향 검증에서 올바른 표준 준수율 계산
    - 매칭된 조문 수를 조 단위로 정확히 계산
    - 157.1% 오류 수정 → 50.0% 정확한 값으로 수정
    - _Requirements: 2.1, 4.1_

- [x] 9. CLI 인터페이스 구현 (ingestion CLI 통합)


  - [x] 9.1 검증 명령어 구현
    - ingestion CLI에 verify 명령어 통합
    - 표준 계약서 자동 로드 (data/chunked_documents/provide_std_contract_art_chunks.json)
    - 사용자 계약서 .txt 파일 입력 지원
    - 하이브리드 검색 + LLM 검증 파이프라인 완성
    - _Requirements: 1.1, 4.1, 5.3_
  
  - [x] 9.2 자동화된 파이프라인 구현
    - 한 줄 명령어로 전체 검증 프로세스 실행
    - FAISS + BM25 인덱스 자동 로드
    - 세그먼트 분리 기능 적용
    - 원점수 및 정규화 점��� 모두 출력
    - _Requirements: 1.1_
  
  - [x] 9.3 결과 출력 및 저장
    - 콘솔에 상세 검증 결과 출력 (매칭/누락 조문)
    - LLM 신뢰도 및 검색 점수 표시
    - 선택적 텍스트 보고서 파일 생성
    - 사용법: `python ingestion/ingest.py` → `verify -u <파일경로>`
    - _Requirements: 4.1, 4.2, 4.3, 5.4_

- [x] 10. 통합 테스트
  - [x] 10.1 전체 워크플로우 테스트
    - provide_std_contract_art_chunks.json을 표준 계약서로 사용
    - 테스트용 사용자 계약서 생성 (data/user_contract_sample.txt)
    - 검증 수행 및 결과 확인 (test_verification_simple.py)
    - 하이브리드 검색 + LLM 검증 파이프라인 완료
    - 세그먼트 분리로 정확도 향상
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4_
  
  - [x] 10.2 보고서 생성 테스트
    - 텍스트 보고서 생성 확인 (test_output6.txt)
    - 원점수 및 정규화 점수 출력 기능 추가
    - 한글 출력 정상 동작 확인
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
