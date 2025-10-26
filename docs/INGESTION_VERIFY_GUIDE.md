# Ingestion CLI - 계약서 검증 기능 가이드

## 개요

ingestion CLI에 계약서 검증 기능이 통합되었습니다. 이제 명령어 하나로 사용자 계약서를 표준 계약서와 비교하여 누락된 조문을 찾고 보고서를 생성할 수 있습니다.

## 사용 방법

### 1. Ingestion CLI 실행

```bash
# 도커 환경에서
python ingestion/ingest.py
```

### 2. 계약서 검증 명령어

```bash
# 기본 사용 (텍스트 보고서만)
verify --user data/user_contract_sample.txt

# 또는 짧은 옵션
verify -u data/user_contract_sample.txt

# PDF 보고서만 생성
verify -u data/user_contract_sample.txt --format pdf

# 텍스트 + PDF 보고서 모두 생성
verify -u data/user_contract_sample.txt --format both
```

### 3. 명령어 옵션

| 옵션 | 짧은 형식 | 설명 | 필수 |
|------|-----------|------|------|
| `--user` | `-u` | 사용자 계약서 파일 경로 (.txt) | ✓ |
| `--format` | `-f` | 보고서 형식 (text/pdf/both) | ✗ (기본값: text) |

## 실행 프로세스

검증 명령어를 실행하면 다음 단계가 자동으로 수행됩니다:

### 1단계: 검증 엔진 초기화
- 표준 계약서 로드 (`data/chunked_documents/parsed_43_73_table_5_chunks.jsonl`)
- FAISS 인덱스 로드
- Azure OpenAI 서비스 초기화

### 2단계: 계약서 검증 수행
- 사용자 계약서 파싱
- 하이브리드 검색 (BM25 + FAISS)
- LLM 기반 의미적 매칭 검증
- 누락 조문 식별

### 3단계: 보고서 생성
- 검증 결과 요약
- 매칭된 조문 목록
- 누락된 조문 목록
- 완성도 지표 (표준 준수율, 검증 완료율)

## 출력 예시

```
============================================================
 계약서 검증 시작
  사용자 계약서: data/user_contract_sample.txt
  보고서 형식: both
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
   [OK] 텍스트 보고서 생성: data/reports/verification_report_20251022_091234.txt
   [OK] PDF 보고서 생성: data/reports/verification_report_20251022_091234.pdf

============================================================
 검증 완료
============================================================
```

## 보고서 위치

생성된 보고서는 `data/reports/` 디렉토리에 저장됩니다:

- 텍스트 보고서: `verification_report_YYYYMMDD_HHMMSS.txt`
- PDF 보고서: `verification_report_YYYYMMDD_HHMMSS.pdf`

## 사용자 계약서 형식

사용자 계약서는 `.txt` 파일로 작성하며, 다음 형식을 따릅니다:

```text
제1조(목적) 본 계약은 ...

제2조(정의) 본 계약에서 사용하는 용어의 정의는 다음과 같다.
1. "데이터"란 ...
2. "데이터 제공자"란 ...

제3조(계약기간) 본 계약의 유효기간은 ...
```

## 환경 변수 설정

검증 기능을 사용하려면 다음 환경 변수가 설정되어 있어야 합니다:

```bash
AZURE_OPENAI_API_KEY=your_api_key
AZURE_ENDPOINT=your_endpoint
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_LLM_DEPLOYMENT=gpt-4o
```

## 도커 환경에서 실행

```bash
# 도커 컨테이너 접속
docker exec -it <container_name> bash

# ingestion CLI 실행
python ingestion/ingest.py

# verify 명령어 실행
ingestion> verify -u data/user_contract_sample.txt --format both
```

## 통합된 기능

이제 ingestion 파이프라인에서 다음 모든 작업을 수행할 수 있습니다:

1. **문서 파싱** (`run --mode parsing`)
2. **텍스트 청킹** (`run --mode chunking`)
3. **임베딩 생성** (`run --mode embedding`)
4. **FAISS 검색** (`search`)
5. **계약서 검증** (`verify`) ← 새로 추가!

## 문제 해결

### 표준 계약서를 찾을 수 없음
```
[ERROR] 표준 계약서를 찾을 수 없습니다
```
→ `data/chunked_documents/parsed_43_73_table_5_chunks.jsonl` 파일이 있는지 확인

### FAISS 인덱스를 찾을 수 없음
```
[ERROR] FAISS 인덱스를 찾을 수 없습니다
```
→ `search_indexes/faiss/` 디렉토리에 인덱스 파일이 있는지 확인
→ 없다면 `run --mode s_embedding` 명령어로 인덱스 생성

### Azure OpenAI API 오류
```
[ERROR] Azure OpenAI 환경변수가 설정되지 않았습니다
```
→ `.env` 파일에 Azure OpenAI 관련 환경 변수 설정 확인

## 다음 단계

Task 8.2와 8.3을 완료하여 대화형 텍스트 입력 및 상세한 결과 출력 기능을 추가할 예정입니다.
