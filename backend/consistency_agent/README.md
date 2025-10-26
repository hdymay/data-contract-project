# Consistency Agent (A3 노드)

## 개요

Consistency Agent는 사용자 계약서의 내용을 표준계약서와 비교하여 정합성을 검증하는 MSA 기반 서비스입니다.

## 아키텍처

### 컴포넌트 구조

```
consistency_agent/
├── agent.py                    # Celery 작업 정의
├── models.py                   # 데이터 모델
├── hybrid_searcher.py          # FAISS + Whoosh 하이브리드 검색
└── nodes/
    ├── a3_node.py              # A3 노드 메인 로직
    └── article_matcher.py      # 대응 조항 검색
```

### 데이터 플로우

```
FastAPI (/api/validation/{contract_id}/start)
    ↓
Celery Task (consistency.validate_contract)
    ↓
ContentAnalysisNode.analyze_contract()
    ↓
각 조항에 대해:
    ArticleMatcher.find_matching_article()
        ↓
    HybridSearcher.search()
        ├─ FAISS 검색 (0.85)
        └─ Whoosh 검색 (0.15)
        ↓
    조 단위 집계 및 정규화
    ↓
ValidationResult 저장 (database)
    ↓
FastAPI (/api/validation/{contract_id})
    ↓
Streamlit UI
```

## 주요 기능

### 1. 대응 조항 검색 (ArticleMatcher)

- **멀티벡터 검색**: 사용자 조항의 각 하위항목으로 개별 검색
- **하이브리드 검색**: FAISS (의미) + Whoosh (키워드)
- **조 단위 집계**: 청크 레벨 결과를 조 단위로 취합
- **정규화**: 조별 청크 개수를 고려한 공정한 점수 계산

### 2. 하이브리드 검색 (HybridSearcher)

- **Dense 검색**: FAISS 벡터 유사도 (가중치 0.85)
- **Sparse 검색**: Whoosh BM25 키워드 매칭 (가중치 0.15)
- **결과 융합**: Min-Max 정규화 + 가중 평균

### 3. 내용 분석 (ContentAnalysisNode)

- **조항별 매칭**: 표준계약서 조항과 매칭
- **점수 계산**: 완전성, 명확성, 실무성 (현재 임시값)
- **특수 조항 처리**: 표준계약서에 없는 조항 식별

## Docker 구성

### Dockerfile.consistency

```dockerfile
FROM python:3.11-slim

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성
COPY requirements/requirements.txt .
COPY requirements/requirements-consistency.txt .
RUN pip install --no-cache-dir -r requirements-consistency.txt

ENV PYTHONPATH=/app

# 소스 코드
COPY backend/consistency_agent/ ./backend/consistency_agent/
COPY backend/shared/ ./backend/shared/
COPY ingestion/ ./ingestion/

# Celery 워커 실행
CMD ["python", "-m", "celery", "-A", "backend.shared.core.celery_app:celery_app", "worker", "-Q", "consistency_validation", "-l", "info"]
```

### docker-compose.yml

```yaml
consistency-validation-worker:
  build:
    context: ..
    dockerfile: docker/Dockerfile.consistency
  env_file:
    - ../.env
  environment:
    - REDIS_URL=redis://redis:6379
    - DATABASE_URL=sqlite:///./data/database/contracts.db
  volumes:
    - ../data:/app/data
    - ../data/search_indexes:/app/search_indexes
    - ../backend:/app/backend
  depends_on:
    - redis
```

## 환경 변수

```bash
# Azure OpenAI (필수)
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Redis
REDIS_URL=redis://redis:6379

# Database
DATABASE_URL=sqlite:///./data/database/contracts.db
```

## 실행 방법

### 1. Docker Compose로 전체 시스템 실행

```bash
# 전체 시스템 시작
docker-compose -f docker/docker-compose.yml up -d

# Consistency Agent 로그 확인
docker-compose -f docker/docker-compose.yml logs -f consistency-validation-worker
```

### 2. 로컬 개발 환경

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 종속성 설치
pip install -r requirements/requirements-consistency.txt

