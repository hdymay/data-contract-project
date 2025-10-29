# Design Document

## Overview

본 문서는 하이브리드 검색 로직 고도화를 위한 설계를 정의합니다. 현재 시스템은 사용자 조항의 제목과 본문을 하나의 쿼리로 결합하여 검색하고 있으나, 이를 독립적으로 검색하고 가중합하는 방식으로 개선합니다.

### 주요 개선사항

1. **Whoosh 검색**: 제목과 본문을 별도 필드로 검색하고 7:3 가중합
2. **FAISS 검색**: 제목과 본문을 별도 인덱스로 구축하고 7:3 가중합
3. **조 단위 취합**: top-5 평균 방식 제거, top-1 직접 선택 방식으로 변경
4. **UI 설정**: 가중합 비율을 Streamlit UI에서 조정 가능

## Architecture

### 현재 아키텍처

```
사용자 조항 (제목 + 본문)
    ↓
단일 쿼리 생성: "{본문} {제목}"
    ↓
┌─────────────────┬─────────────────┐
│  FAISS 검색     │  Whoosh 검색    │
│  (text_norm만)  │  (text_norm +   │
│                 │   title OR 검색)│
└─────────────────┴─────────────────┘
    ↓
하이브리드 융합 (85:15)
    ↓
Top-5 청크 선택
    ↓
조별 평균 점수 계산
    ↓
Top-1 조 선택
```

### 개선된 아키텍처

```
사용자 조항
    ↓
┌──────────────┬──────────────┐
│ 제목 쿼리    │ 본문 쿼리    │
└──────────────┴──────────────┘
    ↓              ↓
┌─────────────────────────────────────────┐
│         FAISS 검색 (별도 인덱스)         │
├──────────────┬──────────────────────────┤
│ title 인덱스 │ text_norm 인덱스         │
│ (제목 쿼리)  │ (본문 쿼리)              │
└──────────────┴──────────────────────────┘
    ↓              ↓
    └──────┬───────┘
           ↓
    청크별 가중합 (본문:제목 = 7:3)
           ↓
┌─────────────────────────────────────────┐
│         Whoosh 검색 (멀티필드)          │
├──────────────┬──────────────────────────┤
│ title 필드   │ text_norm 필드           │
│ (제목 쿼리)  │ (본문 쿼리)              │
└──────────────┴──────────────────────────┘
    ↓              ↓
    └──────┬───────┘
           ↓
    청크별 가중합 (본문:제목 = 7:3)
           ↓
하이브리드 융합 (시멘틱:키워드 = 85:15)
           ↓
    Top-1 청크 선택 (조별)
           ↓
    조별 그룹화 및 정렬
```

## Components and Interfaces

### 1. Ingestion Container

#### 1.1 TextEmbedder (수정)

**파일**: `ingestion/processors/embedder.py`

**변경사항**:
- 각 청크의 `text_norm`과 `title`을 각각 임베딩
- 두 개의 FAISS 인덱스 생성 (text_norm용, title용)

**새로운 메서드**:
```python
def create_dual_embeddings(self, chunks: List[Dict]) -> Tuple[List[Any], List[Any]]:
    """
    청크의 text_norm과 title을 각각 임베딩
    
    Returns:
        (text_norm_embeddings, title_embeddings)
    """
    pass

def save_dual_faiss_indexes(
    self,
    text_norm_embeddings: List[List[float]],
    title_embeddings: List[List[float]],
    source_filename: str,
    output_dir: Path
):
    """
    두 개의 FAISS 인덱스 저장
    - {base_name}_text.faiss
    - {base_name}_title.faiss
    """
    pass
```

#### 1.2 WhooshIndexer (유지)

**파일**: `ingestion/indexers/whoosh_indexer.py`

**변경사항**: 없음 (이미 멀티필드 인덱싱 지원)

### 2. Backend - Consistency Agent

#### 2.1 HybridSearcher (수정)

**파일**: `backend/consistency_agent/hybrid_searcher.py`

**변경사항**:
- 제목과 본문 쿼리를 분리하여 처리
- FAISS 검색 시 두 개의 인덱스 사용
- Whoosh 검색 시 두 개의 쿼리 사용
- 청크별 가중합 계산 추가

**새로운 속성**:
```python
self.text_weight = 0.7  # 본문 가중치 (기본값)
self.title_weight = 0.3  # 제목 가중치 (기본값)
self.faiss_index_text = None  # text_norm 인덱스
self.faiss_index_title = None  # title 인덱스
```

