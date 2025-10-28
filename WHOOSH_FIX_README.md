# Whoosh 검색 문제 해결 가이드

## 🔍 문제 요약

**증상**: Consistency Agent에서 모든 유사도가 0.85 이하로 제한됨

**근본 원인** (최종 분석):
1. **Ingestion과 Consistency 모두** `mecab-python3` 패키지가 누락됨
2. 기존 폴백 토크나이저 `[\w]+`가 **한글을 전혀 토큰화하지 못함**
3. Whoosh 인덱스에 한글 토큰이 거의 없어서 검색 항상 실패
4. 검색 결과 0개 → Sparse 점수 항상 0 → 하이브리드 점수 = 0.85 × Dense만 반영

**해결**:
1. Mecab을 양쪽 컨테이너에 모두 설치
2. **Whoosh 인덱스 재구축** (필수!)

---

## ✅ 구현된 해결책

### 1. Requirements 수정
- **파일**: `requirements/requirements.txt`, `requirements/requirements-ingestion.txt`
- **변경**: `mecab-python3==1.0.6` 추가

### 2. Dockerfile 수정
- **파일**: `docker/Dockerfile.consistency`, `docker/Dockerfile.ingestion`
- **변경**:
  - Mecab 바이너리 설치
  - mecab-ko-dic (한국어 사전) 설치
  - `build-essential`, `make` 추가

### 3. 코드 개선
- **Adaptive Weighting**: Whoosh 실패 시 자동으로 Dense 가중치 1.0 적용
- **상세 진단 로깅**: 검색 실패 원인 파악을 위한 로깅 추가
- **쿼리 이스케이프**: Whoosh 특수문자 처리 개선

### 4. Mecab 필수화
- **파일**: `ingestion/indexers/whoosh_indexer.py`
- **변경**: Mecab 없으면 에러 발생하도록 변경 (일관성 보장)

---

## 🚀 적용 방법

### Step 1: Docker 이미지 재빌드

```bash
# Ingestion과 Consistency Agent 모두 재빌드
docker-compose build ingestion consistency_agent

# 또는 전체 재빌드
docker-compose build
```

### Step 2: Whoosh 인덱스 재구축 (필수!)

**중요**: 기존 인덱스는 한글 토큰화가 안 되어 있으므로 재구축 필수!

상세 가이드: [REBUILD_WHOOSH_INDEX.md](REBUILD_WHOOSH_INDEX.md)

```bash
# 빠른 재구축 (청킹 데이터 있는 경우)
docker-compose run --rm ingestion bash
python -m ingestion.ingest

# CLI에서:
ingestion> run --mode embedding --file all
```

### Step 3: 컨테이너 재시작

```bash
# 컨테이너 중지 및 재시작
docker-compose down
docker-compose up -d
```

### Step 4: Mecab 설치 확인

```bash
# Consistency Agent 컨테이너 접속
docker exec -it <consistency_container_name> bash

# Mecab 설치 확인
mecab --version

# Python에서 Mecab 동작 확인
python -c "from konlpy.tag import Mecab; m = Mecab(); print(m.morphs('형태소 분석 테스트'))"
```

**예상 출력**:
```python
['형태소', '분석', '테스트']
```

### Step 5: Consistency Agent 로그 확인

Consistency Agent를 실행하고 로그를 확인합니다:

```bash
docker-compose logs -f consistency_agent
```

**성공 시 로그**:
```
[INFO] ✓ KoNLPy Mecab 초기화 완료
[INFO] Whoosh 인덱스 로드 완료: provide (82 문서)
[DEBUG] Sparse 검색 완료: 10개, 점수 범위 [0.5234 ~ 2.1456]
[DEBUG] Sparse-Dense 중복: 8/15 (53.3%)
```

**실패 시 로그 (Mecab 없음)**:
```
[WARNING] Mecab을 사용할 수 없습니다. ...
[WARNING] Sparse 검색 결과 없음 - Adaptive Weighting 적용 (Dense: 1.0)
```

---

## 📊 예상 효과

### Before (문제 상황)
- Whoosh 검색: 항상 0개 결과
- 최대 유사도: **0.85** (고정)
- Sparse 기여도: **0%**

### After (해결 후)
- Whoosh 검색: 정상 작동
- 최대 유사도: **0.85 ~ 1.0** (하이브리드)
- Sparse 기여도: **15%** (설정된 가중치대로)

**실제 효과**:
- 거의 일치하는 조항: 0.85 → **0.90 ~ 1.0**
- 부분 일치 조항: 0.70 → **0.75 ~ 0.85**
- 유사도 분포가 더 정확하고 넓은 범위로 표현됨

---

## 🔧 트러블슈팅

### 문제 1: Mecab 설치 실패

**증상**:
```
E: Unable to locate package mecab
```

**해결**:
```dockerfile
# Dockerfile.consistency에서 apt-get update 확인
RUN apt-get update && apt-get install -y mecab ...
```

### 문제 2: mecab-ko-dic 다운로드 실패

**증상**:
```
curl: (22) The requested URL returned error: 404
```

**해결**: 대체 URL 사용
```dockerfile
RUN curl -LO https://github.com/bibreen/mecab-ko-dic/releases/download/latest/mecab-ko-dic-latest.tar.gz
```

### 문제 3: 여전히 Whoosh 결과 0개

**원인**: 기존 인덱스가 이전 토크나이저로 구축됨

**해결**: Whoosh 인덱스 재구축 필요

```bash
# Ingestion 컨테이너에서 인덱스 재구축
docker exec -it <ingestion_container_name> bash
cd /app
python -m ingestion.ingest

# CLI에서:
ingestion> run --mode embedding --file all
```

---

## 📝 주요 변경 파일

1. **docker/Dockerfile.consistency** - Mecab 설치 추가
2. **ingestion/indexers/whoosh_indexer.py** - Mecab 필수화
3. **backend/consistency_agent/hybrid_searcher.py** - Adaptive Weighting 추가
4. **backend/shared/services/knowledge_base_loader.py** - 로드 시 진단 로깅

---

## ✨ 추가 개선사항

### Adaptive Weighting
Whoosh 검색이 실패해도 FAISS의 완전한 유사도를 사용할 수 있도록 자동 가중치 조정:

```python
if not sparse_results and dense_results:
    effective_dense_weight = 1.0  # 0.85 → 1.0
    effective_sparse_weight = 0.0
```

### 상세 진단 로깅
문제 발생 시 빠른 진단을 위한 로그:
- Whoosh 인덱스 문서 수
- 쿼리 이스케이프 전후
- 검색 결과 개수 및 점수 범위
- Sparse-Dense 중복률

---

## 📞 문제 지속 시

로그에서 다음을 확인하여 공유해주세요:

1. Mecab 초기화 성공 여부
2. Whoosh 인덱스 문서 개수
3. Sparse 검색 결과 개수
4. 예외 스택 트레이스 (있는 경우)

```bash
# 전체 로그 추출
docker-compose logs consistency_agent > consistency_logs.txt
```
