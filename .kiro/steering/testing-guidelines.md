# 테스트 가이드라인

## 테스트 전략

### 단위 테스트 (Unit Tests)
- **위치**: `tests/unit/`
- **범위**: 개별 함수 및 클래스 메서드
- **도구**: pytest, unittest
- **커버리지**: 핵심 비즈니스 로직 80% 이상

#### 주요 테스트 대상
- **파서 모듈**: DOCX 파싱 로직, 다양한 형식 처리
- **청커 모듈**: 텍스트 청킹 알고리즘, 메타데이터 생성
- **검색 모듈**: 하이브리드 검색, 점수 계산
- **에이전트 로직**: 분류 알고리즘, 검증 로직

### 통합 테스트 (Integration Tests)
- **위치**: `tests/integration/`
- **범위**: 컴포넌트 간 상호작용
- **환경**: Docker Compose 기반 테스트 환경

#### 주요 테스트 시나리오
- **Ingestion Pipeline**: 파싱 → 청킹 → 임베딩 → 인덱싱 전체 플로우
- **Agent Communication**: Redis 큐를 통한 메시지 전달
- **API Endpoints**: FastAPI 엔드포인트 응답 및 상태 코드
- **Database Operations**: SQLAlchemy 모델 CRUD 작업

### 시스템 테스트 (E2E Tests)
- **위치**: `tests/e2e/`
- **범위**: 전체 시스템 end-to-end 플로우
- **환경**: 실제 운영 환경과 유사한 설정

#### 주요 테스트 케이스
- **사용자 플로우**: 업로드 → 분류 → 결과 확인 → 수정
- **다양한 계약서**: 5종 표준계약서 변형 샘플
- **에러 시나리오**: 잘못된 파일, 네트워크 오류, API 실패
- **성능 테스트**: 응답 시간, 메모리 사용량, 동시 사용자

## 테스트 데이터

### 표준 테스트 데이터
```
tests/data/
├── standard_contracts/     # 5종 표준계약서 원본
├── user_samples/          # 사용자 계약서 샘플
│   ├── valid/            # 정상적인 구조의 계약서
│   ├── variations/       # 구조 변형 계약서
│   └── edge_cases/       # 극단적 케이스
├── expected_results/      # 예상 결과 (분류, 검증)
└── mock_data/            # 테스트용 모조 데이터
```

### 테스트 케이스 분류

#### 1. 정상 케이스 (Happy Path)
- 표준 형식의 DOCX 파일
- 명확한 "제n조" 구조
- 5종 유형에 명확히 해당하는 내용

#### 2. 변형 케이스 (Variations)
- 조 번호 형식 차이 ("제1조", "제 1 조", "1조")
- 제목 형식 차이 ("제1조(목적)", "제1조 목적", "1. 목적")
- 내용 순서 변경 (표준계약서와 다른 조 순서)

#### 3. 극단 케이스 (Edge Cases)
- 매우 짧은 계약서 (5개 조 미만)
- 매우 긴 계약서 (50개 조 이상)
- 특수 문자 포함 제목
- 빈 조항 또는 내용 없는 조

#### 4. 에러 케이스 (Error Cases)
- 손상된 DOCX 파일
- 비DOCX 파일 (PDF, TXT 등)
- 계약서가 아닌 문서
- 한국어가 아닌 언어

## 테스트 실행

### 로컬 환경
```bash
# 전체 테스트 실행
pytest

# 특정 테스트 모듈
pytest tests/unit/test_parser.py

# 커버리지 포함
pytest --cov=backend --cov-report=html

# 통합 테스트 (Docker 필요)
docker-compose -f docker/docker-compose.test.yml up --build
pytest tests/integration/
```

### CI/CD 환경
```bash
# GitHub Actions 또는 유사 CI 도구에서
# 1. 의존성 설치
pip install -r requirements/requirements.txt
pip install -r requirements/requirements-test.txt

# 2. 테스트 환경 설정
docker-compose -f docker/docker-compose.test.yml up -d

# 3. 테스트 실행
pytest tests/ --junitxml=test-results.xml --cov=backend

# 4. 정리
docker-compose -f docker/docker-compose.test.yml down
```

## 성능 테스트

### 벤치마크 기준
- **파싱 시간**: DOCX 파일 (10페이지) < 5초
- **분류 시간**: 사용자 계약서 분류 < 30초
- **검색 응답**: 하이브리드 검색 < 1초
- **메모리 사용량**: 인덱스 로딩 < 2GB

### 부하 테스트
```bash
# Locust를 사용한 부하 테스트
pip install locust
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

### 모니터링 지표
- API 응답 시간 (P50, P95, P99)
- Celery 작업 처리 시간
- Redis 큐 대기 시간
- 메모리 및 CPU 사용률

## 테스트 자동화

### Pre-commit Hooks
```bash
# pre-commit 설치 및 설정
pip install pre-commit
pre-commit install

# .pre-commit-config.yaml 설정
# - 코드 포맷팅 (black, isort)
# - 린팅 (flake8, mypy)
# - 간단한 테스트 실행
```

### 지속적 통합 (CI)
- **트리거**: Pull Request, main 브랜치 푸시
- **단계**: 
  1. 코드 품질 검사 (린팅, 포맷팅)
  2. 단위 테스트 실행
  3. 통합 테스트 실행
  4. 커버리지 리포트 생성
  5. 성능 회귀 테스트

### 테스트 환경 관리
- **개발 환경**: 로컬 Docker Compose
- **스테이징 환경**: 운영과 동일한 구성
- **테스트 데이터**: 익명화된 실제 데이터 사용
- **환경 격리**: 각 테스트는 독립적인 DB 상태

## 품질 기준

### 코드 커버리지
- **최소 기준**: 70%
- **목표**: 80% 이상
- **핵심 모듈**: 90% 이상 (파서, 분류기, 검증기)

### 테스트 통과율
- **단위 테스트**: 100% 통과 필수
- **통합 테스트**: 95% 이상 통과
- **E2E 테스트**: 90% 이상 통과

### 성능 기준
- **응답 시간**: 기준치 대비 20% 이내 변동
- **메모리 사용량**: 기준치 대비 10% 이내 변동
- **처리량**: 동시 사용자 10명 이상 지원

## 테스트 문서화

### 테스트 케이스 문서
- **목적**: 각 테스트의 의도와 검증 내용
- **전제 조건**: 테스트 실행을 위한 환경 설정
- **예상 결과**: 성공/실패 기준
- **실행 방법**: 테스트 실행 명령어

### 버그 리포트
- **재현 단계**: 문제 발생 과정
- **환경 정보**: OS, Python 버전, 의존성
- **로그**: 에러 메시지 및 스택 트레이스
- **해결 방안**: 임시 해결책 및 근본 원인