# 검색 로직 수정 내역

## 문제 상황

유사도가 100%를 초과하는 문제 발생 (예: 270%, 318% 등)

## 원인 분석

### 기존 로직의 문제점

1. **중복 카운트**: 멀티벡터 검색에서 같은 청크가 여러 번 수집됨
2. **잘못된 집계**: 모든 검색 결과를 하나의 리스트에 모아서 조별로 집계
3. **비율 초과**: `matched_ratio = len(chunks) / total_chunks`가 1.0을 초과

### 구체적 예시

```python
# 하위항목 4개, 각각 top-5 검색
# 제5조의 청크 A, B, C, D가 각 검색에서 반복 등장

all_chunk_results = [
    # 하위항목 1: 제5조 청크 A, B, C, D
    # 하위항목 2: 제5조 청크 A, B, C, D (중복!)
    # 하위항목 3: 제5조 청크 A, B, C, D (중복!)
    # 하위항목 4: 제5조 청크 A, B, C, D (중복!)
]

# 제5조 그룹: 16개 청크 (실제로는 4개 청크가 4번씩 중복)
len(chunks) = 16
total_chunks = 4
matched_ratio = 16 / 4 = 4.0  # 400%!
normalized_score = avg_score * 4.0  # 최대 4.0까지 가능!
```

## 수정된 로직

### 핵심 변경 사항

**각 하위항목별로 독립적으로 계산 → 최종 집계**

### 단계별 처리

#### 1단계: 하위항목별 검색 및 조 선정

각 하위항목마다:
1. top_k 청크 검색 (하이브리드)
2. 청크를 조별로 그룹화
3. 각 조의 평균 점수 계산
4. **최고 점수 조 1개 선정**

```python
# 하위항목 1 검색 결과 (top-5)
제5조: (0.95 + 0.82 + 0.75 + 0.62) / 4 = 0.785 ← 선택
제3조: 0.68 / 1 = 0.68

# 하위항목 2 검색 결과 (top-5)
제5조: (0.92 + 0.85 + 0.78 + 0.65) / 4 = 0.80 ← 선택
제2조: 0.71 / 1 = 0.71

# 하위항목 3 검색 결과 (top-5)
제5조: (0.90 + 0.83 + 0.80 + 0.70) / 4 = 0.808 ← 선택
제4조: 0.65 / 1 = 0.65

# 하위항목 4 검색 결과 (top-5)
제5조: (0.88 + 0.81 + 0.76 + 0.72) / 4 = 0.793 ← 선택
제6조: 0.68 / 1 = 0.68
```

#### 2단계: 하위항목별 결과 수집

```python
sub_item_results = [
    {'sub_item': 1, 'matched_article': '제5조', 'score': 0.785},
    {'sub_item': 2, 'matched_article': '제5조', 'score': 0.80},
    {'sub_item': 3, 'matched_article': '제5조', 'score': 0.808},
    {'sub_item': 4, 'matched_article': '제5조', 'score': 0.793}
]
```

#### 3단계: 조 단위 최종 집계

같은 조를 선택한 하위항목들의 점수를 평균:

```python
제5조: (0.785 + 0.80 + 0.808 + 0.793) / 4 = 0.797
```

**결과**: 유사도 0.797 (79.7%) ✅

### 다중 조 매칭 지원

만약 하위항목별로 다른 조를 선택한 경우:

```python
sub_item_results = [
    {'sub_item': 1, 'matched_article': '제5조', 'score': 0.785},
    {'sub_item': 2, 'matched_article': '제5조', 'score': 0.80},
    {'sub_item': 3, 'matched_article': '제7조', 'score': 0.75},  # 다른 조!
    {'sub_item': 4, 'matched_article': '제5조', 'score': 0.793}
]

# 최종 결과: 2개 조 반환
matched_articles = [
    {
        'parent_id': '제5조',
        'score': (0.785 + 0.80 + 0.793) / 3 = 0.793,
        'matched_sub_items': [1, 2, 4]
    },
    {
        'parent_id': '제7조',
        'score': 0.75,
        'matched_sub_items': [3]
    }
]

# Primary: 제5조 (최고 점수)
```

## 수정된 함수

### 1. `_search_with_sub_items()`

**변경 전**: 모든 청크 결과를 `all_chunk_results`에 수집 → 조별 집계

**변경 후**: 각 하위항목별로 최고 조 선정 → 하위항목 결과 수집

### 2. `_select_best_article_from_chunks()` (신규)

하위항목의 top_k 청크에서 조별 평균 점수 계산 후 최고 조 반환

### 3. `_aggregate_sub_item_results()` (신규)

하위항목별 결과를 조 단위로 집계 (같은 조는 평균, 다른 조는 모두 포함)

### 4. `_aggregate_chunks_to_articles()` (삭제)

더 이상 사용하지 않음

### 5. `find_matching_article()`

**반환 형식 변경**:

```python
# 변경 전
{
    "matched": bool,
    "similarity": float,
    "std_article_id": str,
    "std_article_title": str,
    ...
}

# 변경 후
{
    "matched": bool,
    "matched_articles": List[Dict],  # 모든 매칭 조
    "primary_article": Dict,  # 최고 점수 조
    "sub_item_results": List[Dict],
    ...
}
```

## 점수 범위 보장

### 각 단계별 점수 범위

1. **하이브리드 검색**: 0 ≤ score ≤ 1.0
2. **조별 평균**: 0 ≤ avg_score ≤ 1.0
3. **하위항목별 조 점수**: 0 ≤ score ≤ 1.0
4. **최종 조 점수 (평균)**: 0 ≤ score ≤ 1.0

**결과**: 유사도가 항상 0~1 범위 내에 있음 ✅

## 테스트 필요 사항

1. 모든 하위항목이 같은 조를 선택하는 경우
2. 하위항목별로 다른 조를 선택하는 경우
3. 일부 하위항목만 매칭되는 경우
4. 매칭 실패 케이스

## 영향 받는 파일

- `backend/consistency_agent/nodes/article_matcher.py`
- `backend/consistency_agent/nodes/a3_node.py`
- `backend/consistency_agent/models.py`

## 호환성

- 프론트엔드는 `primary_article`의 `score`를 사용하면 기존과 동일하게 동작
- `matched_articles`를 통해 다중 매칭 조 정보 접근 가능
