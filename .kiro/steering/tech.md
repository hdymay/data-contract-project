# 기술 스택 및 빌드 시스템

## 핵심 기술 스택

### Backend
- **FastAPI**: REST API 서버 (Python 3.x)
- **SQLAlchemy**: ORM 및 데이터베이스 관리
- **Alembic**: 데이터베이스 마이그레이션
- **Redis**: 메시지 큐 및 캐싱
- **Celery**: 비동기 작업 처리
- **Uvicorn**: ASGI 서버

### Frontend
- **Streamlit**: 웹 인터페이스 (Python 기반)

### Document Processing
- **PyMuPDF**: PDF 파싱 및 텍스트 추출
- **FAISS**: 벡터 검색 인덱싱
- **Azure OpenAI**: 임베딩 및 AI 분석

### Infrastructure
- **Docker**: 컨테이너화
- **Docker Compose**: 멀티 컨테이너 오케스트레이션

## 주요 명령어

### 개발 환경 설정
```bash
# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements/requirements.txt
pip install -r requirements/requirements-backend.txt
pip install -r requirements/requirements-frontend.txt
```

### Docker 실행
```bash
# 전체 시스템 실행
docker-compose -f docker/docker-compose.yml up -d

# 특정 서비스만 실행
docker-compose -f docker/docker-compose.yml up fast-api redis

# 문서 수집(ingestion) 실행
docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion
```

### 개발 서버 실행
```bash
# 전체 시스템 실행 (권장)
docker-compose -f docker/docker-compose.yml up -d

# 개별 서비스 실행
# FastAPI 백엔드 (포트 8000)
python -m uvicorn backend.fastapi.main:app --host 0.0.0.0 --port 8000 --reload

# Streamlit 프론트엔드 (포트 8501)
streamlit run frontend/app.py

# Celery Worker (분류 작업 처리)
celery -A backend.shared.core.celery_app worker --loglevel=info --queues=classification

# Redis (메시지 큐)
redis-server
```

### 문서 처리 파이프라인
```bash
# 지식베이스 구축 (표준계약서 5종)
docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion

# 또는 직접 실행
python -m ingestion.ingest

# 전체 파이프라인 실행 (파싱→청킹→임베딩→인덱싱)
run --mode full --file all

# 단계별 실행
run --mode parsing --file provide_std_contract.docx
run --mode chunking --file provide_std_contract_structured.json
run --mode embedding --file provide_std_contract_chunks.json
run --mode indexing --file provide_std_contract_chunks.json
```

## 환경 변수
```bash
# Azure OpenAI 설정 (필수)
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_GPT_DEPLOYMENT=gpt-4

# Redis 설정
REDIS_URL=redis://localhost:6379/0

# 데이터베이스 설정
DATABASE_URL=sqlite:///data/database/contracts.db

# Celery 설정
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**중요**: Azure OpenAI 환경 변수가 설정되지 않으면 Classification Agent가 동작하지 않습니다.