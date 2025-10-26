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
# FastAPI 백엔드 (포트 8000)
python -m uvicorn backend.fastapi.main:app --host 0.0.0.0 --port 8000 --reload

# Streamlit 프론트엔드
streamlit run frontend/app.py
```

### 문서 처리 파이프라인
```bash
# 인제스션 CLI 실행
python -m ingestion.ingest

# 전체 파이프라인 실행 (파싱→청킹→임베딩)
run --mode full --file all

# 단계별 실행
run --mode parsing --file document.pdf
run --mode chunking --file document_structured.json
run --mode embedding --file document_chunks.json
```

## 환경 변수
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API 키
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI 엔드포인트
- `AZURE_EMBEDDING_DEPLOYMENT`: 임베딩 모델 배포명
- `AZURE_GPT_DEPLOYMENT`: GPT 모델 배포명
- `REDIS_URL`: Redis 연결 URL
- `DATABASE_URL`: SQLite 데이터베이스 경로