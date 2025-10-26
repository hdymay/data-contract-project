# Design Document

## Overview

계약서 조문 존재 여부 검증 시스템은 사용자가 업로드한 계약서가 표준 계약서의 모든 필수 조문을 포함하고 있는지 검증하는 시스템입니다. 

### 기존 Ingestion 파이프라인 활용

본 시스템은 기존에 구축된 ingestion 자동화 파이프라인을 활용합니다:
- **파싱**: PDF/DOCX → JSON (이미 구현됨)
- **청킹**: JSON → JSONL (이미 구현됨)
- **임베딩 & 인덱싱**: JSONL → FAISS 인덱스 (기존 인프라 확장)

### 3단계 검증 프로세스

1. **BM25 키워드 검색**: 항의 실제 내용(text 필드)에서 핵심 키워드 매칭
   - 조문 제목("제1조")이 아닌 항의 본문 내용을 검색
   - 예: "데이터제공자", "이용을 허락", "대가를 지급" 등
2. **FAISS 벡터 검색**: 항 내용의 의미론적 유사도 기반 매칭 (기존 FAISS 인덱서 활용)
3. **LLM 최종 검증**: 법률 용어의 미묘한 차이 판단

**중요**: 조문 제목(title)은 계약서마다 다를 수 있으므로, 항의 실제 내용(text)을 기준으로 비교합니다.

이 하이브리드 접근 방식은 조문의 항과 호가 많고, 표현이 다양한 계약서 데이터를 정확하게 비교하기 위해 설계되었습니다.

**참고**: 본 시스템은 향후 체크리스트 검증 및 충실도 평가와 결합하여 전체 계약서 정합성 측정 시스템의 일부가 될 예정입니다.

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│  User Contract  │
│   (JSONL)       │
└────────┬────────┘
         │
         v
┌─────────────────────────────────────┐
│  Contract Verification Service      │
│  ┌──────────────────────────────┐  │
│  │ 1. Load Standard Contract    │  │
│  │ 2. Load User Contract        │  │
│  │ 3. Embed Clauses             │  │
│  │ 4. Compare Similarity        │  │
│  │ 5. Identify Missing Clauses  │  │
│  └──────────────────────────────┘  │
└────────┬────────────────────────────┘
         │
         v
┌─────────────────────────────────────┐
│  Report Generator                   │
│  - Text Report                      │
│  - PDF Report                       │
└─────────────────────────────────────┘
```

### Component Architecture

시스템은 다음 주요 컴포넌트로 구성됩니다:

1. **Data Loader**: JSONL 파일에서 계약서 조문 데이터를 로드
2. **Embedding Service**: OpenAI text-embedding-3-large를 사용하여 텍스트 임베딩 생성
3. **Hybrid Search Engine**: BM25와 FAISS를 결합한 하이브리드 검색
4. **LLM Verification Service**: LLM을 사용한 최종 의미론적 검증
5. **Verification Engine**: 누락된 조문 식별 및 검증 결과 생성
6. **Report Generator**: 텍스트 및 PDF 형식의 보고서 생성

## Components and Interfaces

### 1. Data Loader

**책임**: 계약서 데이터를 로드하고 파싱

**인터페이스**:
```python
class ContractDataLoader:
    def load_standard_contract(self, file_path: str) -> List[ClauseData]:
        """
        표준 계약서 로드 (JSONL 형식)
        data/chunked_documents/parsed_43_73_table_5_chunks.jsonl
        """
        pass
    
    def load_user_contract_from_text(self, text: str) -> List[ClauseData]:
        """
        사용자가 붙여넣은 평문 텍스트를 파싱
        - 빈 줄 기준으로 문단 분리
        - 각 문단을 ClauseData로 변환
        - id는 순차적으로 부여 (user-1, user-2, ...)
        """
        pass
    
    def filter_clauses(self, clauses: List[ClauseData], clause_type: str = "조") -> List[ClauseData]:
        """특정 타입의 조문만 필터링 (기본값: "조")"""
        pass
```

### 2. Embedding Service (Azure OpenAI 사용)

**책임**: Azure OpenAI API를 사용하여 텍스트 임베딩 생성

**참고**: 
- 기존 Azure OpenAI 설정 그대로 사용
- 환경 변수: `AZURE_OPENAI_API_KEY`, `AZURE_ENDPOINT`, `AZURE_EMBEDDING_DEPLOYMENT`
- 모델: text-embedding-3-large

**인터페이스**:
```python
class EmbeddingService:
    def __init__(self, 
                 api_key: str,
                 azure_endpoint: str,
                 deployment: str = "text-embedding-3-large"):
        """
        Azure OpenAI 임베딩 서비스 초기화
        """
        pass
    
    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트의 임베딩 벡터 생성"""
        pass
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트의 임베딩 벡터를 배치로 생성"""
        pass
