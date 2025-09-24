# 데이터 표준계약 검증 에이전트

AI 기반 데이터 계약서 분석 및 검증 시스템

## 프로젝트 개요

이 프로젝트는 한국데이터산업진흥원(K-DATA)이 제정한 데이터 표준계약서를 기반으로 실물 데이터 계약서의 내용을 검증하는 멀티 에이전트 아키텍처입니다.

## 기술 스택

- **Frontend**: Streamlit
- **Backend**: FastAPI
- **Queue**: Redis
- **DB**: SQLite
- **Vector Store**: FAISS
- **Text Retrieval**: Woosh
- **LLM Provider**: OpenAI GPT
- **Deployment**: Docker Compose

## 프로젝트 구조

```
data-contract-project/
├── frontend/                    # Streamlit 프론트엔드
├── backend/                     # FastAPI 백엔드
├── docker/                      # Docker 설정
├── data/                        # 데이터 저장소
├── scripts/                     # 유틸리티 스크립트
├── config/                      # 설정 파일
├── tests/                       # 테스트
└── requirements/                # 의존성 관리
```

## 설치 및 실행

### 1. 개발 환경 설정

```bash
# 의존성 설치
pip install -r requirements/requirements-dev.txt

# 데이터 디렉토리 준비
python scripts/data_preparation.py

# 지식베이스 구축
python scripts/setup_knowledge_base.py
```

### 2. Docker로 백엔드 실행

```bash

# 백엔드 서비스 실행
docker-compose up
```

### 3. Streamlit 프론트엔드 실행

```bash
cd frontend
streamlit run app.py --server.port 8501
```