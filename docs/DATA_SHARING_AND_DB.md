# 데이터 공유 및 DB 구성

## 개요

Ingestion에서 생성한 지식베이스(인덱스, 청크)를 Backend 및 Agent 컨테이너에서 공유하는 방법과 DB 구성을 설명합니다.

## 데이터 공유 전략

### Docker 볼륨 마운트 (현재 구조)

모든 컨테이너가 동일한 데이터 디렉토리를 공유합니다:

```yaml
volumes:
  - ../data:/app/data
  - ../data/search_indexes:/app/search_indexes
```

### 디렉토리 구조

```
data/
├── source_documents/          # 원본 표준계약서 (ingestion 입력)
├── extracted_documents/       # 파싱된 structured.json (ingestion 출력)
├── chunked_documents/         # 청킹된 chunks.json (ingestion 출력)
│   ├── provide_std_contract_chunks.json
│   ├── create_std_contract_chunks.json
│   ├── process_std_contract_chunks.json
│   ├── brokerage_provider_std_contract_chunks.json
│   └── brokerage_user_std_contract_chunks.json
├── search_indexes/            # FAISS + Whoosh 인덱스 (ingestion 출력)
│   ├── faiss/
│   │   ├── provide_std_contract.faiss
│   │   ├── create_std_contract.faiss
│   │   ├── process_std_contract.faiss
│   │   ├── brokerage_provider_std_contract.faiss
│   │   └── brokerage_user_std_contract.faiss
│   └── whoosh/
│       ├── provide_std_contract/
│       ├── create_std_contract/
│       ├── process_std_contract/
│       ├── brokerage_provider_std_contract/
│       └── brokerage_user_std_contract/
├── user_contracts/            # 사용자 업로드 계약서 (backend 입력/출력)
│   ├── parsed/                # 파싱된 사용자 계약서
│   └── temp/                  # 임시 업로드 파일
└── database/                  # SQLite DB 파일
    └── contracts.db
```

## 지식베이스 로더

### KnowledgeBaseLoader 클래스

**위치**: `backend/shared/services/knowledge_base_loader.py`

**기능**:
- FAISS 인덱스 로드 및 캐싱
- Whoosh 인덱스 로드
- 청크 메타데이터 로드 및 캐싱
- 지식베이스 상태 확인

**사용 예시**:

```python
from backend.shared.services import get_knowledge_base_loader

# 싱글톤 인스턴스 가져오기
loader = get_knowledge_base_loader()

# FAISS 인덱스 로드
faiss_index = loader.load_faiss_index('provide')

# 청크 메타데이터 로드
chunks = loader.load_chunks('provide')

# Whoosh 인덱스 로드
whoosh_indexer = loader.load_whoosh_index('provide')

# 지식베이스 상태 확인
status = loader.verify_knowledge_base()
# {
#     "status": "ok" | "incomplete" | "missing",
#     "available_types": ["provide", "create", ...],
#     "missing_types": [],
#     "details": {...}
# }
```

### API 엔드포인트

**GET /api/knowledge-base/status**

지식베이스 상태 확인:

```bash
curl http://localhost:8000/api/knowledge-base/status
```

응답:
```json
{
  "status": "ok",
  "available_types": ["provide", "create", "process", "brokerage_provider", "brokerage_user"],
  "missing_types": [],
  "details": {
    "provide": {
      "faiss": true,
      "chunks": true,
      "whoosh": true
    },
    ...
  }
}
```

## 데이터베이스 구성

### SQLite 사용

**이유**:
- ✅ 프로토타입/개발 단계에 최적
- ✅ 설정 간단 (별도 DB 서버 불필요)
- ✅ 파일 기반이라 Docker 볼륨으로 쉽게 공유
- ✅ 동시 접속이 많지 않은 시스템에 적합
- ✅ 실제 운영 고려하지 않으므로 충분

**위치**: `data/database/contracts.db`

### 데이터 모델

**위치**: `backend/shared/database.py`

#### 1. ContractDocument
사용자 계약서 문서

```python
{
    "contract_id": str,          # Primary Key
    "filename": str,
    "upload_date": datetime,
    "file_path": str,            # 임시 파일 경로
    "parsed_data": JSON,         # 파싱된 구조화 데이터
    "parsing_metadata": JSON,    # 파싱 메타데이터
    "status": str                # uploaded, parsing, parsed, classifying, ...
}
```

