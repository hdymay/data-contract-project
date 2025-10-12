# Extracted Documents

이 디렉토리는 파싱된 중간 결과를 저장합니다.

## 구조

```
extracted_documents/
├── standard_contracts/        # 표준계약서 파싱 결과
│   ├── contract_type1.json   # JSON 형식의 구조화된 데이터
│   └── ...
└── guidebooks/               # 활용안내서 파싱 결과
    └── guidebook.json
```

## 용도

- **디버깅**: 파싱이 제대로 되었는지 확인
- **단계별 실행**: 파싱 → 청킹 → 임베딩을 독립적으로 실행
- **검증**: 원본 PDF와 파싱 결과 비교

## 파일 형식

각 JSON 파일은 다음 구조를 가집니다:

```json
{
  "source_file": "contract_type1.pdf",
  "parsed_at": "2025-10-04T15:30:00",
  "total_pages": 25,
  "sections": [
    {
      "section_id": "art_1",
      "title": "제1조 (목적)",
      "content": "...",
      "metadata": {
        "page": 3,
        "article_num": 1
      }
    }
  ]
}
```

## 실행 예시

```bash
# 1단계: 파싱만 실행
docker compose --profile ingestion run --rm ingestion \
  python -m ingestion.ingest \
  --mode parse-only \
  --input /app/data/source_documents \
  --output /app/data/extracted_documents

# 2단계: 파싱 결과 확인
cat data/extracted_documents/standard_contracts/contract_type1.json

# 3단계: 청킹 및 임베딩 실행
docker compose --profile ingestion run --rm ingestion \
  python -m ingestion.ingest \
  --mode index-only \
  --input /app/data/extracted_documents \
  --output /app/search_indexes
```