# Celery 워커 실행
celery -A backend.shared.core.celery_app worker -Q consistency_validation -l info
```

## API 사용법

### 검증 시작

```bash
curl -X POST http://localhost:8000/api/validation/{contract_id}/start
```

**응답:**

```json
{
  "message": "검증이 시작되었습니다",
  "contract_id": "contract_123",
  "task_id": "task_456",
  "status": "processing"
}
```

### 검증 결과 조회

```bash
curl http://localhost:8000/api/validation/{contract_id}
```

**응답:**

```json
{
  "contract_id": "contract_123",
  "status": "completed",
  "validation_result": {
    "overall_score": 0.85,
    "content_analysis": {
      "total_articles": 15,
      "analyzed_articles": 14,
      "special_articles": 1,
      "overall_scores": {
        "completeness": 0.85,
        "clarity": 0.90,
        "practicality": 0.80
      },
      "article_analysis": [...]
    }
  }
}
```

## 테스트

### 통합 테스트 실행

```bash
# pytest 설치
pip install pytest

# 테스트 실행
pytest tests/integration/test_consistency_agent.py -v
```

### 테스트 커버리지

- KnowledgeBaseLoader: 인덱스 로드
- HybridSearcher: 하이브리드 검색
- ArticleMatcher: 대응 조항 검색
- ContentAnalysisNode: 전체 분석
- Database Models: 데이터 저장/조회

## 성능 최적화

### 1. 캐싱

- **FAISS 인덱스**: 계약 유형별 캐싱
- **청크 메타데이터**: 메모리 캐싱
- **Searcher 인스턴스**: 재사용

### 2. 비동기 처리

- Celery 작업 큐로 비동기 처리
- Redis 메시지 브로커
- 프론트엔드 폴링으로 결과 조회

### 3. 확장성

- Celery 워커 수평 확장 가능
- Docker Compose로 워커 수 조정
- Redis 클러스터링 지원

## 제한사항

### 현재 구현

- ✅ 대응 조항 검색
- ✅ 하이브리드 검색
- ✅ 조 단위 집계
- ⚠️ 임시 점수 (ContentComparator 미구현)
- ❌ 개선 제안 (SuggestionGenerator 미구현)
- ❌ 특수 조항 분석 (SpecialArticleHandler 미구현)

### 다음 단계

1. **ContentComparator 구현**: LLM 기반 내용 비교
2. **SuggestionGenerator 구현**: 개선 제안 생성
3. **SpecialArticleHandler 구현**: 특수 조항 평가
4. **A1, A2 노드 구현**: 완전성, 체크리스트 검증

## 트러블슈팅

### 1. FAISS 인덱스 로드 실패

```
ERROR: FAISS 인덱스 파일을 찾을 수 없습니다
```

**해결책:**

- Ingestion 파이프라인 실행: `docker-compose --profile ingestion run --rm ingestion`
- 인덱스 파일 경로 확인: `/app/search_indexes/faiss/{contract_type}_std_contract.faiss`

### 2. Azure OpenAI 연결 실패

```
ERROR: Azure OpenAI 환경 변수가 설정되지 않음
```

**해결책:**

- `.env` 파일에 환경 변수 설정
- Docker Compose 재시작

### 3. Celery 작업 실행 안됨

```
WARNING: No consumers for queue 'consistency_validation'
```

**해결책:**

- Celery 워커 큐 이름 확인: `-Q consistency_validation`
- Redis 연결 확인: `redis-cli ping`

### 4. 데이터베이스 오류

```
ERROR: no such table: validation_results
```

**해결책:**

- 데이터베이스 초기화: `python -c "from backend.shared.database import init_db; init_db()"`

## 모니터링

### Celery 작업 모니터링

```bash
# Flower 설치 및 실행
pip install flower
celery -A backend.shared.core.celery_app flower

# 브라우저에서 http://localhost:5555 접속
```

### 로그 확인

```bash
# Docker 로그
docker-compose logs -f consistency-validation-worker

# 로컬 로그
tail -f logs/consistency_agent.log
```

## 기여

### 코드 스타일

- PEP 8 준수
- Type hints 사용
- Docstring 작성 (Google 스타일)

### 커밋 메시지

```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
refactor: 코드 리팩토링
test: 테스트 추가/수정
```

## 라이선스

MIT License