```

### 3. Hybrid Search Engine (기존 FAISS 인덱서 확장)

**책임**: BM25와 FAISS를 결합하여 후보 조문 검색

**참고**: 
- FAISS 부분은 기존 `ingestion/indexers/faiss_indexer.py` 확장
- BM25는 새로 추가 (rank-bm25 라이브러리 사용)

**인터페이스**:
```python
class HybridSearchEngine:
    def __init__(self, faiss_index_path: Path, bm25_weight: float = 0.3, faiss_weight: float = 0.7):
        """
        하이브리드 검색 초기화
        faiss_index_path: 기존 ingestion으로 생성된 FAISS 인덱스 경로
        """
        pass
    
    def build_bm25_index(self, clauses: List[ClauseData]) -> None:
        """BM25 인덱스 구축 (키워드 기반)"""
        pass
    
    def load_faiss_index(self, index_name: str) -> bool:
        """기존 FAISS 인덱스 로드"""
        pass
    
    def search(self, query_text: str, query_embedding: List[float], 
              top_k: int = 5) -> List[Tuple[int, float]]:
        """하이브리드 검색 수행 (BM25 + FAISS 점수 결합)"""
        pass
    
    def get_bm25_scores(self, query_text: str) -> List[float]:
        """BM25 점수 계산"""
        pass
    
    def get_faiss_scores(self, query_embedding: List[float], top_k: int) -> List[Tuple[int, float]]:
        """FAISS 유사도 점수 계산 (기존 인덱서 활용)"""
        pass
```

### 4. LLM Verification Service

**책임**: LLM을 사용하여 후보 조문의 의미론적 일치 여부 최종 검증

**인터페이스**:
```python
class LLMVerificationService:
    def __init__(self, model: str = "gpt-4o"):
        """LLM 모델 초기화"""
        pass
    
    def verify_clause_match(self, standard_clause: ClauseData, 
                           candidate_clause: ClauseData) -> VerificationDecision:
        """두 조문이 의미적으로 동일한지 LLM으로 검증"""
        pass
    
    def batch_verify(self, pairs: List[Tuple[ClauseData, ClauseData]]) -> List[VerificationDecision]:
        """여러 조문 쌍을 배치로 검증"""
        pass
    
    def explain_mismatch(self, standard_clause: ClauseData, 
                        candidate_clause: ClauseData) -> str:
        """불일치 이유 설명 생성"""
        pass
```

### 5. Verification Engine

**책임**: 표준 계약서와 사용자 계약서를 비교하여 누락된 조문 식별

**인터페이스**:
```python
class ContractVerificationEngine:
    def __init__(self, embedding_service: EmbeddingService, 
                 hybrid_search: HybridSearchEngine,
                 llm_verification: LLMVerificationService):
        """검증 엔진 초기화"""
        pass
    
    def verify_contract(self, standard_clauses: List[ClauseData], 
                       user_clauses: List[ClauseData]) -> VerificationResult:
        """계약서 검증 수행 (3단계 프로세스)"""
        pass
    
    def identify_missing_clauses(self, standard_clauses: List[ClauseData],
                                user_clauses: List[ClauseData],
                                match_results: List[MatchResult]) -> List[ClauseData]:
        """누락된 조문 식별"""
        pass
```

### 6. Report Generator

**책임**: 검증 결과를 텍스트 및 PDF 형식으로 생성

**인터페이스**:
```python
class ReportGenerator:
    def generate_text_report(self, result: VerificationResult, 
                            output_path: str) -> str:
        """텍스트 형식 보고서 생성"""
        pass
    
    def generate_pdf_report(self, result: VerificationResult, 
                           output_path: str) -> str:
        """PDF 형식 보고서 생성"""
        pass
    
    def format_missing_clauses(self, missing_clauses: List[ClauseData]) -> str:
        """누락된 조문을 읽기 쉬운 형식으로 포맷"""
        pass
```

## Data Models

### ClauseData

계약서의 개별 조문 데이터를 표현하는 모델

```python
@dataclass
class ClauseData:
    id: str                    # 조문 ID (예: "42-1")
    title: str                 # 조문 제목 (예: "제1조(목적)")
    subtitle: Optional[str]    # 부제목
    type: str                  # 타입 (예: "조", "해설")
    text: str                  # 조문 내용
    embedding: Optional[List[float]] = None  # 임베딩 벡터 (캐시용)
