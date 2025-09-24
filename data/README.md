# 데이터 디렉토리

이 디렉토리는 다음과 같은 데이터를 저장합니다:

## 디렉토리 구조
```
data/
├── standard_contracts/     # 표준계약서 5종
│   ├── data_provision/     # 데이터 제공형
│   ├── data_creation/      # 데이터 창출형
│   ├── data_processing/    # 데이터 가공서비스형
│   ├── data_brokerage_provider/  # 데이터 중개거래형(운영자-제공자)
│   └── data_brokerage_user/      # 데이터 중개거래형(운영자-이용자)
├── guide/                  # 활용안내서
├── embeddings/             # 임베딩 인덱스
│   ├── faiss_index/        # FAISS 인덱스
│   └── whoosh_index/       # Woosh 인덱스
├── database/               # SQLite DB
├── uploads/                # 업로드된 파일
└── reports/                # 생성된 리포트
```

## 사용법
1. 표준계약서 파일들을 해당 디렉토리에 업로드
2. 활용안내서 파일을 guide/ 디렉토리에 업로드
3. 지식베이스 구축 스크립트 실행
