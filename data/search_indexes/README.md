# Search Indexes

이 디렉토리는 지식베이스 검색 인덱스를 저장합니다.

## 구조

```
search_indexes/
├── whoosh/                    # Whoosh 키워드 인덱스
│   └── index/                 # Whoosh 인덱스 파일들
├── faiss/                     # FAISS 벡터 인덱스
│   ├── index.faiss           # FAISS 인덱스 바이너리
│   └── id_to_metadata.json   # 벡터 ID → 문서 메타데이터 매핑
├── chunks/                    # 원본 청크 데이터
│   └── documents.jsonl       # 각 청크의 전체 텍스트 + 메타데이터
└── metadata.json             # 인덱스 버전, 생성일시, 통계 정보
```

## 생성 방법

```bash
docker compose --profile ingestion run --rm ingestion
```

## 용도

- **whoosh/**: BM25 기반 키워드 검색 (정확한 용어 매칭)
- **faiss/**: 시맨틱 벡터 검색 (의미 유사도 검색)
- **chunks/**: 검색 결과 본문 제공용 원본 데이터
- **metadata.json**: 인덱스 버전 관리 및 통계