```

### VerificationDecision

LLM 검증 결과를 표현하는 모델

```python
@dataclass
class VerificationDecision:
    is_match: bool                 # 매칭 여부
    confidence: float              # 신뢰도 (0.0 ~ 1.0)
    reasoning: str                 # 판단 근거
```

### MatchResult

조문 매칭 결과를 표현하는 모델

```python
@dataclass
class MatchResult:
    standard_clause: ClauseData    # 표준 계약서 조문
    matched_clause: Optional[ClauseData]  # 매칭된 사용자 계약서 조문
    bm25_score: float             # BM25 점수
    faiss_score: float            # FAISS 유사도 점수
    hybrid_score: float           # 결합 점수
    llm_decision: Optional[VerificationDecision]  # LLM 검증 결과
    is_matched: bool              # 최종 매칭 여부
```

### VerificationResult

전체 검증 결과를 표현하는 모델

```python
@dataclass
class VerificationResult:
    total_standard_clauses: int           # 표준 계약서 총 조문 수
    matched_clauses: int                  # 매칭된 조문 수
    missing_clauses: List[ClauseData]     # 누락된 조문 목록
    match_results: List[MatchResult]      # 상세 매칭 결과
    verification_date: datetime           # 검증 수행 일시
    is_complete: bool                     # 모든 조문 존재 여부
    
    @property
    def completion_rate(self) -> float:
        """완성도 비율 계산"""
        return (self.matched_clauses / self.total_standard_clauses) * 100
```

## Error Handling

### 예외 처리 전략

1. **파일 로드 오류**
   - JSONL 파일이 존재하지 않거나 읽을 수 없는 경우
   - 처리: `FileNotFoundError` 발생 및 명확한 오류 메시지 제공

2. **JSON 파싱 오류**
   - JSONL 형식이 올바르지 않은 경우
   - 처리: `JSONDecodeError` 발생 및 문제가 있는 라인 번호 표시

3. **OpenAI API 오류**
   - API 키가 유효하지 않거나 요청 한도 초과
   - 처리: 재시도 로직 구현 (최대 3회), 실패 시 명확한 오류 메시지

4. **임베딩 생성 실패**
   - 텍스트가 너무 길거나 비어있는 경우
   - 처리: 텍스트 자르기 또는 건너뛰기, 로그 기록

5. **보고서 생성 오류**
   - 파일 쓰기 권한 없음 또는 디스크 공간 부족
   - 처리: 대체 경로 시도 또는 메모리에 결과 유지

### 로깅 전략

- 모든 주요 작업에 대해 INFO 레벨 로깅
- 오류 발생 시 ERROR 레벨 로깅 및 스택 트레이스 포함
- 디버깅을 위한 DEBUG 레벨 로깅 (임베딩 생성, 유사도 계산 등)

## Testing Strategy

### 단위 테스트

각 컴포넌트에 대한 독립적인 테스트:

1. **Data Loader 테스트**
   - 유효한 JSONL 파일 로드
   - 잘못된 형식 처리
   - 조문 필터링 기능

2. **Embedding Service 테스트**
   - 임베딩 생성 (모킹된 OpenAI API 사용)
   - 캐싱 동작 확인
   - 배치 처리 기능

3. **Similarity Matcher 테스트**
   - 코사인 유사도 계산 정확성
   - 임계값 기반 매칭 판단
   - 최적 매칭 찾기

4. **Verification Engine 테스트**
   - 완전한 계약서 검증 (모든 조문 존재)
   - 부분적으로 누락된 계약서 검증
   - 빈 계약서 처리

5. **Report Generator 테스트**
   - 텍스트 보고서 생성
   - PDF 보고서 생성
   - 포맷팅 정확성

### 통합 테스트

전체 워크플로우 테스트:

1. 실제 표준 계약서 데이터로 검증 수행
2. 다양한 사용자 계약서 시나리오 테스트
3. 보고서 생성 및 저장 확인

### 테스트 데이터

- `data/chunked_documents/parsed_43_73_table_5_chunks.jsonl`을 표준 계약서로 사용
- 테스트용 사용자 계약서 샘플 생성 (일부 조문 누락)

## Performance Considerations

### 임베딩 캐싱

- 동일한 텍스트에 대한 중복 임베딩 생성 방지
- 메모리 기반 캐시 사용 (딕셔너리)
- 향후 확장: 파일 기반 또는 데이터베이스 캐싱

### 배치 처리

- OpenAI API 호출 최소화를 위해 배치 임베딩 사용
- 배치 크기: 100개 텍스트 (API 제한 고려)

### 유사도 계산 최적화

- NumPy를 사용한 벡터화 연산
- 불필요한 비교 건너뛰기 (이미 매칭된 조문)

## Security Considerations

1. **API 키 관리**
   - 환경 변수를 통한 OpenAI API 키 관리
   - 코드에 하드코딩 금지

2. **데이터 보호**
   - 계약서 데이터의 민감성 고려
   - 임시 파일 사용 시 적절한 삭제

3. **입력 검증**
   - JSONL 파일 형식 검증
   - 텍스트 길이 제한 확인

## Deployment Considerations

### 환경 변수

```
# Azure OpenAI (기존 설정 사용)
AZURE_OPENAI_API_KEY=<your-azure-api-key>
AZURE_ENDPOINT=<your-azure-endpoint>
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# LLM (검증용)
AZURE_LLM_DEPLOYMENT=gpt-4o-mini

