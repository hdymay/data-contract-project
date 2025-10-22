# 조/별지 단위 청커 (ArticleChunker) 사용 가이드

## 개요

`ArticleChunker`는 표준계약서의 `*_structured.json` 파일을 입력으로 받아 조(article)와 별지(exhibit) 단위로 청킹하는 모듈.

## 출력 형식

청크 구조:

```json
{
  "id": "ART-015",
  "global_id": "urn:std:provide:art:015",
  "doc_type": "std_contract",
  "contract_type": "provide",
  "unit_type": "article",
  "unit_no": 15,
  "order_index": 15,
  "breadcrumb": "제15조",
  "title": "계약의 해제 또는 해지",
  "text_raw": "...",
  "text_norm": "...",
  "anchors": [
    {"unit_type":"articleText", "offset_raw": 12, "offset_norm": 8, "breadcrumb": "제15조 조본문"},
    {"unit_type":"clause", "offset_raw": 82, "offset_norm": 78, "breadcrumb": "제15조 제1항"}
  ],
  "source_file": "provide_std_contract_structured.json"
}
```

## Docker를 통한 사용법

### 1. Docker 컨테이너 실행

```bash
# docker-compose를 사용한 실행
docker-compose --profile ingestion run --rm ingestion

# 또는 직접 빌드 후 실행
docker-compose build ingestion
docker-compose --profile ingestion run --rm ingestion
```

### 2. CLI 명령어

ingestion CLI 진입 후 다음 명령어 사용:

#### 단일 파일 청킹
```bash
ingestion> run --mode art_chunking --file provide_std_contract_structured.json
```

#### 모든 파일 청킹
```bash
ingestion> run --mode art_chunking --file all
```

#### 상태 확인
```bash
ingestion> status
ingestion> status --detail
```

#### 파일 목록 확인
```bash
ingestion> ls extracted
ingestion> ls chunked
```

## 로컬 테스트 (Docker 없이)

로컬 환경 테스트:

```bash
# PYTHONPATH 설정
export PYTHONPATH=/path/to/data-contract-project  # Linux/Mac
$env:PYTHONPATH="C:\Python Projects\data-contract-project"  # Windows PowerShell

# 테스트 스크립트 실행
python ingestion/test_chunker.py
```

## 청킹 특징

### 1. 청킹 단위
- **조(article)**: 하나의 조 전체를 하나의 청크로 처리
- **별지(exhibit)**: 하나의 별지 전체를 하나의 청크로 처리

### 2. text_raw vs text_norm
- **text_raw**: 개행 문자 포함, 원본 텍스트 그대로
- **text_norm**: 개행 제거 및 공백으로 연결, 인덱스 표현식 제거

### 3. anchors
각 청크 내의 하위 항목(항, 호, 목, 표 등)의 위치 기록.

## 출력 파일

입력 파일: `data/extracted_documents/provide_std_contract_structured.json`
출력 파일: `data/chunked_documents/provide_std_contract_art_chunks.json`

## 다음 단계

청킹 완료 후 임베딩 단계 진행:

```bash
ingestion> run --mode embedding --file provide_std_contract_art_chunks.json
```

## 주의사항

- 현재는 **표준계약서 전용** (활용안내서는 미구현)
- `*_structured.json` 파일만 입력으로 사용 가능
- 계약 유형(provide, create, process 등)은 파일명에서 자동 추출