**수정된 메서드**:
```python
def load_indexes(
    self,
    faiss_index_text,
    faiss_index_title,
    chunks: List[Dict],
    whoosh_indexer
):
    """두 개의 FAISS 인덱스 로드"""
    pass

def dense_search(
    self,
    text_query: str,
    title_query: str,
    top_k: int = 50,
    contract_id: str = None
) -> List[Dict[str, Any]]:
    """
    제목과 본문을 별도로 검색하고 가중합
    
    1. text_query를 text_norm 인덱스에서 검색
    2. title_query를 title 인덱스에서 검색
    3. 동일 청크에 대해 가중합 계산
    """
    pass

def sparse_search(
    self,
    text_query: str,
    title_query: str,
    top_k: int = 50
) -> List[Dict[str, Any]]:
    """
    제목과 본문을 별도 필드로 검색하고 가중합
    
    1. text_query를 text_norm 필드에서 검색
    2. title_query를 title 필드에서 검색
    3. 동일 청크에 대해 가중합 계산
    """
    pass

def search(
    self,
    text_query: str,
    title_query: str,
    top_k: int = 10,
    dense_top_k: int = 50,
    sparse_top_k: int = 50,
    contract_id: str = None
) -> List[Dict[str, Any]]:
    """하이브리드 검색 (제목/본문 분리)"""
    pass

def set_field_weights(self, text_weight: float, title_weight: float):
    """본문:제목 가중치 설정"""
    if abs(text_weight + title_weight - 1.0) > 0.001:
        raise ValueError("가중치 합은 1.0이어야 합니다")
    self.text_weight = text_weight
    self.title_weight = title_weight
```

#### 2.2 WhooshSearcher (수정)

**파일**: `backend/shared/services/whoosh_searcher.py`

**변경사항**:
- 제목과 본문 쿼리를 분리하여 검색
- 각 필드별 점수를 가중합

**새로운 메서드**:
```python
def search_with_field_weights(
    self,
    text_query: str,
    title_query: str,
    text_weight: float = 0.7,
    title_weight: float = 0.3,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    제목과 본문을 별도로 검색하고 가중합
    
    1. text_query를 text_norm 필드에서 검색
    2. title_query를 title 필드에서 검색
    3. 청크별로 두 점수를 가중합
    """
    pass
```

#### 2.3 ArticleMatcher (수정)

**파일**: `backend/consistency_agent/nodes/article_matcher.py`

**변경사항**:
- 제목과 본문 쿼리를 분리하여 생성
- top-5 → top-1 방식으로 변경
- 조별 평균 계산 로직 제거

**수정된 메서드**:
```python
def _build_search_queries(
    self,
    sub_item: str,
    article_title: str
) -> Tuple[str, str]:
    """
    검색 쿼리 생성 (제목/본문 분리)
    
    Returns:
        (text_query, title_query)
    """
    return (sub_item, article_title)

def _hybrid_search(
    self,
    text_query: str,
    title_query: str,
    contract_type: str,
    top_k: int,
    contract_id: str = None
) -> List[Dict]:
    """하이브리드 검색 (제목/본문 분리)"""
    pass

def _select_best_article_from_chunks(
    self,
    chunk_results: List[Dict]
) -> Optional[Dict]:
    """
    청크 검색 결과에서 최고 점수 조 1개 선정
    
    변경사항: top-5 평균 → top-1 직접 선택
    각 조의 최고 점수 청크를 대표 점수로 사용
    """
    pass
```

#### 2.4 KnowledgeBaseLoader (수정)

**파일**: `backend/shared/services/knowledge_base_loader.py`

**변경사항**:
- 두 개의 FAISS 인덱스 로드 지원

**수정된 메서드**:
```python
def load_faiss_indexes(self, contract_type: str) -> Optional[Tuple[Any, Any]]:
    """
    FAISS 인덱스 로드 (text_norm, title)
    
    Returns:
        (text_index, title_index) 또는 None
    """
    pass
```

### 3. Frontend - Streamlit UI

#### 3.1 검색 설정 UI (신규)

**파일**: `frontend/app.py`

**추가 기능**:
- 사이드바에 검색 설정 섹션 추가
- 본문:제목 가중치 슬라이더 (기본값 0.7:0.3)
- 시멘틱:키워드 가중치 슬라이더 (기본값 0.85:0.15)
- 설정 변경 시 세션 상태에 저장

