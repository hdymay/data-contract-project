# Implementation Plan - Consistency Agent A3 Node

## Overview

A3 노드(Content Analysis) 구현을 위한 태스크 목록입니다. 각 태스크는 독립적으로 실행 가능하며, 순차적으로 진행됩니다.

## Tasks

- [ ] 1. 기본 인프라 및 데이터 모델 구현
- [x] 1.1 ArticleAnalysis 데이터 클래스 구현


  - dataclass로 단일 조항 분석 결과 구조 정의
  - 매칭 정보, 평가 점수, 분석 결과, 제안 필드 포함
  - _Requirements: 6.1, 6.2_

- [x] 1.2 ContentAnalysisResult 데이터 클래스 구현

  - 전체 계약서 분석 결과 구조 정의
  - 조항별 분석 리스트, 전체 평가, 통계 포함
  - _Requirements: 6.1, 6.2_

- [x] 1.3 ValidationResult DB 모델 확인 및 수정


  - 기존 ValidationResult 모델이 A3 결과를 저장할 수 있는지 확인
  - 필요시 content_analysis 필드 추가 (JSON 타입)
  - _Requirements: 6.3_

- [ ] 2. ArticleMatcher 구현 (멀티벡터 검색)
- [x] 2.1 ArticleMatcher 클래스 기본 구조 구현


  - __init__ 메서드: KnowledgeBaseLoader, similarity_threshold 초기화
  - 조별 청크 개수 캐싱 딕셔너리 초기화
  - 기본 속성 및 로거 설정
  - _Requirements: 1.1, 1.2_

- [ ] 2.2 사용자 하위항목 정규화 로직 구현
  - _normalize_sub_item 메서드 구현
  - 앞뒤 공백 제거 (strip)
  - ①②③ 원문자, 1. 2. 3. 번호, (가) (나) 괄호 번호 제거
  - _Requirements: 1.1_

- [ ] 2.3 검색 쿼리 생성 로직 구현
  - _build_search_query 메서드 구현
  - 하위항목 전체 내용 + 조 제목 (제목은 뒤에 배치)
  - 예: "{sub_item} {article_title}"
  - _Requirements: 1.1_

- [ ] 2.4 조별 청크 개수 캐싱 구현
  - 초기화 시 표준계약서 chunks.json에서 parent_id별 개수 계산
  - article_chunk_counts 딕셔너리에 저장
  - 예: {"제1조": 1, "제2조": 6, "제3조": 4, ...}
  - _Requirements: 1.1, 7.2_

- [ ] 2.5 멀티벡터 검색 구현
  - _search_with_sub_items 메서드 구현
  - 사용자 조항의 각 하위항목(content 배열)으로 개별 검색
  - 각 하위항목마다 Top-10 청크 검색 (FAISS 0.85 + Whoosh 0.15)
  - 모든 하위항목의 검색 결과를 조 단위로 취합
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2.6 조 단위 취합 로직 구현
  - _aggregate_chunks_to_articles 메서드 구현
  - Top-10 청크를 parent_id로 그룹화
  - 정규화된 평균 점수 계산: avg_score / sqrt(total_chunks)
  - 점수 순 정렬하여 Top-1 조 선택
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2.7 표준계약서 조의 모든 청크 로드 구현
  - _load_full_article_chunks 메서드 구현
  - 해당 parent_id의 모든 청크 반환 (조 본문 + 모든 하위항목)
  - _Requirements: 1.5_

- [ ] 2.8 특수 조항 감지 로직 구현
  - 최종 조 점수 < 0.7인 경우 is_special=True 반환
  - 특수 조항 플래그 및 로깅
  - _Requirements: 1.4, 5.1_

- [ ] 3. ContentComparator 구현 (LLM 기반 내용 비교)
- [ ] 3.1 ContentComparator 클래스 기본 구조 구현
  - __init__ 메서드: AzureOpenAI 클라이언트 초기화
  - 기본 속성 및 로거 설정
  - _Requirements: 2.1_

- [ ] 3.2 LLM 프롬프트 생성 로직 구현
  - _build_comparison_prompt 메서드 구현
  - 맥락 기반 유연한 평가를 위한 프롬프트 템플릿 작성
  - 표준 조항과 사용자 조항을 프롬프트에 포함
  - _Requirements: 2.1, 3.1, 3.2, 3.3_

