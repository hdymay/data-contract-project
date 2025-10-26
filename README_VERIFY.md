# 계약서 검증 시스템 - 빠른 시작 가이드

## 🚀 한 줄 명령어로 계약서 검증하기

ingestion CLI를 통해 명령어 하나로 모든 검증 로직을 자동 실행할 수 있습니다!

### 1. Ingestion CLI 실행

```bash
python ingestion/ingest.py
```

### 2. 계약서 검증

```bash
ingestion> verify -u data/user_contract_sample.txt --format both
```

이 명령어 하나로 다음 모든 작업이 자동으로 실행됩니다:

✅ 표준 계약서 로드  
✅ 사용자 계약서 파싱  
✅ 하이브리드 검색 (BM25 + FAISS)  
✅ LLM 기반 의미적 매칭  
✅ 누락 조문 식별  
✅ 텍스트 보고서 생성  
✅ PDF 보고서 생성  

## 📊 출력 예시

```
============================================================
 계약서 검증 시작
============================================================

=== 1단계: 검증 엔진 초기화 ===
   [OK] 검증 엔진 초기화 완료

=== 2단계: 계약서 검증 수행 ===
   [OK] 검증 완료
        - 표준 조문 수: 45
        - 매칭된 조문: 10
        - 누락된 조문: 35
        - 표준 준수율: 22.2%
        - 검증 완료율: 100.0%

=== 3단계: 보고서 생성 ===
   [OK] 텍스트 보고서: data/reports/verification_report_20251022_091234.txt
   [OK] PDF 보고서: data/reports/verification_report_20251022_091234.pdf

============================================================
 검증 완료
============================================================
```

## 🎯 주요 기능

### 1. 자동화된 검증 파이프라인
- 표준 계약서 자동 로드
- FAISS 인덱스 자동 로드
- 검증 결과 자동 저장

### 2. 다양한 보고서 형식
```bash
# 텍스트만
verify -u data/user_contract.txt

# PDF만
verify -u data/user_contract.txt --format pdf

# 둘 다
verify -u data/user_contract.txt --format both
```

### 3. 상세한 검증 결과
- 표준 준수율: 표준 계약서 대비 포함된 조문 비율
- 검증 완료율: 사용자 계약서의 검증 완료 비율
- 매칭된 조문 목록 (LLM 판단 근거 포함)
- 누락된 조문 목록

## 📁 파일 구조

```
project/
├── ingestion/
│   └── ingest.py              # CLI 진입점 (verify 명령어 포함)
├── backend/
│   └── clause_verification/
│       ├── verification_engine.py    # 검증 엔진
│       ├── report_generator.py       # 보고서 생성
│       ├── hybrid_search.py          # 하이브리드 검색
│       ├── llm_verification.py       # LLM 검증
│       └── ...
├── data/
│   ├── user_contract_sample.txt      # 사용자 계약서 샘플
│   ├── chunked_documents/
│   │   └── parsed_43_73_table_5_chunks.jsonl  # 표준 계약서
│   └── reports/                      # 생성된 보고서
└── search_indexes/
    └── faiss/                        # FAISS 인덱스
```

## 🔧 환경 설정

`.env` 파일에 다음 환경 변수를 설정하세요:

```bash
AZURE_OPENAI_API_KEY=your_api_key
AZURE_ENDPOINT=your_endpoint
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_LLM_DEPLOYMENT=gpt-4o
```

## 🐳 도커 환경에서 실행

```bash
# 컨테이너 접속
docker exec -it <container_name> bash

# CLI 실행
python ingestion/ingest.py

# 검증 실행
ingestion> verify -u data/user_contract_sample.txt --format both
```

## 📖 상세 가이드

더 자세한 내용은 [INGESTION_VERIFY_GUIDE.md](docs/INGESTION_VERIFY_GUIDE.md)를 참고하세요.

## 🎉 완료!

이제 ingestion CLI 하나로 문서 파싱부터 계약서 검증까지 모든 작업을 수행할 수 있습니다!

```bash
# 전체 파이프라인
ingestion> run --mode full --file all          # 문서 처리
ingestion> search -i index_name -q "질의"      # 검색 테스트
ingestion> verify -u user_contract.txt         # 계약서 검증
```