**UI 구성**:
```python
with st.sidebar:
    st.header("검색 설정")
    
    st.subheader("본문:제목 가중치")
    text_weight = st.slider(
        "본문 가중치",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.05,
        help="본문과 제목의 가중합 비율 (본문:제목)"
    )
    st.caption(f"본문: {text_weight:.0%}, 제목: {1-text_weight:.0%}")
    
    st.subheader("시멘틱:키워드 가중치")
    dense_weight = st.slider(
        "시멘틱 가중치",
        min_value=0.0,
        max_value=1.0,
        value=0.85,
        step=0.05,
        help="시멘틱(FAISS)과 키워드(Whoosh)의 가중합 비율"
    )
    st.caption(f"시멘틱: {dense_weight:.0%}, 키워드: {1-dense_weight:.0%}")
```

## Data Models

### FAISS 인덱스 파일 구조

**기존**:
```
search_indexes/faiss/
  ├── provide_std_contract.faiss
  ├── create_std_contract.faiss
  └── ...
```

**개선**:
```
search_indexes/faiss/
  ├── provide_std_contract_text.faiss    # text_norm 인덱스
  ├── provide_std_contract_title.faiss   # title 인덱스
  ├── create_std_contract_text.faiss
  ├── create_std_contract_title.faiss
  └── ...
```

### 검색 결과 데이터 구조

**HybridSearcher 반환값**:
```python
{
    'chunk': {
        'id': str,
        'global_id': str,
        'unit_type': str,
        'parent_id': str,
        'title': str,
        'text_raw': str,
        'text_norm': str,
        ...
    },
    'score': float,              # 최종 하이브리드 점수
    'dense_score': float,        # FAISS 점수 (text + title 가중합)
    'sparse_score': float,       # Whoosh 점수 (text + title 가중합)
    'text_score': float,         # 본문 점수 (FAISS 또는 Whoosh)
    'title_score': float,        # 제목 점수 (FAISS 또는 Whoosh)
    'parent_id': str,
    'title': str
}
```

## Error Handling

### 1. 인덱스 호환성 오류

**시나리오**: 기존 단일 FAISS 인덱스 파일이 존재하는 경우

**처리**:
```python
if old_index_exists and not new_indexes_exist:
    logger.error(
        "기존 FAISS 인덱스 형식이 감지되었습니다. "
        "새로운 형식의 인덱스를 생성하려면 Ingestion Container를 실행하세요: "
        "docker-compose -f docker/docker-compose.yml --profile ingestion run --rm ingestion"
    )
    raise ValueError("인덱스 형식 불일치")
```

### 2. 제목 또는 본문 검색 실패

**시나리오**: 제목 또는 본문 검색 결과가 없는 경우

**처리**:
```python
if not text_results and not title_results:
    logger.warning("제목과 본문 검색 모두 결과 없음")
    return []

if not text_results:
    logger.warning("본문 검색 결과 없음, 제목 검색 결과만 사용")
    return title_results

if not title_results:
    logger.warning("제목 검색 결과 없음, 본문 검색 결과만 사용")
    return text_results
```

### 3. 가중치 검증 오류

**시나리오**: 사용자가 잘못된 가중치를 입력한 경우

**처리**:
```python
def validate_weights(text_weight: float, title_weight: float):
    if text_weight < 0 or text_weight > 1:
        raise ValueError(f"본문 가중치는 0~1 사이여야 합니다: {text_weight}")
    
    if title_weight < 0 or title_weight > 1:
        raise ValueError(f"제목 가중치는 0~1 사이여야 합니다: {title_weight}")
    
    if abs(text_weight + title_weight - 1.0) > 0.001:
        raise ValueError(
            f"가중치 합은 1.0이어야 합니다: {text_weight} + {title_weight} = {text_weight + title_weight}"
        )
```

## Testing Strategy

### 1. 단위 테스트

**테스트 대상**:
- `TextEmbedder.create_dual_embeddings()`: 제목/본문 임베딩 생성
- `HybridSearcher.dense_search()`: 제목/본문 분리 검색
- `HybridSearcher.sparse_search()`: 제목/본문 분리 검색
- `ArticleMatcher._select_best_article_from_chunks()`: top-1 선택 로직