- [ ] 3.3 LLM 호출 및 응답 파싱 구현
  - compare_articles 메서드 구현
  - Azure OpenAI GPT-4 호출
  - JSON 응답 파싱 (completeness, clarity, practicality, missing_elements 등)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 3.4 에러 처리 및 재시도 로직 구현
  - LLM API 호출 실패 시 지수 백오프로 재시도 (최대 3회)
  - 재시도 실패 시 기본값 반환 (모든 점수 0.5)
  - 에러 로깅
  - _Requirements: 7.4, 8.3_

- [ ] 4. SuggestionGenerator 구현 (개선 제안 생성)
- [ ] 4.1 SuggestionGenerator 클래스 기본 구조 구현
  - __init__ 메서드: AzureOpenAI 클라이언트 초기화
  - 기본 속성 및 로거 설정
  - _Requirements: 4.1_

- [ ] 4.2 개선 제안 생성 프롬프트 작성
  - LLM 프롬프트 템플릿 작성
  - 누락 요소, 불명확한 점, 실무적 문제를 입력으로 사용
  - 구체적 제안, 예시 문구, 참조 위치 요청
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.3 LLM 호출 및 제안 생성 구현
  - generate_suggestions 메서드 구현
  - Azure OpenAI GPT-4 호출
  - JSON 배열 응답 파싱
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 4.4 제안 우선순위 정렬 구현
  - _prioritize_suggestions 메서드 구현
  - risk_level과 type을 기준으로 정렬 (high > medium > low)
  - _Requirements: 4.3_

- [ ] 5. SpecialArticleHandler 구현 (특수 조항 처리)
- [ ] 5.1 SpecialArticleHandler 클래스 기본 구조 구현
  - __init__ 메서드: AzureOpenAI 클라이언트 초기화
  - 기본 속성 및 로거 설정
  - _Requirements: 5.1_

- [ ] 5.2 특수 조항 분석 프롬프트 작성
  - LLM 프롬프트 템플릿 작성
  - 조항 목적, 적절성, 법적 리스크, 권장 조치 요청
  - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [ ] 5.3 특수 조항 분석 구현
  - analyze_special_article 메서드 구현
  - Azure OpenAI GPT-4 호출
  - JSON 응답 파싱 (is_appropriate, purpose, assessment, recommendation)
  - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [ ] 6. ContentAnalysisNode 메인 클래스 구현
- [ ] 6.1 ContentAnalysisNode 클래스 기본 구조 구현
  - __init__ 메서드: 의존성 주입 (KnowledgeBaseLoader, AzureOpenAI)
  - 하위 컴포넌트 초기화 (ArticleMatcher, ContentComparator 등)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 6.2 단일 조항 분석 로직 구현
  - analyze_article 메서드 구현
  - ArticleMatcher로 대응 조항 검색 (멀티벡터 방식)
  - 매칭 성공 시: 매칭된 조들의 모든 청크 로드 → ContentComparator + SuggestionGenerator 호출
  - 매칭 실패 시: SpecialArticleHandler 호출
  - ArticleAnalysis 객체 생성 및 반환
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 6.3 전체 계약서 분석 로직 구현
  - analyze_contract 메서드 구현
  - 사용자 계약서의 모든 조항을 순회하며 analyze_article 호출
  - 전체 평균 점수 계산 (completeness, clarity, practicality)
  - ContentAnalysisResult 객체 생성 및 반환
  - _Requirements: 6.1, 6.2_

- [ ] 6.4 진행 상황 로깅 구현
  - 각 조항 분석 시작/완료 로그
  - 전체 분석 시작/완료 로그
  - 처리 시간 측정 및 로그
  - _Requirements: 8.1, 8.2, 8.4_

- [ ] 7. DB 저장 및 통합
- [ ] 7.1 ValidationResult 저장 로직 구현
  - ContentAnalysisResult를 JSON으로 직렬화
  - ValidationResult 테이블에 저장
  - contract_id 연결
  - _Requirements: 6.3_

- [ ] 7.2 에러 처리 및 재시도 구현
  - DB 저장 실패 시 재시도 (최대 3회)
  - 부분 결과 저장 로직
  - 에러 로깅
  - _Requirements: 6.5, 8.3, 8.5_

- [ ] 7.3 Celery Task 등록
  - backend/consistency_agent/agent.py에 Celery task 구현
  - analyze_contract_content_task 함수 작성
  - Redis 큐에서 작업 수신 및 ContentAnalysisNode 호출
  - _Requirements: 6.4_

- [ ] 8. 성능 최적화
- [ ] 8.1 지식베이스 캐싱 구현
  - KnowledgeBaseLoader의 캐싱 기능 활용
  - 인덱스 재로드 방지
  - _Requirements: 7.2_

