# 프로젝트 현재 상태

## 개요
데이터 표준계약 검증 시스템 - 5종의 데이터 표준계약서를 기반으로 사용자 계약서를 검증하는 AI 시스템

## 완료된 작업

### 1. 사용자 계약서 DOCX 처리 파이프라인 ✅
- **파일**: `backend/fastapi/user_contract_parser.py`
- **기능**: 간단한 "제n조" 패턴 매칭으로 파싱
- **저장**: SQLite DB에 JSON으로 저장 (파일 저장 안 함)
- **API**: `POST /upload` - DOCX 업로드 및 파싱

### 2. 데이터 공유 및 DB 구성 ✅
- **공유 방식**: Docker 볼륨 마운트 (현재 구조 유지)
- **DB**: SQLite (`data/database/contracts.db`)
- **모델**: ContractDocument, ClassificationResult, ValidationResult, Report
- **지식베이스 로더**: `backend/shared/services/knowledge_base_loader.py`

### 3. 프론트엔드 업데이트 ✅
- **파일**: `frontend/app.py`
- **변경**: PDF → DOCX 업로드로 변경
- **표시**: 파싱 결과 및 메타데이터 표시

### 4. Spec 문서 작성 ✅
- **위치**: `.kiro/specs/system-enhancement/`
- **파일**: requirements.md, design.md, tasks.md
- **내용**: 전체 시스템 요구사항, 설계, 구현 계획

## 현재 상태

### 구현 완료
- ✅ 사용자 계약서 DOCX 파싱
- ✅ DB 모델 및 저장
- ✅ 지식베이스 로더 (파일 로드 유틸리티)
- ✅ FastAPI 기본 엔드포인트
- ✅ Docker 볼륨 데이터 공유

### 미구현 (다음 단계)
- ❌ Classification Agent (계약서 유형 분류)
- ❌ Consistency Validation Agent (정합성 검증)
- ❌ Report Agent (보고서 생성)
- ❌ Redis Queue 연동
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