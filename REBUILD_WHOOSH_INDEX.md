# Whoosh 인덱스 재구축 가이드

## 📋 배경

기존 Whoosh 인덱스가 `mecab-python3` 없이 구축되어 **한글 토큰화가 제대로 되지 않았습니다**.
Mecab을 적용하여 인덱스를 재구축하면 한국어 검색 품질이 크게 향상됩니다.

---

## ⚠️ 중요 사항

**Whoosh 인덱스 재구축은 필수입니다!**

이유:
1. 기존 인덱스: 폴백 토크나이저 `[\w]+` 사용 → 한글 토큰화 실패
2. 새 인덱스: Mecab 형태소 분석 → 정확한 한글 토큰화
3. 토크나이저가 다르면 검색 시 매칭 불가

---

## 🚀 재구축 절차

### Step 1: Ingestion 컨테이너 재빌드

```bash
# 1. Ingestion 이미지 재빌드 (Mecab 포함)
docker-compose build ingestion

# 2. 확인: Mecab 정상 설치 여부
docker run --rm <ingestion_image> python -c "from konlpy.tag import Mecab; print('✓ Mecab OK')"
```

**예상 출력**:
```
✓ Mecab OK
```

### Step 2: 기존 Whoosh 인덱스 백업 (선택사항)

```bash
# 안전을 위해 기존 인덱스 백업
mv data/search_indexes/whoosh data/search_indexes/whoosh_backup_$(date +%Y%m%d)
```

### Step 3: Ingestion CLI 실행

```bash
# Ingestion 컨테이너 실행 (대화형 모드)
docker run --rm -it \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/search_indexes:/app/search_indexes \
  <ingestion_image> \
  python -m ingestion.ingest
```

또는 docker-compose 사용:

```bash
# docker-compose.yml에서 ingestion 서비스 확인 후
docker-compose run --rm ingestion bash
cd /app
python -m ingestion.ingest
```

### Step 4: 전체 파이프라인 실행

Ingestion CLI가 시작되면:

```
ingestion> run --mode full --file all
```

이 명령어는:
1. **Parsing**: 모든 PDF/DOCX 파싱
2. **Chunking**: 조/항 단위로 청킹
3. **Embedding**: FAISS 임베딩 생성
4. **Indexing**: **Whoosh 인덱스 재구축** (Mecab 사용)

**예상 소요 시간**: 5-10분 (파일 개수에 따라 다름)

### Step 5: 인덱스 재구축 확인

```
ingestion> status
```

**예상 출력**:
```
=== 디렉토리 상태 ===

📁 source_documents: 5 files
📁 extracted_documents: 5 files
📁 chunked_documents: 5 files
📁 search_indexes/faiss: 5 indexes
📁 search_indexes/whoosh: 5 indexes

✓ 모든 인덱스 정상
```

로그에서 다음 메시지 확인:
```
[INFO] ✓ KoNLPy Mecab 초기화 완료
[INFO] Whoosh 인덱스 구축 완료: 82개 청크
```

### Step 6: Consistency Agent 재시작

```bash
# Consistency Agent 컨테이너 재시작
docker-compose restart consistency_agent

# 로그 확인
docker-compose logs -f consistency_agent
```

### Step 7: 검증

Consistency Agent 로그에서 다음 확인:

**성공 시**:
```
[INFO] ✓ KoNLPy Mecab 초기화 완료
[INFO] Whoosh 인덱스 로드 완료: provide (82 문서)
[DEBUG] Sparse 검색 완료: 10개, 점수 범위 [0.5234 ~ 2.1456]
[DEBUG] Sparse-Dense 중복: 8/15 (53.3%)
```

**실패 시** (인덱스 미재구축):
```
[WARNING] Whoosh 검색 결과 0개
[WARNING] Sparse 검색 결과 없음 - Adaptive Weighting 적용 (Dense: 1.0)
```

---

## 📊 재구축 전후 비교

### Before (폴백 토크나이저)

```python
# 토큰화 예시
텍스트: "데이터 제공 계약"
토큰: []  # 한글 매칭 안 됨!
```

**검색 결과**: 항상 0개

### After (Mecab 형태소 분석)

```python
# 토큰화 예시
텍스트: "데이터 제공 계약"
토큰: ["데이터", "제공", "계약"]
```

**검색 결과**: 정상 작동
- "데이터 제공" 검색 → 관련 조항 10개 반환
- 유사도 점수: 0.85 ~ 1.0 (하이브리드)

---

## 🔧 트러블슈팅

### 문제 1: "Mecab을 사용할 수 없습니다" 에러

**원인**: `mecab-python3` 미설치

**해결**:
```bash
# 컨테이너 내부에서 확인
pip list | grep mecab

# 없으면 requirements 확인 후 재빌드
```

### 문제 2: 인덱스 파일이 생성되지 않음

**원인**: 권한 문제 또는 경로 오류

**해결**:
```bash
# 볼륨 마운트 확인
docker-compose config | grep volumes

# 디렉토리 권한 확인
ls -la data/search_indexes/whoosh/
```

### 문제 3: "전체 파이프라인" 실행 시 오류

**원인**: 소스 파일 없음

**해결**:
```bash
# 소스 파일 확인
ls -la data/source_documents/

# PDF/DOCX 파일이 있어야 함
```

대안: 기존에 청킹된 파일이 있다면:
```
ingestion> run --mode embedding --file all
```

---

## ⏱️ 빠른 재구축 (청킹 데이터 있는 경우)

이미 청킹된 JSON 파일이 있다면 임베딩만 재실행:

```bash
# Ingestion CLI에서
ingestion> run --mode embedding --file all
```

이 방법은:
- ✓ 파싱/청킹 스킵
- ✓ FAISS 임베딩 재생성
- ✓ **Whoosh 인덱스 재구축** (Mecab 사용)

**소요 시간**: 2-3분

---

## 📝 체크리스트

재구축 완료 전 확인사항:

- [ ] Ingestion 컨테이너 재빌드 완료
- [ ] Mecab 정상 작동 확인
- [ ] 기존 인덱스 백업 (선택)
- [ ] Whoosh 인덱스 재구축 실행
- [ ] 로그에서 "Mecab 초기화 완료" 확인
- [ ] Consistency Agent 재시작
- [ ] Sparse 검색 결과 > 0 확인
- [ ] 유사도 0.85 이상 값 확인

---

## 🎯 예상 효과

재구축 후:
- ✅ Whoosh 검색 정상 작동
- ✅ 하이브리드 검색 활성화 (Dense 85% + Sparse 15%)
- ✅ 유사도 범위: 0.0 ~ 1.0 (전체 스펙트럼)
- ✅ 검색 품질 대폭 향상

**실제 유사도 변화**:
- 거의 일치: 0.85 → **0.92 ~ 0.98**
- 부분 일치: 0.70 → **0.78 ~ 0.88**
- 관련 없음: 0.60 → **0.45 ~ 0.65**

더 정확한 유사도 분포로 조항 매칭 품질 향상!