- [ ] 8.2 표준계약서 원본 캐싱 구현
  - 첫 로드 시 메모리에 캐싱
  - 동일 contract_type 재사용
  - _Requirements: 7.2_

- [ ] 8.3 배치 처리 검토 (선택적)
  - 여러 조항을 한 번에 LLM에 전송 가능한지 검토
  - 현재는 순차 처리로 구현
  - _Requirements: 7.3_

- [ ] 9. 테스트 및 검증
- [ ] 9.1 ArticleMatcher 단위 테스트 작성
  - 다양한 유사도 케이스 테스트
  - 특수 조항 감지 테스트
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 9.2 ContentComparator 단위 테스트 작성
  - LLM 응답 파싱 테스트
  - 에러 처리 테스트
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 9.3 SuggestionGenerator 단위 테스트 작성
  - 제안 생성 로직 테스트
  - 우선순위 정렬 테스트
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 9.4 SpecialArticleHandler 단위 테스트 작성
  - 특수 조항 분류 테스트
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 9.5 ContentAnalysisNode 통합 테스트 작성
  - 전체 분석 플로우 테스트
  - 지식베이스 로더 연동 테스트
  - DB 저장 및 조회 테스트
  - _Requirements: 모든 요구사항_

- [ ] 9.6 E2E 테스트 작성
  - 실제 계약서 샘플로 전체 분석
  - 다양한 계약 유형 테스트 (5종)
  - 성능 측정 (20개 조항 < 5분)
  - _Requirements: 7.1_

- [ ] 10. API 엔드포인트 구현 (선택적)
- [ ] 10.1 FastAPI 엔드포인트 추가
  - POST /api/validation/{contract_id}/start - A3 분석 시작
  - GET /api/validation/{contract_id}/content-analysis - A3 결과 조회
  - _Requirements: 6.4_

- [ ] 10.2 프론트엔드 연동 (Phase 2)
  - Streamlit에 A3 결과 표시 페이지 추가
  - 조항별 분석 결과 시각화
  - 개선 제안 표시
  - _Requirements: 6.4_

- [ ] 11. 문서화
- [ ] 11.1 코드 주석 및 docstring 작성
  - 모든 클래스 및 메서드에 docstring 추가
  - 복잡한 로직에 인라인 주석 추가
  - _Requirements: 모든 요구사항_

- [ ] 11.2 사용 가이드 작성
  - A3 노드 실행 방법
  - 환경 변수 설정
  - 트러블슈팅 가이드
  - _Requirements: 모든 요구사항_

- [ ] 11.3 PROJECT_STATUS.md 업데이트
  - A3 노드 구현 완료 상태 반영
  - 다음 단계 (A1, A2 노드) 명시
  - _Requirements: 모든 요구사항_

---

## Implementation Notes

### 실행 순서
1. **기본 인프라** (Task 1): 데이터 모델 정의
2. **핵심 컴포넌트** (Task 2-5): ArticleMatcher, ContentComparator, SuggestionGenerator, SpecialArticleHandler
3. **메인 클래스** (Task 6): ContentAnalysisNode 통합
4. **DB 및 Celery** (Task 7): 저장 및 비동기 처리
5. **최적화** (Task 8): 성능 개선
6. **테스트** (Task 9): 단위/통합/E2E 테스트
7. **API 및 문서화** (Task 10-11): 엔드포인트 및 문서

### 의존성
- Task 2-5는 Task 1 완료 후 병렬 진행 가능
- Task 6은 Task 2-5 완료 후 진행
- Task 7은 Task 6 완료 후 진행
- Task 8-11은 Task 7 완료 후 진행

### 테스트 전략
- 각 컴포넌트 구현 후 즉시 단위 테스트 작성
- 통합 테스트는 메인 클래스 완성 후 작성
- E2E 테스트는 전체 시스템 통합 후 작성

### Phase 1 범위
- A3 노드 단독 구현 (A1, A2 제외)
- 활용안내서 제외 (표준계약서만 사용)
- 순차 처리 (병렬 처리 제외)
- 기본 API 엔드포인트 (프론트엔드 연동은 Phase 2)

### 예상 소요 시간
- Task 1-2: 2-3시간
- Task 3-5: 4-6시간
- Task 6: 3-4시간
- Task 7: 2-3시간
- Task 8: 1-2시간
- Task 9: 4-5시간
- Task 10-11: 2-3시간
- **총 예상 시간**: 18-26시간
