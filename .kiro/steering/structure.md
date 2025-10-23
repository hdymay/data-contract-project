# 프로젝트 구조 및 조직

## 디렉토리 구조

### 루트 레벨
- `.env`: 환경 변수 설정 파일
- `.gitignore`: Git 무시 파일 목록
- `.kiro/`: Kiro AI 설정 및 스티어링 규칙
- `.venv/`: Python 가상환경

### 백엔드 (`backend/`)
```
backend/
├── fastapi/           # FastAPI 웹 서버
│   ├── main.py       # 메인 애플리케이션 엔트리포인트
│   └── pdf_parser.py # PDF 파싱 유틸리티
├── classification_agent/  # 문서 분류 에이전트
│   ├── agent.py      # 분류 로직
│   └── nodes/        # 분류 노드 구현
├── consistency_agent/     # 정합성 검증 에이전트
│   ├── agent.py      # 검증 로직
│   └── nodes/        # 검증 노드 구현
├── report_agent/          # 보고서 생성 에이전트
│   ├── agent.py      # 보고서 생성 로직
│   └── nodes/        # 보고서 노드 구현
└── shared/               # 공통 모듈
    ├── core/            # 핵심 비즈니스 로직
    └── services/        # 공통 서비스
```

### 프론트엔드 (`frontend/`)
```
frontend/
├── app.py            # Streamlit 메인 애플리케이션
└── .streamlit/       # Streamlit 설정
```

### 문서 처리 (`ingestion/`)
```
ingestion/
├── ingest.py         # CLI 메인 모듈
├── parsers/          # 문서 파서 (PDF, DOCX)
├── processors/       # 청킹 및 임베딩 처리기
├── indexers/         # 검색 인덱스 생성기
└── test_chunker.py   # 청킹 테스트
```

### 데이터 (`data/`)
```
data/
├── source_documents/     # 원본 문서 (PDF, DOCX)
├── extracted_documents/  # 파싱된 구조화 데이터 (JSON)
├── chunked_documents/    # 청킹된 문서 (JSONL)
├── search_indexes/       # FAISS/Whoosh 인덱스
└── database/            # SQLite 데이터베이스
```

### 인프라 (`docker/`)
```
docker/
├── docker-compose.yml    # 멀티 컨테이너 오케스트레이션
├── Dockerfile.backend    # FastAPI 컨테이너
├── Dockerfile.classification  # 분류 에이전트 컨테이너
├── Dockerfile.consistency    # 정합성 에이전트 컨테이너
├── Dockerfile.report         # 보고서 에이전트 컨테이너
└── Dockerfile.ingestion      # 문서 처리 컨테이너
```

### 의존성 (`requirements/`)
```
requirements/
├── requirements.txt              # 공통 의존성
├── requirements-backend.txt      # FastAPI 의존성
├── requirements-frontend.txt     # Streamlit 의존성
├── requirements-classification.txt  # 분류 에이전트 의존성
├── requirements-consistency.txt     # 정합성 에이전트 의존성
├── requirements-report.txt          # 보고서 에이전트 의존성
└── requirements-ingestion.txt       # 문서 처리 의존성
```

### 테스트 (`tests/`)
```
tests/
├── unit/         # 단위 테스트
├── integration/  # 통합 테스트
└── e2e/         # 엔드투엔드 테스트
```

## 아키텍처 패턴

### 마이크로서비스 아키텍처
- 각 에이전트는 독립적인 서비스로 구성
- Redis를 통한 메시지 큐 기반 통신
- Docker 컨테이너로 격리된 실행 환경

### 데이터 플로우
1. **업로드**: Streamlit → FastAPI → 파일 저장
2. **처리**: 문서 파싱 → 청킹 → 임베딩 → 인덱싱
3. **분석**: 분류 에이전트 → 정합성 에이전트 → 보고서 에이전트
4. **결과**: 분석 보고서 생성 및 반환

### 명명 규칙
- **파일명**: snake_case (예: `pdf_parser.py`)
- **클래스명**: PascalCase (예: `ArticleChunker`)
- **함수명**: snake_case (예: `chunk_file()`)
- **상수명**: UPPER_SNAKE_CASE (예: `DATABASE_URL`)
- **디렉토리명**: snake_case 또는 kebab-case

### 코드 조직 원칙
- 각 에이전트는 독립적인 모듈로 구성
- 공통 기능은 `shared/` 디렉토리에 배치
- 설정 파일과 비즈니스 로직 분리
- 테스트 코드는 해당 모듈과 동일한 구조로 조직