# 검증 설정
SIMILARITY_THRESHOLD=0.85
BM25_WEIGHT=0.3
FAISS_WEIGHT=0.7
STANDARD_CONTRACT_PATH=data/chunked_documents/parsed_43_73_table_5_chunks.jsonl
USER_CONTRACT_DIR=data/user_contracts
```

### 의존성

```
openai>=1.0.0  # Azure OpenAI 사용
numpy>=1.24.0
faiss-cpu>=1.7.4  # 벡터 검색용
rank-bm25>=0.2.2  # BM25 검색용
reportlab>=4.0.0  # PDF 생성용
python-dotenv>=1.0.0
```

### 디렉토리 구조

```
backend/
  clause_verification/          # 새로 추가
    __init__.py
    data_loader.py              # 기존 ingestion 활용
    hybrid_search.py            # BM25 + FAISS (기존 인프라 확장)
    llm_verification.py
    verification_engine.py
    report_generator.py
    models.py
    config.py
  tests/
    test_data_loader.py
    test_hybrid_search.py
    test_llm_verification.py
    test_verification_engine.py
    test_report_generator.py

ingestion/                      # 기존 파이프라인 (재사용)
  parsers/
    std_contract_docx_parser.py
    std_contract_pdf_parser.py
  processors/
    chunker.py                  # 재사용
    embedder.py                 # 확장 필요
  indexers/
    faiss_indexer.py            # 확장 필요
  ingest.py

data/
  source_documents/             # 원본 계약서
  extracted_documents/          # 파싱 결과 (JSON)
  chunked_documents/            # 청킹 결과 (JSONL)
    parsed_43_73_table_5_chunks.jsonl  # 표준 계약서 (기준)
  reports/                      # 검증 보고서
search_indexes/
  faiss/                        # FAISS 인덱스

# 사용자 계약서는 대화형 입력으로 직접 제공 (파일 저장 불필요)
```

## Verification Workflow

각 표준 계약서 항(clause)에 대해 다음 워크플로우를 수행합니다:

```
For each standard_clause in standard_contract:
  
  1. Extract Content
     └─ 항의 실제 내용(text 필드) 추출
        예: "본 계약은 ○○○(이하 "데이터제공자"라 한다)가..."
  
  2. Hybrid Search (BM25 + FAISS)
     ├─ BM25: 항 내용의 핵심 키워드 검색 → top-5 후보
     │   예: "데이터제공자", "데이터이용자", "대가", "지급"
     ├─ FAISS: 항 내용의 벡터 유사도 검색 → top-5 후보
     └─ 점수 결합 (0.3 * BM25 + 0.7 * FAISS) → 최종 top-3
  
  3. LLM Verification
     ├─ 각 후보 항의 내용을 LLM으로 비교
     ├─ 의미적 일치 여부 판단 (조문 제목 무시)
     ├─ 신뢰도 점수 및 판단 근거 생성
     └─ 첫 번째 매칭 성공 시 → 다음 항으로
  
  4. Result Recording
     ├─ 매칭 성공: MatchResult 저장
     └─ 매칭 실패: 누락 항으로 표시
```

**참고**: 
- 조문 제목(title)은 비교 기준이 아님 (계약서마다 다를 수 있음)
- 항의 실제 내용(text)만을 기준으로 존재 여부 판단

## Future Enhancements

### Phase 2: 체크리스트 검증
- 계약서 필수 항목 체크리스트 준수 여부 확인
- 동일한 하이브리드 검색 인프라 재사용

### Phase 3: 충실도 평가
- 조문의 내용 충실도 평가
- 표준 대비 누락/변경된 세부 내용 분석

### 기타 개선사항
1. **다중 표준 계약서 지원**: 여러 유형의 표준 계약서 선택 가능
2. **웹 인터페이스**: FastAPI 엔드포인트 추가
3. **실시간 검증**: 계약서 작성 중 실시간 피드백
4. **조문 추천**: 누락된 조문에 대한 텍스트 제안
5. **히스토리 관리**: 검증 이력 저장 및 조회