#### 2. ClassificationResult
계약서 분류 결과

```python
{
    "id": int,                   # Primary Key
    "contract_id": str,          # Foreign Key
    "predicted_type": str,       # provide, create, process, ...
    "confidence": float,
    "scores": JSON,              # 각 유형별 점수
    "reasoning": str,            # 분류 이유 (내부 로깅용)
    "user_override": str,        # 사용자가 수정한 유형
    "confirmed_type": str,       # 최종 확정된 유형
    "created_at": datetime
}
```

#### 3. ValidationResult
정합성 검증 결과

```python
{
    "id": int,                   # Primary Key
    "contract_id": str,          # Foreign Key
    "contract_type": str,
    "completeness_check": JSON,  # 완전성 검증 결과
    "checklist_validation": JSON,# 체크리스트 검증 결과
    "content_analysis": JSON,    # 내용 분석 결과
    "overall_score": float,
    "issues": JSON,              # 이슈 리스트
    "suggestions": JSON,         # 개선 제안
    "created_at": datetime
}
```

#### 4. Report
최종 보고서

```python
{
    "id": int,                   # Primary Key
    "contract_id": str,          # Foreign Key
    "contract_type": str,
    "validation_date": datetime,
    "overall_assessment": JSON,  # 전체 평가
    "issues": JSON,              # 이슈 리스트
    "positive_points": JSON,     # 긍정적 평가
    "recommendations": JSON,     # 개선 권장사항
    "created_at": datetime
}
```

### DB 초기화

FastAPI 시작 시 자동으로 테이블 생성:

```python
@app.on_event("startup")
async def startup_event():
    init_db()  # 테이블 생성
```

### DB 세션 사용

FastAPI 의존성 주입:

```python
from backend.shared.database import get_db, ContractDocument
from sqlalchemy.orm import Session

@app.post("/upload")
async def upload_file(file: UploadFile, db: Session = Depends(get_db)):
    # DB 사용
    contract_doc = ContractDocument(
        contract_id=contract_id,
        filename=filename,
        parsed_data=result["structured_data"],
        status="parsed"
    )
    db.add(contract_doc)
    db.commit()
```

## Ingestion 워크플로우

### 1. 지식베이스 구축

```bash
# Docker Compose로 ingestion 실행
docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion

# CLI에서 전체 파이프라인 실행
ingestion> run --mode full --file all
```

### 2. 결과 확인

```bash
# 상태 확인
ingestion> status

# 또는 FastAPI 엔드포인트로 확인
curl http://localhost:8000/api/knowledge-base/status
```

### 3. Backend에서 사용

```python
from backend.shared.services import get_knowledge_base_loader

loader = get_knowledge_base_loader()

# 계약 유형별 인덱스 로드
faiss_index = loader.load_faiss_index('provide')
chunks = loader.load_chunks('provide')
whoosh_indexer = loader.load_whoosh_index('provide')
```

## 환경 변수

`.env` 파일에 다음 설정 추가:

```bash
# 데이터베이스
DATABASE_URL=sqlite:////app/data/database/contracts.db

# Redis
REDIS_URL=redis://redis:6379

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

## 트러블슈팅

### 지식베이스가 로드되지 않을 때

1. Ingestion 실행 확인:
   ```bash
   docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion
   ```

2. 파일 존재 확인:
   ```bash
   ls -la data/search_indexes/faiss/
   ls -la data/chunked_documents/
   ```

3. 상태 확인:
   ```bash
   curl http://localhost:8000/api/knowledge-base/status
   ```

### DB 초기화 실패

1. 디렉토리 권한 확인:
   ```bash
   mkdir -p data/database
   chmod 777 data/database
   ```

2. DB 파일 삭제 후 재시작:
   ```bash
   rm data/database/contracts.db
   docker-compose restart fast-api
   ```

## 다음 단계

- [ ] Classification Agent 구현
- [ ] HybridSearcher를 KnowledgeBaseLoader와 통합
- [ ] Redis Queue를 통한 Agent 간 통신 구현
