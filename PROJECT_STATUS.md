# 프로젝트 현재 상태

## 개요
데이터 표준계약 검증 시스템 - 5종의 데이터 표준계약서를 기반으로 사용자 계약서를 검증하는 AI 시스템

## 완료된 작업

### 1. 사용자 계약서 DOCX 처리 파이프라인 ✅
- **파일**: `backend/fastapi/user_contract_parser.py`
- **기능**: 간단한 "제n조" 패턴 매칭으로 파싱 (계층 구조 무시)
- **저장**: SQLite DB에 JSON으로 저장 (파일 저장 안 함)
- **API**: `POST /upload` - DOCX 업로드 및 파싱
- **구조**: 조 단위로 파싱, 하위 항목은 평면 리스트로 저장
- **추가**: 서문(preamble) 수집 기능 (제1조 이전 텍스트)

### 2. 데이터 공유 및 DB 구성 ✅
- **공유 방식**: Docker 볼륨 마운트 (현재 구조 유지)
- **DB**: SQLite (`data/database/contracts.db`)
- **모델**: ContractDocument, ClassificationResult, ValidationResult, Report
- **지식베이스 로더**: `backend/shared/services/knowledge_base_loader.py`
- **API**: `GET /api/knowledge-base/status` - 지식베이스 상태 확인

### 3. Classification Agent 구현 ✅
- **파일**: `backend/classification_agent/agent.py`
- **기능**: 
  - RAG 기반 유사도 계산 (5종 표준계약서 각각)
  - LLM 기반 최종 분류 (Azure OpenAI GPT-4)
  - Celery Task 등록 및 비동기 처리
- **Celery Task**: `classification.classify_contract`
- **Queue**: `classification`
- **알려진 이슈**: Azure OpenAI 자격 증명 환경 변수 필요 (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT)

### 4. Celery 설정 및 Task 등록 ✅
- **파일**: `backend/shared/core/celery_app.py`
- **개선**: 
  - Task 자동 발견 설정 (`include` 추가)
  - Celery 설정 추가 (타임아웃, 시리얼라이저 등)
- **Agent __init__.py**: Classification, Consistency, Report Agent 모듈 초기화

### 5. FastAPI 엔드포인트 구현 ✅
- **파일**: `backend/fastapi/main.py`
- **엔드포인트**:
  - `POST /upload` - DOCX 업로드 및 파싱, 자동으로 분류 작업 큐에 전송
  - `GET /api/knowledge-base/status` - 지식베이스 상태 확인
  - `POST /api/classification/{contract_id}/start` - 분류 작업 수동 트리거
  - `GET /api/classification/{contract_id}` - 분류 결과 조회
  - `POST /api/classification/{contract_id}/confirm` - 사용자 분류 확인/수정

### 6. 프론트엔드 업데이트 ✅
- **파일**: `frontend/app.py`
- **변경**: PDF → DOCX 업로드로 변경
- **표시**: 
  - 파싱 결과 및 메타데이터 표시
  - 계약서 구조 미리보기 (서문 + 조항 목록)
  - 분류 결과 조회 및 표시
  - 유형별 유사도 점수 표시
  - 사용자 분류 확인/수정 UI

### 7. Spec 문서 작성 ✅
- **위치**: `.kiro/specs/system-enhancement/`
- **파일**: requirements.md, design.md, tasks.md
- **내용**: 전체 시스템 요구사항, 설계, 구현 계획

## 현재 상태

### 구현 완료
- ✅ 사용자 계약서 DOCX 파싱 (간단한 제n조 패턴)
- ✅ DB 모델 및 저장 (SQLite)
- ✅ 지식베이스 로더 (FAISS/Whoosh 인덱스 로드)
- ✅ FastAPI 엔드포인트 (업로드, 분류 시작, 분류 조회, 분류 확인)
- ✅ Docker 볼륨 데이터 공유
- ✅ Classification Agent (RAG + LLM 분류)
- ✅ Celery Task 등록 및 설정
- ✅ Redis Queue 연동 (업로드 시 자동 분류 작업 전송)
- ✅ 프론트엔드 분류 결과 표시 및 유형 변경 UI

### 테스트 필요
- ⚠️ Classification Agent 전체 플로우 테스트
  - Azure OpenAI 자격 증명 설정 필요
  - Celery Worker 동작 확인 필요
  - 실제 계약서로 분류 정확도 검증 필요

### 미구현 (다음 단계)
- ❌ Consistency Validation Agent (정합성 검증)
- ❌ Report Agent (보고서 생성)
- ❌ 활용안내서 처리 (Phase 2)

## 기술 스택
- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: Streamlit
- **AI**: Azure OpenAI (GPT-4, text-embedding-3-large)
- **검색**: FAISS (벡터) + Whoosh (키워드)
- **Queue**: Redis + Celery
- **Container**: Docker Compose

## 데이터 구조

### 사용자 계약서 파싱 결과
```json
{
  "articles": [
    {
      "number": 1,
      "title": "목적",
      "text": "제1조(목적)",
      "content": ["본 계약은...", "데이터이용자는..."]
    }
  ]
}
```

### 지식베이스 (Ingestion 결과)
```
data/
├── chunked_documents/         # *_chunks.json (5종)
├── search_indexes/
│   ├── faiss/                # *.faiss (5종)
│   └── whoosh/               # 디렉토리 (5종)
└── database/
    └── contracts.db          # SQLite
```

## 다음 작업 우선순위

1. **Classification Agent 구현**
   - KnowledgeBaseLoader 사용
   - RAG 기반 유사도 계산
   - LLM 기반 최종 분류

2. **HybridSearcher 통합**
   - 기존 ingestion/processors/searcher.py 활용
   - Multi-Vector 검색 (항/호 → 조 단위 집계)

3. **Consistency Validation Agent**
   - 3개 노드: 완전성, 체크리스트, 내용 분석
   - 맥락 기반 유연한 검증

## 중요 설계 원칙

1. **맥락 기반 유연한 검증**: 표준계약서와 다르더라도 의미적으로 유사하면 인정
2. **Phase 1 단순화**: 활용안내서 제외, 규격화된 DOCX만 지원
3. **Docker 볼륨 공유**: 별도 벡터 DB 없이 파일 기반 공유

## 테스트 방법

```bash
# 1. 지식베이스 구축
docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion

# 2. 서버 시작
docker-compose -f docker/docker-compose.yml up fast-api

# 3. 프론트엔드
streamlit run frontend/app.py

# 4. 상태 확인
curl http://localhost:8000/api/knowledge-base/status
```

## 문제 해결

- **지식베이스 없음**: ingestion CLI 실행 필요
- **DB 초기화 실패**: `rm data/database/contracts.db` 후 재시작
- **파싱 실패**: DOCX 파일이 "제n조" 형식인지 확인

---

**마지막 업데이트**: 2025-10-24
**다음 작업**: Classification Agent 구현