**테스트 케이스**:
```python
def test_dual_embeddings():
    """제목과 본문이 각각 임베딩되는지 확인"""
    chunks = [
        {'text_norm': '본문 내용', 'title': '제목'}
    ]
    text_embs, title_embs = embedder.create_dual_embeddings(chunks)
    assert len(text_embs) == len(title_embs) == 1
    assert text_embs[0] != title_embs[0]  # 다른 벡터

def test_field_weighted_search():
    """제목/본문 가중합이 올바르게 계산되는지 확인"""
    results = searcher.dense_search(
        text_query="본문 쿼리",
        title_query="제목 쿼리",
        top_k=5
    )
    for result in results:
        assert 'text_score' in result
        assert 'title_score' in result
        expected_score = (
            0.7 * result['text_score'] + 
            0.3 * result['title_score']
        )
        assert abs(result['dense_score'] - expected_score) < 0.001
```

### 2. 통합 테스트

**테스트 시나리오**:
1. Ingestion Container 실행 → 새로운 형식의 인덱스 생성 확인
2. Backend에서 새로운 인덱스 로드 → 검색 수행 → 결과 검증
3. UI에서 가중치 변경 → 검색 결과 변화 확인

### 3. 성능 테스트

**측정 지표**:
- 인덱스 생성 시간 (기존 대비 2배 예상)
- 검색 응답 시간 (기존과 유사해야 함)
- 메모리 사용량 (기존 대비 2배 예상)

**목표**:
- 검색 응답 시간 < 2초 (하위항목 5개 기준)
- 메모리 사용량 < 4GB (5종 계약서 인덱스)

## Performance Considerations

### 1. 인덱스 크기

**예상 증가량**:
- FAISS 인덱스: 2배 (text + title)
- Whoosh 인덱스: 변화 없음 (이미 멀티필드)

**최적화 방안**:
- FAISS 인덱스 압축 (IVF, PQ 등) - 향후 고려
- 메모리 캐싱 전략 유지

### 2. 검색 속도

**예상 영향**:
- FAISS 검색: 2배 호출 (text + title)
- Whoosh 검색: 2배 호출 (text + title)
- 가중합 계산: 추가 연산

**최적화 방안**:
- 병렬 검색 (asyncio 또는 ThreadPoolExecutor)
- 캐싱 전략 (동일 쿼리 재사용)

### 3. 임베딩 생성

**예상 영향**:
- API 호출 횟수: 2배
- 처리 시간: 2배
- 비용: 2배

**최적화 방안**:
- 배치 처리 (한 번에 여러 텍스트 임베딩)
- 재시도 로직 (API 실패 시)

## Migration Strategy

### Phase 1: 인덱스 재생성

1. Ingestion Container 코드 수정
2. 새로운 형식의 인덱스 생성
3. 기존 인덱스와 병행 유지 (롤백 대비)

### Phase 2: Backend 업데이트

1. HybridSearcher 수정
2. ArticleMatcher 수정
3. KnowledgeBaseLoader 수정
4. 기존 인덱스 형식 감지 및 에러 처리

### Phase 3: UI 추가

1. Streamlit UI에 설정 섹션 추가
2. 가중치 조정 기능 구현
3. 세션 상태 관리

### Phase 4: 검증 및 배포

1. 통합 테스트 수행
2. 성능 측정 및 최적화
3. 문서 업데이트
4. 프로덕션 배포

## Alternative Approaches

### 1. 가중합 방식

**현재 설계**: 본문:제목 = 7:3 고정 비율

**대안 1**: 동적 가중치
- 쿼리 길이에 따라 가중치 조정
- 짧은 쿼리: 제목 가중치 증가
- 긴 쿼리: 본문 가중치 증가

**대안 2**: 학습 기반 가중치
- 사용자 피드백 수집
- 최적 가중치 학습

**선택 이유**: 고정 비율이 구현이 간단하고 예측 가능하며, UI로 조정 가능

### 2. 조 단위 취합 방식

**현재 설계**: top-1 직접 선택

**대안 1**: 가중 평균
- 상위 N개 청크의 가중 평균 (순위에 따라 가중치 감소)

**대안 2**: 최대값 선택
- 각 조의 최고 점수만 사용

**선택 이유**: top-1 방식이 가장 직관적이고 구현이 간단하며, 불필요한 평균 계산 제거

### 3. FAISS 인덱스 구조

**현재 설계**: 두 개의 독립 인덱스

**대안 1**: 단일 인덱스 + 메타데이터
- 하나의 인덱스에 text/title 구분 메타데이터 추가

**대안 2**: 연결 벡터 (Concatenated Vector)
- text와 title 벡터를 연결하여 하나의 긴 벡터로 저장

**선택 이유**: 독립 인덱스가 검색 로직이 명확하고 가중치 조정이 용이
