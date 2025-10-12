# Chunked Documents

이 디렉토리는 청킹된 중간 결과를 저장합니다.

## 구조

```
chunked_documents/
├── standard_contracts/        # 표준계약서 청킹 결과
│   ├── contract_type1_chunks.jsonl
│   └── ...
└── guidebooks/               # 활용안내서 청킹 결과
    └── guidebook_chunks.jsonl
```

## 용도

- **청킹 검증**: 청크 크기, 오버랩 설정이 적절한지 확인
- **단계별 디버깅**: 파싱 → 청킹 → 임베딩을 독립적으로 테스트
- **비용 절감**: 청킹까지 완료 후 임베딩 모델만 변경하여 재실행 가능
- **품질 관리**: 청크가 의미 단위로 잘 분리되었는지 검토

## 파일 형식 (JSONL)

각 라인은 하나의 청크를 나타냅니다:

```jsonl
{"chunk_id": "contract1_art1_0", "text": "제1조 (목적) 본 계약은...", "metadata": {"article": 1, "page": 3}, "tokens": 450}
{"chunk_id": "contract1_art2_0", "text": "제2조 (정의) 본 계약에서...", "metadata": {"article": 2, "page": 4}, "tokens": 520}
{"chunk_id": "contract1_art2_1", "text": "제2조 뒷부분...", "metadata": {"article": 2, "page": 5}, "tokens": 380}
```

## 실행 예시

```bash
# 1단계: 파싱만
docker compose --profile ingestion run --rm ingestion \
  python -m ingestion.ingest --mode parse

# 2단계: 청킹만 (파싱 결과 사용)
docker compose --profile ingestion run --rm ingestion \
  python -m ingestion.ingest --mode chunk

# 3단계: 임베딩 + 인덱싱 (청킹 결과 사용)
docker compose --profile ingestion run --rm ingestion \
  python -m ingestion.ingest --mode index

# 청킹 결과 확인
head -n 5 data/chunked_documents/standard_contracts/contract_type1_chunks.jsonl
```

## 청킹 통계 파일

각 디렉토리에는 통계 파일도 저장됩니다:

```json
// standard_contracts/stats.json
{
  "total_chunks": 1250,
  "avg_chunk_size": 520,
  "min_chunk_size": 200,
  "max_chunk_size": 1000,
  "chunking_params": {
    "chunk_size": 1000,
    "overlap": 100,
    "method": "article_based"
  },
  "processed_at": "2025-10-04T15:30:00"
}
```

